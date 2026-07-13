from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from flask import current_app

from app.services.storage import get_storage_backend


def report_storage_key(report_file_url: str | None) -> str | None:
    raw_url = (report_file_url or "").strip()
    if not raw_url:
        return None
    parsed_path = unquote(urlparse(raw_url).path).replace("\\", "/")
    prefix = (current_app.config.get("UPLOAD_URL_BASE") or "/uploads").rstrip("/")
    if not parsed_path.startswith(f"{prefix}/"):
        return None
    storage_key = parsed_path[len(prefix) + 1 :]
    if not storage_key.startswith("reports/"):
        return None

    base_dir = Path(current_app.config["UPLOAD_DIR"]).resolve()
    target = (base_dir / storage_key).resolve()
    try:
        target.relative_to(base_dir)
    except ValueError:
        return None
    return storage_key


def report_file_path(report_file_url: str | None) -> Path | None:
    storage_key = report_storage_key(report_file_url)
    if storage_key is None:
        return None
    target = (Path(current_app.config["UPLOAD_DIR"]).resolve() / storage_key).resolve()
    return target if target.is_file() else None


def delete_report_urls(report_file_urls) -> None:
    storage = get_storage_backend(current_app.config)
    for report_file_url in set(report_file_urls):
        storage_key = report_storage_key(report_file_url)
        if storage_key is None:
            continue
        try:
            storage.delete(storage_key)
        except OSError:
            current_app.logger.exception(
                "failed to clean report file after database deletion: %s",
                storage_key,
            )
