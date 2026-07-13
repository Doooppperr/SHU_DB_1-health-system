import os
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_storage, subdir="reports"):
        raise NotImplementedError

    @abstractmethod
    def get_url(self, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str, url_base: str = "/uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.url_base = url_base.rstrip("/") or "/uploads"

    def save(self, file_storage, subdir="reports"):
        filename = file_storage.filename or "upload.bin"
        extension = os.path.splitext(filename)[1].lower()
        safe_name = f"{uuid4().hex}{extension}"

        base_dir = self.base_dir.resolve()
        save_dir = (base_dir / subdir).resolve()
        try:
            save_dir.relative_to(base_dir)
        except ValueError:
            raise ValueError("storage subdirectory escapes the upload directory") from None
        save_dir.mkdir(parents=True, exist_ok=True)

        abs_path = save_dir / safe_name
        file_storage.save(abs_path)

        key = f"{subdir}/{safe_name}".replace("\\", "/")
        return {
            "key": key,
            "url": self.get_url(key),
            "abs_path": str(abs_path),
        }

    def get_url(self, key: str) -> str:
        return f"{self.url_base}/{key}".replace("//", "/")

    def delete(self, key: str) -> None:
        base_dir = self.base_dir.resolve()
        target = (base_dir / key).resolve()
        try:
            target.relative_to(base_dir)
        except ValueError:
            return
        if target.exists() and target.is_file():
            target.unlink()


def get_storage_backend(config):
    return LocalStorage(config["UPLOAD_DIR"], config.get("UPLOAD_URL_BASE", "/uploads"))
