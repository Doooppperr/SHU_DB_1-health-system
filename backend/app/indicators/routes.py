from flask import request
from flask_jwt_extended import jwt_required

from app.indicators import indicators_bp
from app.models import IndicatorCategory, IndicatorDict


@indicators_bp.get("/dicts")
@jwt_required()
def list_indicator_dicts():
    keyword = (request.args.get("keyword") or "").strip().lower()

    query = (
        IndicatorDict.query.join(IndicatorCategory)
        .order_by(IndicatorCategory.sort_order.asc(), IndicatorDict.id.asc())
    )

    items = query.all()
    if keyword:
        items = [
            item
            for item in items
            if keyword in item.name.lower()
            or keyword in item.code.lower()
            or any(keyword in alias.lower() for alias in (item.aliases or []))
        ]

    return {"items": [item.to_dict() for item in items]}, 200
