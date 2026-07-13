from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.ai import ai_bp
from app.ai.service import (
    AiConfigurationError,
    AiProviderError,
    answer_authenticated_question,
    answer_guest_question,
    emergency_reply,
    find_faq_answer,
    get_ai_client,
    is_emergency_message,
    merge_summary_deterministically,
    summarize_history,
)
from app.extensions import db
from app.models import FriendRelation, HealthRecord, User


_rate_buckets = defaultdict(deque)
_rate_lock = threading.Lock()


def _current_user_optional():
    identity = get_jwt_identity()
    if identity is None:
        return None
    return db.session.get(User, int(identity))


def _rate_limit_key(user):
    if user:
        return f"user:{user.id}"
    return f"guest:{request.remote_addr or 'unknown'}"


def _is_rate_limited(user):
    limit_key = (
        "AI_AUTH_RATE_LIMIT_PER_MINUTE" if user else "AI_GUEST_RATE_LIMIT_PER_MINUTE"
    )
    limit = int(current_app.config.get(limit_key, 30 if user else 10))
    now = time.monotonic()
    bucket_key = _rate_limit_key(user)
    with _rate_lock:
        bucket = _rate_buckets[bucket_key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
    return False


def _parse_history(raw_history):
    if raw_history is None:
        return [], None
    if not isinstance(raw_history, list):
        return None, "history must be a list"

    max_messages = int(current_app.config.get("AI_MAX_HISTORY_MESSAGES", 20))
    if len(raw_history) > max_messages:
        return None, f"history cannot contain more than {max_messages} messages"
    if len(raw_history) % 2 != 0:
        return None, "history must contain complete user/assistant rounds"

    history = []
    for index, item in enumerate(raw_history):
        if not isinstance(item, dict):
            return None, "history item must be an object"
        expected_role = "user" if index % 2 == 0 else "assistant"
        role = item.get("role")
        content = item.get("content")
        if role != expected_role:
            return None, "history roles must alternate user and assistant"
        if not isinstance(content, str) or not content.strip():
            return None, "history content cannot be empty"
        if len(content) > 4000:
            return None, "history content is too long"
        history.append({"role": role, "content": content.strip()})
    return history, None


def _parse_record_ids(raw_ids):
    if raw_ids is None:
        return [], None
    if not isinstance(raw_ids, list):
        return None, "selected_record_ids must be a list"

    max_records = int(current_app.config.get("AI_MAX_SELECTED_RECORDS", 5))
    if len(raw_ids) > max_records:
        return None, f"select at most {max_records} records"

    parsed = []
    for value in raw_ids:
        if isinstance(value, bool):
            return None, "record id must be integer"
        try:
            record_id = int(value)
        except (TypeError, ValueError):
            return None, "record id must be integer"
        if record_id not in parsed:
            parsed.append(record_id)
    return parsed, None


def _can_access_owner(user, owner_id):
    if user.role == "user" and user.id == owner_id:
        return True
    if user.role != "user":
        return False
    return (
        FriendRelation.query.filter_by(
            user_id=user.id,
            friend_user_id=owner_id,
            auth_status=True,
        ).first()
        is not None
    )


def _load_selected_records(user, record_ids):
    if not record_ids:
        return [], None, None

    records = HealthRecord.query.filter(HealthRecord.id.in_(record_ids)).all()
    by_id = {item.id: item for item in records}
    if len(by_id) != len(record_ids):
        return None, {"message": "record not found"}, 404

    ordered = [by_id[item_id] for item_id in record_ids]
    if any(not _can_access_owner(user, record.owner_id) for record in ordered):
        return None, {"message": "record not found"}, 404
    if any(record.status != "confirmed" for record in ordered):
        return None, {"message": "only confirmed records can be analyzed"}, 400

    owner_ids = {record.owner_id for record in ordered}
    if len(owner_ids) != 1:
        return None, {"message": "selected records must belong to the same owner"}, 400
    return ordered, None, None


def _format_record_context(user, records):
    if not records:
        return ""

    owner_label = "本人" if records[0].owner_id == user.id else "已授权亲友"
    sections = [f"档案归属：{owner_label}。共选择 {len(records)} 份档案。"]
    for index, record in enumerate(records, start=1):
        institution = record.institution.name if record.institution else "未填写机构"
        lines = [f"档案 {index}：体检日期 {record.exam_date.isoformat()}，机构 {institution}。"]
        if not record.indicators:
            lines.append("- 暂无指标。")
        for item in record.indicators:
            definition = item.indicator_dict
            if definition is None:
                continue
            reference = "未提供"
            if definition.reference_low is not None or definition.reference_high is not None:
                reference = (
                    f"{definition.reference_low if definition.reference_low is not None else '-∞'}"
                    f" ~ {definition.reference_high if definition.reference_high is not None else '+∞'}"
                    f" {definition.unit or ''}"
                ).strip()
            lines.append(
                f"- {definition.name}（{definition.code}）：{item.value} {definition.unit or ''}；"
                f"参考范围 {reference}；系统标记{'异常' if item.is_abnormal else '正常'}。"
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


@ai_bp.post("/chat")
@jwt_required(optional=True)
def chat():
    user = _current_user_optional()
    if get_jwt_identity() is not None and user is None:
        return {"message": "user not found"}, 404
    if _is_rate_limited(user):
        return {"message": "AI requests are too frequent, please try again later"}, 429

    payload = request.get_json(silent=True) or {}
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return {"message": "message is required"}, 400
    message = message.strip()
    if len(message) > 2000:
        return {"message": "message is too long"}, 400

    summary = payload.get("summary") or ""
    if not isinstance(summary, str) or len(summary) > 6000:
        return {"message": "summary is invalid or too long"}, 400

    history, history_error = _parse_history(payload.get("history"))
    if history_error:
        return {"message": history_error}, 400

    record_ids, record_error = _parse_record_ids(payload.get("selected_record_ids"))
    if record_error:
        return {"message": record_error}, 400
    if user is None and record_ids:
        return {"message": "login is required to use health records"}, 403
    if user is not None and user.role != "user" and record_ids:
        return {"message": "only regular users can use health records with AI"}, 403

    records = []
    if user:
        records, error_payload, error_status = _load_selected_records(user, record_ids)
        if error_payload:
            return error_payload, error_status

    compacted_count = 0
    model_history = history
    updated_summary = summary.strip()
    needs_compaction = len(history) >= int(
        current_app.config.get("AI_MAX_HISTORY_MESSAGES", 20)
    )

    faq_answer = find_faq_answer(message)
    is_local_emergency = user is not None and is_emergency_message(message)
    client = None
    try:
        if needs_compaction:
            compacted_count = 2
            model_history = history[2:]
            if faq_answer or is_local_emergency:
                updated_summary = merge_summary_deterministically(
                    updated_summary, history[:2]
                )
            else:
                client = get_ai_client(current_app.config)
                updated_summary = summarize_history(
                    client, updated_summary, history[:2]
                )

        support_phone = (current_app.config.get("AI_SUPPORT_PHONE") or "").strip()
        if faq_answer:
            result = {"reply": faq_answer, "decision": "answer", "usage": {}}
            source = "faq"
        elif is_local_emergency:
            result = {
                "reply": emergency_reply(),
                "decision": "emergency",
                "usage": {},
            }
            source = "safety_rule"
        else:
            client = client or get_ai_client(current_app.config)
            if user is None:
                result = answer_guest_question(
                    client,
                    message,
                    model_history,
                    updated_summary,
                    support_phone,
                )
            else:
                result = answer_authenticated_question(
                    client,
                    message,
                    model_history,
                    updated_summary,
                    _format_record_context(user, records),
                    support_phone,
                )
            source = "model"
    except AiConfigurationError:
        return {"message": "AI service is not configured"}, 503
    except AiProviderError:
        current_app.logger.exception("AI provider request failed")
        return {"message": "AI service is temporarily unavailable"}, 502

    response = {
        "reply": result["reply"],
        "decision": result["decision"],
        "source": source,
        "summary": updated_summary,
        "compacted_count": compacted_count,
        "mode": "authenticated" if user else "guest",
        "selected_record_ids": record_ids,
        "model": (
            getattr(client, "model", None)
            or current_app.config.get("DEEPSEEK_MODEL")
        )
        if source == "model"
        else None,
    }
    if response["decision"] == "support":
        response["support_phone"] = support_phone or None
    return response, 200
