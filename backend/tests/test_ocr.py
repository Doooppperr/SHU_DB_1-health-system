import io

from app.extensions import db
from app.models import HealthRecord
from app.services.ocr import OCRMappingService


def _auth_headers(client, username):
    client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "email": f"{username}@example.com"},
    )
    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secret123"},
    )
    access_token = login_response.get_json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _first_institution_and_package(client, headers):
    institutions = client.get("/api/institutions", headers=headers).get_json()["items"]
    institution_id = institutions[0]["id"]
    packages = client.get(f"/api/institutions/{institution_id}/packages", headers=headers).get_json()["items"]
    package_id = packages[0]["id"]
    return institution_id, package_id


def test_ocr_mapping_alias():
    service = OCRMappingService()

    assert service.normalize_key(" GLU(空腹) ") == "glu空腹"
    assert service.normalize_key("  空腹血糖  ") == "空腹血糖"


def test_upload_ocr_parse_and_confirm_flow(client, app):
    headers = _auth_headers(client, "ocr_user")
    institution_id, package_id = _first_institution_and_package(client, headers)

    response = client.post(
        "/api/records/upload",
        data={
            "exam_date": "2026-04-08",
            "institution_id": str(institution_id),
            "package_id": str(package_id),
            "file": (io.BytesIO(b"fake pdf"), "report.pdf"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()

    assert payload["item"]["status"] == "parsed"
    assert payload["ocr"]["mapped_count"] >= 3
    assert payload["ocr"]["unmatched_count"] >= 1

    record_id = payload["item"]["id"]

    confirm_response = client.put(f"/api/records/{record_id}/confirm", headers=headers)
    assert confirm_response.status_code == 200
    assert confirm_response.get_json()["item"]["status"] == "confirmed"

    with app.app_context():
        record = db.session.get(HealthRecord, record_id)
        assert record is not None
        assert record.status == "confirmed"


def test_upload_ocr_requires_file(client):
    headers = _auth_headers(client, "ocr_missing_file_user")

    response = client.post(
        "/api/records/upload",
        data={"exam_date": "2026-04-08"},
        headers=headers,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

