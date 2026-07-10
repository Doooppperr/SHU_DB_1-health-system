from datetime import date
import json

from app.ai.service import AiCompletion, DeepSeekClient, answer_authenticated_question
from app.extensions import db
from app.models import FriendRelation, HealthIndicator, HealthRecord, IndicatorDict, User


def _register(client, username):
    response = client.post(
        "/api/auth/register",
        json=client.register_payload(username, email=f"{username}@example.com"),
    )
    assert response.status_code == 201
    payload = response.get_json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload["user"]["id"]


def _create_record(app, owner_id, uploader_id, value="6.2", status="confirmed"):
    with app.app_context():
        indicator_dict = IndicatorDict.query.filter_by(code="FBG").first()
        assert indicator_dict is not None
        record = HealthRecord(
            owner_id=owner_id,
            uploader_id=uploader_id,
            exam_date=date(2026, 7, 1),
            status=status,
        )
        db.session.add(record)
        db.session.flush()
        db.session.add(
            HealthIndicator(
                record_id=record.id,
                indicator_dict_id=indicator_dict.id,
                value=value,
                is_abnormal=True,
                source="manual",
            )
        )
        db.session.commit()
        return record.id


def test_guest_can_get_registration_faq_without_login(client):
    response = client.post(
        "/api/ai/chat",
        json={"message": "如何注册账号？", "history": [], "selected_record_ids": []},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "guest"
    assert payload["source"] == "faq"
    assert "注册" in payload["reply"]


def test_guest_fallback_uses_public_system_guide(client):
    response = client.post(
        "/api/ai/chat",
        json={"message": "请简单介绍一下这个平台", "history": []},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source"] == "model"
    assert payload["model"] == "mock-deepseek-v4-flash"


def test_guest_cannot_attach_health_records(client):
    response = client.post(
        "/api/ai/chat",
        json={"message": "解释指标", "selected_record_ids": [1]},
    )
    assert response.status_code == 403


def test_authenticated_user_can_ask_health_education_question(client):
    headers, _user_id = _register(client, "ai_health_user")
    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"message": "空腹血糖是什么意思？", "history": []},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "authenticated"
    assert payload["decision"] == "answer"
    assert "不构成疾病诊断" in payload["reply"]


def test_emergency_phrase_uses_deterministic_safety_reply(client):
    headers, _user_id = _register(client, "ai_emergency_user")
    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"message": "我胸痛而且呼吸困难", "history": []},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["decision"] == "emergency"
    assert payload["source"] == "safety_rule"
    assert "120" in payload["reply"]


def test_user_can_attach_multiple_confirmed_records_for_same_owner(client, app):
    headers, user_id = _register(client, "ai_record_owner")
    first_id = _create_record(app, user_id, user_id, value="6.2")
    second_id = _create_record(app, user_id, user_id, value="5.7")

    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={
            "message": "解释这两份报告里的空腹血糖",
            "history": [],
            "selected_record_ids": [first_id, second_id],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["selected_record_ids"] == [first_id, second_id]


def test_user_cannot_attach_unauthorized_record(client, app):
    headers, user_id = _register(client, "ai_requester")
    _owner_headers, owner_id = _register(client, "ai_private_owner")
    record_id = _create_record(app, owner_id, owner_id)

    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"message": "解释这份档案", "selected_record_ids": [record_id]},
    )

    assert response.status_code == 404
    assert user_id != owner_id


def test_selected_records_must_have_one_owner(client, app):
    headers, manager_id = _register(client, "ai_manager")
    _owner_headers, friend_id = _register(client, "ai_friend_owner")
    own_record_id = _create_record(app, manager_id, manager_id)
    friend_record_id = _create_record(app, friend_id, friend_id)

    with app.app_context():
        db.session.add(
            FriendRelation(
                user_id=manager_id,
                friend_user_id=friend_id,
                relation_name="亲友",
                auth_status=True,
            )
        )
        db.session.commit()

    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={
            "message": "综合解释",
            "selected_record_ids": [own_record_id, friend_record_id],
        },
    )

    assert response.status_code == 400
    assert "same owner" in response.get_json()["message"]


def test_only_confirmed_records_can_be_attached(client, app):
    headers, user_id = _register(client, "ai_draft_owner")
    record_id = _create_record(app, user_id, user_id, status="draft")

    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"message": "解释档案", "selected_record_ids": [record_id]},
    )
    assert response.status_code == 400


def test_ten_round_history_is_compacted_before_model_call(client):
    headers, _user_id = _register(client, "ai_history_user")
    history = []
    for index in range(10):
        history.extend(
            [
                {"role": "user", "content": f"问题 {index}"},
                {"role": "assistant", "content": f"回答 {index}"},
            ]
        )

    response = client.post(
        "/api/ai/chat",
        headers=headers,
        json={
            "message": "空腹血糖偏高通常和哪些生活因素有关？",
            "history": history,
            "summary": "",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["compacted_count"] == 2
    assert payload["summary"]


def test_invalid_history_shape_is_rejected(client):
    response = client.post(
        "/api/ai/chat",
        json={
            "message": "如何登录？",
            "history": [{"role": "user", "content": "上一条"}],
        },
    )
    assert response.status_code == 400


def test_unconfigured_provider_returns_503_for_model_fallback(client, app):
    app.config["AI_USE_MOCK"] = False
    app.config["DEEPSEEK_API_KEY"] = ""

    response = client.post(
        "/api/ai/chat",
        json={"message": "请概括平台的主要能力"},
    )
    assert response.status_code == 503


def test_deepseek_client_uses_v4_flash_non_thinking_json_mode(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "choices": [{"message": {"content": '{"decision":"answer","answer":"ok"}'}}],
                "usage": {"total_tokens": 12},
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.ai.service.requests.post", fake_post)
    client = DeepSeekClient(
        {
            "DEEPSEEK_API_KEY": "test-key-not-real",
            "DEEPSEEK_API_BASE": "https://api.deepseek.com",
            "DEEPSEEK_MODEL": "deepseek-v4-flash",
            "AI_REQUEST_TIMEOUT_SECONDS": 60,
        }
    )
    completion = client.complete(
        [{"role": "user", "content": "test"}],
        json_output=True,
    )

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["json"]["model"] == "deepseek-v4-flash"
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert completion.usage["total_tokens"] == 12


def test_support_decision_discards_generated_medical_answer():
    class SupportDecisionClient:
        @staticmethod
        def complete(_messages, **_kwargs):
            return AiCompletion(
                content=json.dumps(
                    {"decision": "support", "answer": "不应展示的具体治疗建议"},
                    ensure_ascii=False,
                ),
                usage={},
            )

    result = answer_authenticated_question(
        SupportDecisionClient(),
        "请直接给我一个治疗方案",
        history=[],
        summary="",
        record_context="未选择档案",
        support_phone="400-123-4567",
    )

    assert result["decision"] == "support"
    assert "400-123-4567" in result["reply"]
    assert "具体治疗建议" not in result["reply"]
