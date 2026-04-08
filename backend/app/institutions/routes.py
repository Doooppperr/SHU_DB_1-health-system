from flask_jwt_extended import jwt_required

from app.extensions import db
from app.institutions import institutions_bp
from app.models import Institution, Package


@institutions_bp.get("")
@jwt_required()
def list_institutions():
    institutions = Institution.query.order_by(Institution.id.asc()).all()
    return {"items": [item.to_dict() for item in institutions]}, 200


@institutions_bp.get("/<int:institution_id>")
@jwt_required()
def get_institution_detail(institution_id: int):
    institution = db.session.get(Institution, institution_id)
    if institution is None:
        return {"message": "institution not found"}, 404

    return {"item": institution.to_dict()}, 200


@institutions_bp.get("/<int:institution_id>/packages")
@jwt_required()
def list_packages(institution_id: int):
    institution = db.session.get(Institution, institution_id)
    if institution is None:
        return {"message": "institution not found"}, 404

    packages = Package.query.filter_by(institution_id=institution_id).order_by(Package.id.asc()).all()
    return {
        "institution": {
            "id": institution.id,
            "name": institution.name,
            "branch_name": institution.branch_name,
        },
        "items": [item.to_dict() for item in packages],
    }, 200
