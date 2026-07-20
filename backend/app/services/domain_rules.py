"""Single source of truth for package-domain admission and display placement."""

from app.extensions import db
from app.models import IndicatorDomainLink, PackageVersion, PackageVersionDomain


class DomainAdmissionError(ValueError):
    pass


def package_version_domain_ids(package_version_id):
    if not package_version_id:
        return set()
    return {
        row.health_domain_id
        for row in PackageVersionDomain.query.filter_by(package_version_id=package_version_id).all()
    }


def current_package_version(package):
    if package is None:
        return None
    if package.current_version_id:
        current = db.session.get(PackageVersion, package.current_version_id)
        if current:
            return current
    return PackageVersion.query.filter_by(package_id=package.id).order_by(
        PackageVersion.version_number.desc(), PackageVersion.id.desc()
    ).first()


def report_allowed_domain_ids(report):
    version_id = report.package_version_id
    if not version_id and report.appointment is not None:
        version_id = report.appointment.package_version_id
    if not version_id and report.package is not None:
        version = current_package_version(report.package)
        version_id = version.id if version else None
    return package_version_domain_ids(version_id)


def indicator_domain_ids(indicator_id):
    return {
        row.health_domain_id
        for row in IndicatorDomainLink.query.filter_by(indicator_dict_id=indicator_id).all()
    }


def resolve_display_domain(indicator_id, allowed_domain_ids):
    allowed = set(allowed_domain_ids)
    links = IndicatorDomainLink.query.filter_by(indicator_dict_id=indicator_id).order_by(
        IndicatorDomainLink.is_primary.desc(), IndicatorDomainLink.sort_order.asc(),
        IndicatorDomainLink.health_domain_id.asc(),
    ).all()
    matched = [row for row in links if row.health_domain_id in allowed]
    if not matched:
        raise DomainAdmissionError("indicator does not belong to an allowed package domain")
    primary = next((row for row in matched if row.is_primary), None)
    return (primary or matched[0]).health_domain_id


def admit_indicator(report, indicator_id):
    allowed = report_allowed_domain_ids(report)
    if not allowed:
        # Legacy records remain readable while unmapped packages are reviewed,
        # but new writes are never admitted without an explicit domain snapshot.
        raise DomainAdmissionError("appointment package has no approved health-domain snapshot")
    return resolve_display_domain(indicator_id, allowed)


def validate_report_domains(report):
    allowed = report_allowed_domain_ids(report)
    if not allowed:
        raise DomainAdmissionError("appointment package has no approved health-domain snapshot")
    for row in report.indicators:
        resolved = resolve_display_domain(row.indicator_dict_id, allowed)
        if row.display_domain_id not in {None, resolved}:
            raise DomainAdmissionError("indicator display domain conflicts with package snapshot")
        row.display_domain_id = resolved
    for row in report.text_results:
        if row.health_domain_id not in allowed:
            raise DomainAdmissionError("text result is outside the package domain snapshot")
    for row in report.assets:
        if row.health_domain_id not in allowed:
            raise DomainAdmissionError("asset is outside the package domain snapshot")
    return allowed
