from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from app.services.reports import cleanup_expired_reports


if __name__ == "__main__":
    app = create_app("development")
    with app.app_context():
        deleted = cleanup_expired_reports()
        print(f"deleted={len(deleted)}")
