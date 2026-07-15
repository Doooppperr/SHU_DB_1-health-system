from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from app.extensions import db
from app.ai.rag import RetrievalResult
from app.models import ExamRegistration, IndicatorDict, Institution, InstitutionReport, SelfMeasurement, User
from app.services.record_files import report_file_path
from app.services.reports import cleanup_expired_reports


PASSWORD = "Shuhealthdoc！"


def login(client, username, password=PASSWORD):
    response = client.post("/api/auth/login", json=client.login_payload(username, password))
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def report_fixture(app, *, user="test3", institution_index=0):
    with app.app_context():
        person = User.query.filter_by(username=user).first()
        institution = Institution.query.order_by(Institution.id).all()[institution_index]
        indicator = IndicatorDict.query.filter_by(code="HR").first()
        return person.real_name, person.health_id, institution.id, indicator.id


def create_locked_report(client, headers, name, health_id, institution_id, indicator_id, exam_day):
    response = client.post("/api/org/reports", headers=headers, json={"subject_name": name, "subject_health_id": health_id, "exam_date": exam_day.isoformat()})
    assert response.status_code == 201
    report_id = response.get_json()["item"]["id"]
    assert client.post(f"/api/org/reports/{report_id}/indicators", headers=headers, json={"indicator_dict_id": indicator_id, "value": "73"}).status_code == 201
    assert client.post(f"/api/org/reports/{report_id}/lock", headers=headers).status_code == 200
    return report_id


def test_health_identity_profile_and_multi_institution_accounts(app, client):
    captcha = client.get("/api/auth/captcha").get_json()
    registered = client.post("/api/auth/register", json={"username": "new-person", "password": "secret123", "captcha_id": captcha["captcha_id"], "captcha_answer": captcha["captcha_answer"]})
    assert registered.status_code == 201
    token = {"Authorization": f"Bearer {registered.get_json()['access_token']}"}
    health_id = registered.get_json()["user"]["health_id"]
    assert health_id.startswith("HID-")
    assert client.put("/api/profile/me", headers=token, json={"health_id": "HID-FORGED1"}).status_code == 409
    profile = client.put("/api/profile/me", headers=token, json={"real_name": "新用户", "birth_date": "1990-02-03", "gender": "female"})
    assert profile.status_code == 200 and profile.get_json()["item"]["health_id"] == health_id

    admin = login(client, "admin", "admin123")
    with app.app_context(): institution_id = Institution.query.first().id
    invite = client.post(f"/api/admin/institutions/{institution_id}/invite", headers=admin).get_json()["invite_code"]
    captcha = client.get("/api/auth/captcha").get_json()
    staff = client.post("/api/auth/register", json={"username": "third-staff", "password": "secret123", "invite_code": invite, "captcha_id": captcha["captcha_id"], "captcha_answer": captcha["captcha_answer"]})
    assert staff.status_code == 201 and staff.get_json()["user"]["role"] == "institution_admin"
    with app.app_context(): assert User.query.filter_by(managed_institution_id=institution_id, role="institution_admin").count() == 3


def test_both_matching_directions_lock_and_scope(app, client):
    name, health_id, institution_id, indicator_id = report_fixture(app)
    user = login(client, "test3"); org = login(client, "institution1_staff1"); other_org = login(client, "institution2_staff1")
    first_day = date.today() + timedelta(days=7)
    registration = client.post("/api/exam-registrations", headers=user, json={"institution_id": institution_id, "exam_date": first_day.isoformat()})
    assert registration.status_code == 201 and registration.get_json()["match_result"] == "not_found"
    report_id = create_locked_report(client, org, name, health_id, institution_id, indicator_id, first_day)
    assert client.put(f"/api/org/reports/{report_id}", headers=org, json={"exam_date": date.today().isoformat()}).status_code == 409
    submitted = client.post(f"/api/org/reports/{report_id}/submit", headers=org)
    assert submitted.status_code == 200 and submitted.get_json()["match_result"] == "matched"
    assert client.get(f"/api/org/reports/{report_id}", headers=other_org).status_code == 404

    second_day = first_day + timedelta(days=1)
    second_id = create_locked_report(client, org, name, health_id, institution_id, indicator_id, second_day)
    assert client.post(f"/api/org/reports/{second_id}/submit", headers=org).get_json()["match_result"] == "not_found"
    reverse = client.post("/api/exam-registrations", headers=user, json={"institution_id": institution_id, "exam_date": second_day.isoformat()})
    assert reverse.status_code == 201 and reverse.get_json()["match_result"] == "matched"
    assert len(client.get("/api/exam-reports", headers=user).get_json()["items"]) >= 2
    assert client.get("/api/records", headers=user).status_code == 404
    assert client.get("/api/admin/records", headers=login(client, "admin", "admin123")).status_code == 404


def test_registration_uniqueness_expiry_and_cancel_rules(app, client):
    user = login(client, "test3")
    with app.app_context(): ids = [item.id for item in Institution.query.order_by(Institution.id).limit(2)]
    day = date.today() + timedelta(days=20)
    assert client.post("/api/exam-registrations", headers=user, json={"institution_id": ids[0], "exam_date": day.isoformat()}).status_code == 201
    assert client.post("/api/exam-registrations", headers=user, json={"institution_id": ids[1], "exam_date": day.isoformat()}).status_code == 409
    with app.app_context():
        waiting = InstitutionReport.query.filter_by(status="waiting_match").first()
        waiting.expires_at = datetime.now(timezone.utc) - timedelta(microseconds=1)
        waiting_id = waiting.id; db.session.commit()
        assert waiting_id in cleanup_expired_reports()
        assert db.session.get(InstitutionReport, waiting_id) is None


def test_self_measurement_trend_priority_withdraw_fallback(app, client):
    headers = login(client, "test1")
    with app.app_context():
        weight = IndicatorDict.query.filter_by(code="WEIGHT").first(); bmi = IndicatorDict.query.filter_by(code="BMI").first()
        weight_id, bmi_id = weight.id, bmi.id
    day = date.today() - timedelta(days=4)
    for hour, value in ((8, 70.1), (20, 70.8)):
        response = client.post("/api/self-measurements", headers=headers, json={"indicator_dict_id": weight_id, "value": value, "measured_at": f"{day.isoformat()}T{hour:02d}:00:00+00:00"})
        assert response.status_code == 201
    assert client.post("/api/self-measurements", headers=headers, json={"indicator_dict_id": bmi_id, "value": 22, "measured_at": datetime.now(timezone.utc).isoformat()}).status_code == 400
    trend = client.get(f"/api/health/trends/{weight_id}", headers=headers).get_json()["points"]
    point = next(item for item in trend if item["date"] == day.isoformat())
    assert point["source"] == "institution_report" and point["value"] == 71.9
    with app.app_context():
        report = InstitutionReport.query.filter_by(matched_user_id=User.query.filter_by(username="test1").first().id, exam_date=day, status="published").first()
        report.status = "withdrawn"; report.withdrawn_at = datetime.now(timezone.utc); db.session.commit()
    fallback = client.get(f"/api/health/trends/{weight_id}", headers=headers).get_json()["points"]
    point = next(item for item in fallback if item["date"] == day.isoformat())
    assert point["source"] == "self_measurement" and point["value"] == 70.8


def test_friend_read_only_privacy_and_role_isolation(app, client):
    viewer = login(client, "test1")
    with app.app_context():
        owner = User.query.filter_by(username="test2").first()
        owner_id, owner_name = owner.id, owner.real_name
    timeline = client.get(f"/api/health/timeline?owner_id={owner_id}", headers=viewer)
    assert timeline.status_code == 200
    serialized = str(timeline.get_json())
    assert "health_id" not in serialized and "allergy_history" not in serialized and "subject_name_snapshot" not in serialized
    assert owner_name not in serialized
    assert client.post("/api/self-measurements", headers=login(client, "institution1_staff1"), json={}).status_code == 403
    assert client.get("/api/health/timeline", headers=login(client, "admin", "admin123")).status_code == 403


def test_ai_requires_per_request_consent_and_excludes_identity(app, client):
    headers = login(client, "test1")
    available = client.get("/api/ai/records", headers=headers)
    assert available.status_code == 200 and available.get_json()["items"]
    report_id = available.get_json()["items"][0]["id"]
    denied = client.post("/api/ai/analyze/stream", headers=headers, json={"selected_record_ids": [report_id]})
    assert denied.status_code == 400
    allowed = client.post("/api/ai/analyze/stream", headers=headers, json={"selected_record_ids": [report_id], "consent": True}, buffered=True)
    assert allowed.status_code == 200
    body = allowed.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(username="test1").first()
        assert user.health_id not in body
        assert user.real_name not in body


def test_org_ocr_mock_creates_reviewable_draft_and_lock_deletes_file(app, client):
    headers = login(client, "institution2_staff1")
    name, health_id, _institution_id, _indicator_id = report_fixture(app, institution_index=1)
    response = client.post(
        "/api/org/reports/ocr", headers=headers,
        data={"file": (BytesIO(b"mock report"), "report.pdf"), "subject_name": name, "subject_health_id": health_id, "exam_date": (date.today() + timedelta(days=40)).isoformat()},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    report_id = response.get_json()["item"]["id"]
    with app.app_context():
        report = db.session.get(InstitutionReport, report_id)
        path = report_file_path(report.temporary_file_url)
        assert path and path.exists() and report.indicators
    locked = client.post(f"/api/org/reports/{report_id}/lock", headers=headers)
    assert locked.status_code == 200
    assert not path.exists()
    assert "raw_text" not in str(locked.get_json()["item"].get("ocr_diagnostics"))


def test_admin_cascade_deletes_regular_user_business_data(app, client):
    admin = login(client, "admin", "admin123")
    with app.app_context():
        user = User.query.filter_by(username="test3").first()
        institution = Institution.query.first()
        indicator = IndicatorDict.query.filter_by(code="HR").first()
        user_id = user.id
        db.session.add(SelfMeasurement(user_id=user.id, indicator_dict_id=indicator.id, value=70, measured_at=datetime.now(timezone.utc)))
        db.session.add(ExamRegistration(user_id=user.id, institution_id=institution.id, exam_date=date.today() + timedelta(days=55)))
        db.session.commit()
    assert client.delete(f"/api/users/{user_id}", headers=admin, json={"confirm": True}).status_code == 200
    with app.app_context():
        assert db.session.get(User, user_id) is None
        assert SelfMeasurement.query.filter_by(user_id=user_id).count() == 0
        assert ExamRegistration.query.filter_by(user_id=user_id).count() == 0


def test_ai_emergency_skips_public_knowledge_retrieval(app, client):
    class ForbiddenRetriever:
        @staticmethod
        def retrieve(*_args, **_kwargs):
            raise AssertionError("emergency path must not invoke RAG")

    app.extensions["knowledge_retriever"] = ForbiddenRetriever()
    response = client.post(
        "/api/ai/chat/stream",
        headers=login(client, "test1"),
        json={"message": "我胸痛并且呼吸困难", "history": []},
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"decision":"emergency"' in body
    assert '"stage":"retrieving"' not in body


def test_ai_owner_scope_uses_published_reports_and_degrades_without_rag(app, client):
    class UnavailableRetriever:
        @staticmethod
        def retrieve(*_args, **_kwargs):
            return RetrievalResult(status="unavailable", error_code="test_unavailable")

    app.extensions["knowledge_retriever"] = UnavailableRetriever()
    with app.app_context():
        user = User.query.filter_by(username="test1").first()
        owner_id = user.id
        expected_ids = [
            item.id
            for item in InstitutionReport.query.filter_by(
                matched_user_id=user.id, status="published"
            ).order_by(InstitutionReport.exam_date, InstitutionReport.id)
        ]
    response = client.post(
        "/api/ai/chat",
        headers=login(client, "test1"),
        json={
            "message": "请解释这些历史报告的整体变化",
            "record_scope": {"owner_id": owner_id, "mode": "all_confirmed"},
            "consent": True,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["selected_record_ids"] == expected_ids
    assert payload["rag_used"] is False
    assert payload["retrieval_status"] == "unavailable"


def test_admin_ai_retrieves_only_public_audience(app, client):
    audiences = []

    class CapturingRetriever:
        @staticmethod
        def retrieve(_query, *, audience, **_kwargs):
            audiences.append(audience)
            return RetrievalResult(status="no_match")

    app.extensions["knowledge_retriever"] = CapturingRetriever()
    response = client.post(
        "/api/ai/chat",
        headers=login(client, "demo_admin"),
        json={"message": "请说明平台公共知识检索边界", "history": []},
    )
    assert response.status_code == 200
    assert audiences == ["public"]
