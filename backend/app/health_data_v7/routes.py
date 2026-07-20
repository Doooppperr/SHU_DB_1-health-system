from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app, g, request, send_file

from app.extensions import db
from app.health_data_v7 import health_data_v7_bp
from app.models import (
    FriendRelation, HealthDomain, IndicatorDomainLink, InstitutionReport,
    ReportAsset, ReportIndicator, SelfMeasurement, User,
)
from app.services.permissions import ROLE_ADMIN, ROLE_INSTITUTION_ADMIN, ROLE_USER, roles_required


BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


def _measurement_day(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TZ).date()


def _day_bounds(day):
    return (
        datetime.combine(day, time.min, tzinfo=BUSINESS_TZ).astimezone(timezone.utc),
        datetime.combine(day, time.max, tzinfo=BUSINESS_TZ).astimezone(timezone.utc),
    )


def _owner():
    raw = request.args.get("owner_id")
    if raw in {None, ""}: return g.current_user, None
    try: owner_id = int(raw)
    except (TypeError, ValueError): return None, ({"message": "owner_id must be an integer"}, 400)
    if owner_id == g.current_user.id: return g.current_user, None
    relation = FriendRelation.query.filter_by(user_id=g.current_user.id, friend_user_id=owner_id, auth_status=True).first()
    owner = db.session.get(User, owner_id) if relation else None
    if not owner or owner.role != "user": return None, ({"message": "friend authorization required"}, 403)
    return owner, None


def _date_range():
    try:
        start = date.fromisoformat(request.args["start_date"]) if request.args.get("start_date") else None
        end = date.fromisoformat(request.args["end_date"]) if request.args.get("end_date") else None
    except ValueError:
        return None, None, ({"message": "date range must use YYYY-MM-DD"}, 400)
    if start and end and start > end: return None, None, ({"message": "start_date must not exceed end_date"}, 400)
    return start, end, None


def _pagination():
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    requested = request.args.get("page_size", 15, type=int) or 15
    return page, 30 if requested == 30 else 15


def report_key(report): return f"hd-i-{report.id:x}"
def self_key(owner_id, day): return f"hd-s-{owner_id:x}-{day.isoformat()}"


def parse_key(value):
    try:
        if value.startswith("hd-i-"): return "institution", int(value[5:], 16)
        if value.startswith("hd-s-"):
            owner_hex, day = value[5:].split("-", 1)
            return "self", (int(owner_hex, 16), date.fromisoformat(day))
    except (TypeError, ValueError):
        pass
    return None, None


@health_data_v7_bp.get("/health-domains")
@roles_required(ROLE_USER, ROLE_INSTITUTION_ADMIN, ROLE_ADMIN)
def domains():
    rows = HealthDomain.query.filter_by(is_active=True).order_by(HealthDomain.sort_order, HealthDomain.id).all()
    return {"items": [row.to_dict() for row in rows]}, 200


@health_data_v7_bp.get("/health-data")
@roles_required(ROLE_USER)
def health_data_list():
    owner, error = _owner()
    if error: return error
    start, end, error = _date_range()
    if error: return error
    institution_id = request.args.get("institution_id", type=int)
    domain_id = request.args.get("domain_id", type=int)
    records = []
    query = InstitutionReport.query.filter_by(matched_user_id=owner.id, status="published")
    if start: query = query.filter(InstitutionReport.exam_date >= start)
    if end: query = query.filter(InstitutionReport.exam_date <= end)
    if institution_id: query = query.filter(InstitutionReport.institution_id == institution_id)
    if domain_id:
        query = query.filter(db.or_(
            InstitutionReport.indicators.any(ReportIndicator.display_domain_id == domain_id),
            InstitutionReport.text_results.any(health_domain_id=domain_id),
            InstitutionReport.assets.any(health_domain_id=domain_id),
        ))
    for report in query.all():
        domain_ids = {row.display_domain_id for row in report.indicators if row.display_domain_id}
        domain_ids.update(row.health_domain_id for row in report.text_results)
        domain_ids.update(row.health_domain_id for row in report.assets)
        domain_rows = HealthDomain.query.filter(HealthDomain.id.in_(domain_ids)).order_by(HealthDomain.sort_order).all() if domain_ids else []
        records.append({"health_data_id": report_key(report), "source_type": "institution",
                        "business_date": report.exam_date.isoformat(),
                        "source": {"id": report.institution_id, "name": report.institution.name,
                                   "branch_name": report.institution.branch_name} if report.institution else None,
                        "package": {"id": report.package_id, "name": report.package.name} if report.package else None,
                        "domains": [row.to_dict() for row in domain_rows], "indicator_count": len(report.indicators),
                        "text_result_count": len(report.text_results), "asset_count": len(report.assets)})
    if not institution_id:
        measurements = SelfMeasurement.query.filter_by(user_id=owner.id)
        if start: measurements = measurements.filter(SelfMeasurement.measured_at >= _day_bounds(start)[0])
        if end: measurements = measurements.filter(SelfMeasurement.measured_at <= _day_bounds(end)[1])
        grouped = defaultdict(list)
        for row in measurements.order_by(SelfMeasurement.measured_at, SelfMeasurement.id).all():
            linked_domains = {link.health_domain_id for link in row.indicator_dict.domain_links}
            if domain_id and domain_id not in linked_domains: continue
            grouped[_measurement_day(row.measured_at)].append(row)
        for day, rows in grouped.items():
            domain_ids = {link.health_domain_id for row in rows for link in row.indicator_dict.domain_links if link.is_primary}
            domain_rows = HealthDomain.query.filter(HealthDomain.id.in_(domain_ids)).order_by(HealthDomain.sort_order).all() if domain_ids else []
            records.append({"health_data_id": self_key(owner.id, day), "source_type": "self",
                            "business_date": day.isoformat(), "source": {"id": None, "name": "个人自测", "branch_name": None},
                            "package": None, "domains": [row.to_dict() for row in domain_rows],
                            "indicator_count": len(rows), "text_result_count": 0, "asset_count": 0})
    records.sort(key=lambda row: (row["business_date"], row["health_data_id"]), reverse=True)
    page, size = _pagination(); total = len(records)
    return {"owner": owner.friend_identity_dict(), "items": records[(page - 1) * size:page * size],
            "pagination": {"page": page, "page_size": size, "total": total, "pages": (total + size - 1) // size}}, 200


def _detail_for(owner, health_data_id):
    kind, value = parse_key(health_data_id)
    sections = defaultdict(lambda: {"indicators": [], "text_results": [], "assets": []})
    if kind == "institution":
        report = InstitutionReport.query.filter_by(id=value, matched_user_id=owner.id, status="published").first()
        if not report: return None
        for row in report.indicators:
            if row.display_domain_id: sections[row.display_domain_id]["indicators"].append(row.to_dict())
        for row in report.text_results: sections[row.health_domain_id]["text_results"].append(row.to_dict())
        for row in report.assets: sections[row.health_domain_id]["assets"].append(row.to_dict(health_data_id))
        source = {"id": report.institution_id, "name": report.institution.name,
                  "branch_name": report.institution.branch_name} if report.institution else None
        package = {"id": report.package_id, "name": report.package.name} if report.package else None
        business_date = report.exam_date.isoformat()
    elif kind == "self" and value[0] == owner.id:
        day = value[1]
        start_at, end_at = _day_bounds(day)
        rows = SelfMeasurement.query.filter_by(user_id=owner.id).filter(
            SelfMeasurement.measured_at >= start_at,
            SelfMeasurement.measured_at <= end_at,
        ).order_by(SelfMeasurement.measured_at, SelfMeasurement.id).all()
        if not rows: return None
        for row in rows:
            link = next((item for item in row.indicator_dict.domain_links if item.is_primary), None)
            if link: sections[link.health_domain_id]["indicators"].append(row.to_dict())
        source = {"id": None, "name": "个人自测", "branch_name": None}; package = None; business_date = day.isoformat()
    else:
        return None
    rendered = []
    for domain_id, values in sections.items():
        domain = db.session.get(HealthDomain, domain_id)
        rendered.append({"domain": domain.to_dict(), **values})
    rendered.sort(key=lambda row: (row["domain"]["sort_order"], row["domain"]["id"]))
    return {"health_data_id": health_data_id, "source_type": kind, "business_date": business_date,
            "source": source, "package": package, "sections": rendered}


@health_data_v7_bp.get("/health-data/<health_data_id>")
@roles_required(ROLE_USER)
def health_data_detail(health_data_id):
    owner, error = _owner()
    if error: return error
    item = _detail_for(owner, health_data_id)
    return ({"item": item, "owner": owner.friend_identity_dict()}, 200) if item else ({"message": "health data not found"}, 404)


@health_data_v7_bp.get("/health-data/<health_data_id>/assets/<int:asset_id>/content")
@roles_required(ROLE_USER)
def asset_content(health_data_id, asset_id):
    owner, error = _owner()
    if error: return error
    kind, report_id = parse_key(health_data_id)
    if kind != "institution": return {"message": "asset not found"}, 404
    asset = db.session.query(ReportAsset).join(InstitutionReport).filter(
        ReportAsset.id == asset_id, ReportAsset.report_id == report_id,
        InstitutionReport.matched_user_id == owner.id, InstitutionReport.status == "published").first()
    if not asset: return {"message": "asset not found"}, 404
    path = Path(current_app.config["UPLOAD_DIR"]) / asset.storage_key
    if not path.is_file(): return {"message": "asset content unavailable"}, 404
    return send_file(path, mimetype=asset.mime_type, download_name=asset.title, conditional=True)


@health_data_v7_bp.get("/health-trends/<int:domain_id>")
@roles_required(ROLE_USER)
def health_trends(domain_id):
    owner, error = _owner()
    if error: return error
    domain = db.session.get(HealthDomain, domain_id)
    if not domain or not domain.is_active: return {"message": "health domain not found"}, 404
    start, end, error = _date_range()
    if error: return error
    institution_id = request.args.get("institution_id", type=int)
    items = []
    links = IndicatorDomainLink.query.filter_by(health_domain_id=domain.id).order_by(
        IndicatorDomainLink.sort_order, IndicatorDomainLink.indicator_dict_id).all()
    for link in links:
        definition = link.indicator; sources = defaultdict(list)
        reports = db.session.query(ReportIndicator, InstitutionReport).join(InstitutionReport).filter(
            InstitutionReport.matched_user_id == owner.id, InstitutionReport.status == "published",
            ReportIndicator.indicator_dict_id == definition.id, ReportIndicator.display_domain_id == domain.id)
        if start: reports = reports.filter(InstitutionReport.exam_date >= start)
        if end: reports = reports.filter(InstitutionReport.exam_date <= end)
        if institution_id: reports = reports.filter(InstitutionReport.institution_id == institution_id)
        for result, report in reports.order_by(InstitutionReport.exam_date, InstitutionReport.id).all():
            try: numeric = float(result.value)
            except (TypeError, ValueError): continue
            key = f"institution:{report.institution_id}"
            sources[key].append({"date": report.exam_date.isoformat(), "value": numeric,
                                 "unit": result.normalized_unit or definition.unit,
                                 "reference": result.reference_text, "is_abnormal": result.is_abnormal,
                                 "health_data_id": report_key(report),
                                 "source": {"type": "institution", "id": report.institution_id,
                                            "name": report.institution.name, "branch_name": report.institution.branch_name}})
        if not institution_id:
            measurements = SelfMeasurement.query.filter_by(user_id=owner.id, indicator_dict_id=definition.id)
            if start: measurements = measurements.filter(SelfMeasurement.measured_at >= _day_bounds(start)[0])
            if end: measurements = measurements.filter(SelfMeasurement.measured_at <= _day_bounds(end)[1])
            daily = {}
            for row in measurements.order_by(SelfMeasurement.measured_at, SelfMeasurement.id).all(): daily[_measurement_day(row.measured_at)] = row
            for day, row in sorted(daily.items()):
                sources["self"].append({"date": day.isoformat(), "value": float(row.value), "unit": definition.unit,
                                        "measured_at": row.measured_at.isoformat(), "health_data_id": self_key(owner.id, day),
                                        "source": {"type": "self", "id": None, "name": "个人自测"}})
        if sources:
            series = []
            for key, points in sources.items():
                previous = points[-2]["value"] if len(points) > 1 else None
                series.append({"source_key": key, "source": points[-1]["source"], "points": points,
                               "summary": {"latest": points[-1]["value"],
                                           "change": points[-1]["value"] - previous if previous is not None else None,
                                           "count": len(points)}})
            items.append({"indicator": definition.to_dict(), "series": series})
    assets = db.session.query(ReportAsset, InstitutionReport).join(InstitutionReport).filter(
        InstitutionReport.matched_user_id == owner.id, InstitutionReport.status == "published",
        ReportAsset.health_domain_id == domain.id)
    if start: assets = assets.filter(InstitutionReport.exam_date >= start)
    if end: assets = assets.filter(InstitutionReport.exam_date <= end)
    if institution_id: assets = assets.filter(InstitutionReport.institution_id == institution_id)
    asset_events = [{"date": report.exam_date.isoformat(), "health_data_id": report_key(report),
                     "asset": asset.to_dict(report_key(report)),
                     "source": {"type": "institution", "id": report.institution_id,
                                "name": report.institution.name, "branch_name": report.institution.branch_name}}
                    for asset, report in assets.order_by(InstitutionReport.exam_date, ReportAsset.sort_order).all()]
    return {"owner": owner.friend_identity_dict(), "domain": domain.to_dict(),
            "series_by_indicator": items, "asset_events": asset_events,
            "abnormal_count": sum(1 for item in items for series in item["series"] for point in series["points"] if point.get("is_abnormal"))}, 200
