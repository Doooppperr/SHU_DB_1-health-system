"""Create a joint SQLite + permanent-health-asset recovery archive and manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

BACKEND_DIR = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): value.update(chunk)
    return value.hexdigest()


def create_recovery_set(database, upload_dir, output):
    database, upload_dir, output = database.resolve(), upload_dir.resolve(), output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        snapshot = Path(temporary) / "health_system.db"
        source = sqlite3.connect(database); target = sqlite3.connect(snapshot)
        try: source.backup(target)
        finally: target.close(); source.close()
        connection = sqlite3.connect(snapshot)
        try:
            rows = connection.execute("SELECT storage_key, sha256, byte_size FROM report_assets ORDER BY id").fetchall()
        finally: connection.close()
        assets = []
        for key, expected_hash, expected_size in rows:
            path = (upload_dir / key).resolve()
            if not path.is_relative_to(upload_dir) or not path.is_file(): raise RuntimeError(f"missing permanent asset: {key}")
            actual_hash = digest(path)
            if expected_hash != actual_hash or path.stat().st_size != expected_size: raise RuntimeError(f"asset checksum mismatch: {key}")
            assets.append({"storage_key": key, "sha256": actual_hash, "byte_size": expected_size})
        manifest = {"schema_version": 7, "created_at": datetime.now(timezone.utc).isoformat(),
                    "database": {"name": "health_system.db", "sha256": digest(snapshot), "byte_size": snapshot.stat().st_size},
                    "assets": assets}
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "database/health_system.db")
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for item in assets: archive.write(upload_dir / item["storage_key"], f"uploads/{item['storage_key']}")
    return manifest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--database", type=Path, default=BACKEND_DIR / "instance" / "health_system.db")
    parser.add_argument("--upload-dir", type=Path, default=BACKEND_DIR / "uploads"); parser.add_argument("--output", type=Path)
    args = parser.parse_args(); output = args.output or BACKEND_DIR / "instance" / f"healthdoc-recovery-v7-{datetime.now():%Y%m%d-%H%M%S}.zip"
    manifest = create_recovery_set(args.database, args.upload_dir, output)
    print(f"output={output.resolve()} assets={len(manifest['assets'])} database_sha256={manifest['database']['sha256']}")


if __name__ == "__main__": main()
