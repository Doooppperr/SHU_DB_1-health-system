from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Organization
from app.organizations import organizations_bp


@organizations_bp.get("")
@jwt_required()
def list_organizations():
    rows = Organization.query.filter_by(is_active=True).order_by(Organization.id).all()
    items = []
    for row in rows:
        payload = row.to_dict(include_branches=True)
        payload["branches"] = [branch for branch in payload["branches"] if branch["is_active"]]
        payload["active_branch_count"] = len(payload["branches"])
        items.append(payload)
    return {"items": items}, 200


@organizations_bp.get("/<int:organization_id>")
@jwt_required()
def get_organization(organization_id):
    row = db.session.get(Organization, organization_id)
    if row is None or not row.is_active:
        return {"message": "organization not found"}, 404
    payload = row.to_dict(include_branches=True)
    payload["branches"] = [branch for branch in payload["branches"] if branch["is_active"]]
    return {"item": payload}, 200
