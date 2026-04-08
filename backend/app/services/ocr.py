import base64
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import fitz
import requests
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.signer.signer import Signer


class OCRProvider(ABC):
    @abstractmethod
    def parse_report(self, file_path: str):
        raise NotImplementedError


class MockHuaweiOCRProvider(OCRProvider):
    def parse_report(self, file_path: str):
        fields = [
            {"label": "GLU", "value": "7.2"},
            {"label": "TC", "value": "5.8"},
            {"label": "ALT", "value": "46"},
            {"label": "UA", "value": "401"},
            {"label": "未知检查项", "value": "阴性"},
        ]

        return {
            "engine": "mock_huawei_ocr",
            "raw_text": "模拟OCR识别结果（用于第4轮闭环联调）",
            "fields": fields,
            "meta": {"file_path": file_path, "mode": "mock"},
        }


class HuaweiOCRProvider(OCRProvider):
    def __init__(self, endpoint: str, ak: str, sk: str, project_id: str, api_path: str, pdf_max_pages: int = 8):
        self.endpoint = self._normalize_endpoint(endpoint)
        self.ak = (ak or "").strip()
        self.sk = (sk or "").strip()
        self.project_id = (project_id or "").strip()
        self.api_path = (api_path or "/v2/{project_id}/ocr/general-table").strip()
        self.pdf_max_pages = max(1, int(pdf_max_pages or 8))
        self.timeout_seconds = 30

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        endpoint = (endpoint or "").strip()
        if not endpoint:
            return ""

        if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
            endpoint = f"https://{endpoint}"

        return endpoint.rstrip("/")

    def _resolve_resource_path(self) -> str:
        if not self.project_id:
            raise RuntimeError("Huawei OCR project_id is not configured")

        path = self.api_path.replace("{project_id}", self.project_id)
        if not path.startswith("/"):
            path = f"/{path}"
        return path

    def _sign_request(self, payload: str):
        if not self.endpoint or not self.ak or not self.sk:
            raise RuntimeError("Huawei OCR credentials are not configured")

        resource_path = self._resolve_resource_path()
        url = f"{self.endpoint}{resource_path}"
        parsed = urlparse(url)

        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

        sdk_request = SdkRequest(
            method="POST",
            schema=parsed.scheme,
            host=parsed.netloc,
            resource_path=parsed.path,
            query_params=query_params,
            header_params={
                "Content-Type": "application/json",
            },
            body=payload,
        )

        credentials = BasicCredentials(self.ak, self.sk, self.project_id)
        signer = Signer(credentials)
        signed_request = signer.sign(sdk_request)

        signed_url = f"{parsed.scheme}://{parsed.netloc}{signed_request.uri or parsed.path}"
        return signed_url, signed_request.header_params, signed_request.body

    @staticmethod
    def _extract_cells(node, collector):
        if isinstance(node, dict):
            keys = {k.lower(): k for k in node.keys()}
            row_key = keys.get("row") or keys.get("row_index")
            col_key = keys.get("column") or keys.get("col") or keys.get("column_index")
            text_key = keys.get("text") or keys.get("words") or keys.get("content") or keys.get("value")

            if row_key and col_key and text_key:
                row = node.get(row_key)
                col = node.get(col_key)
                text = node.get(text_key)
                if isinstance(row, int) and isinstance(col, int) and isinstance(text, str) and text.strip():
                    collector.append({"row": row, "col": col, "text": text.strip()})

            for value in node.values():
                HuaweiOCRProvider._extract_cells(value, collector)

        elif isinstance(node, list):
            for item in node:
                HuaweiOCRProvider._extract_cells(item, collector)

    @staticmethod
    def _extract_text_lines(node, collector):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key.lower() in {"words", "text", "content", "word"}:
                    text = value.strip()
                    if text:
                        collector.append(text)
                else:
                    HuaweiOCRProvider._extract_text_lines(value, collector)
        elif isinstance(node, list):
            for item in node:
                HuaweiOCRProvider._extract_text_lines(item, collector)

    @staticmethod
    def _split_line_to_pair(line: str):
        text = (line or "").strip()
        if not text:
            return None, None

        if "：" in text:
            parts = text.split("：", 1)
            return parts[0].strip(), parts[1].strip()

        if ":" in text:
            parts = text.split(":", 1)
            return parts[0].strip(), parts[1].strip()

        tab_parts = re.split(r"\t+", text)
        if len(tab_parts) >= 2:
            return tab_parts[0].strip(), tab_parts[1].strip()

        many_space_parts = re.split(r"\s{2,}", text)
        if len(many_space_parts) >= 2:
            return many_space_parts[0].strip(), many_space_parts[1].strip()

        number_tail = re.match(r"^(.+?)\s+([+-]?\d+(?:\.\d+)?(?:\s*[A-Za-z%/μµ0-9²]+)?)$", text)
        if number_tail:
            return number_tail.group(1).strip(), number_tail.group(2).strip()

        return None, None

    def _extract_fields(self, response_data):
        rows = []
        self._extract_cells(response_data, rows)

        fields = []

        if rows:
            row_map = {}
            for item in rows:
                row_map.setdefault(item["row"], []).append(item)

            for row_index in sorted(row_map.keys()):
                cols = sorted(row_map[row_index], key=lambda x: x["col"])
                if len(cols) < 2:
                    continue
                label = cols[0]["text"].strip()
                value = cols[1]["text"].strip()
                if label and value:
                    fields.append({"label": label, "value": value})

        lines = []
        self._extract_text_lines(response_data, lines)

        for line in lines:
            label, value = self._split_line_to_pair(line)
            if label and value:
                fields.append({"label": label, "value": value})

        deduped = {}
        for field in fields:
            key = f"{field['label']}::{field['value']}"
            deduped[key] = field

        return list(deduped.values())

    def _request_ocr(self, image_bytes: bytes):
        if not image_bytes:
            raise RuntimeError("uploaded file is empty")

        payload = json.dumps({"image": base64.b64encode(image_bytes).decode("utf-8")}, ensure_ascii=False)
        url, headers, body = self._sign_request(payload)

        try:
            response = requests.post(
                url,
                data=body,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"huawei ocr request error: {exc}") from exc

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"raw": response.text}
        else:
            try:
                response_data = json.loads(response.text)
            except ValueError:
                response_data = {"raw": response.text}

        if response.status_code >= 400:
            raise RuntimeError(
                f"huawei ocr request failed [{response.status_code}]: {json.dumps(response_data, ensure_ascii=False)}"
            )

        return response.status_code, response_data

    def _prepare_image_inputs(self, file_path: str):
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            # general-table expects image payload; convert PDF pages to PNG.
            try:
                doc = fitz.open(file_path)
            except Exception as exc:
                raise RuntimeError(f"failed to open pdf: {exc}") from exc

            if doc.page_count == 0:
                doc.close()
                raise RuntimeError("pdf file has no pages")

            image_inputs = []
            page_total = min(doc.page_count, self.pdf_max_pages)

            for page_index in range(page_total):
                page = doc.load_page(page_index)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_inputs.append((f"pdf_page_{page_index + 1}", pix.tobytes("png")))

            doc.close()
            return image_inputs

        with open(file_path, "rb") as f:
            return [("single_image", f.read())]

    def parse_report(self, file_path: str):
        try:
            image_inputs = self._prepare_image_inputs(file_path)
        except OSError as exc:
            raise RuntimeError(f"cannot read report file: {exc}") from exc
        except RuntimeError:
            raise

        all_fields = []
        page_results = []
        errors = []

        for page_name, image_bytes in image_inputs:
            try:
                status_code, response_data = self._request_ocr(image_bytes)
                page_fields = self._extract_fields(response_data)

                all_fields.extend(page_fields)
                page_results.append(
                    {
                        "page": page_name,
                        "status_code": status_code,
                        "field_count": len(page_fields),
                        "response": response_data,
                    }
                )
            except RuntimeError as exc:
                errors.append({"page": page_name, "error": str(exc)})

        if not page_results:
            error_message = errors[0]["error"] if errors else "unknown OCR error"
            raise RuntimeError(error_message)

        deduped_fields = {}
        for item in all_fields:
            deduped_fields[f"{item['label']}::{item['value']}"] = item

        fields = list(deduped_fields.values())
        raw_text = "\n".join([f"{item['label']}:{item['value']}" for item in fields])

        return {
            "engine": "huawei_ocr_general_table",
            "raw_text": raw_text,
            "fields": fields,
            "meta": {
                "mode": "live",
                "endpoint": self.endpoint,
                "api_path": self._resolve_resource_path(),
                "pages_processed": len(image_inputs),
                "pages_succeeded": len(page_results),
                "pages_failed": len(errors),
                "errors": errors[:5],
                "response_sample": page_results[0]["response"],
            },
        }


class OCRMappingService:
    @staticmethod
    def normalize_key(text: str) -> str:
        return "".join(ch.lower() for ch in (text or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

    def build_lookup(self, indicator_dicts):
        lookup = {}
        for item in indicator_dicts:
            candidates = [item.code, item.name, *(item.aliases or [])]
            for candidate in candidates:
                normalized = self.normalize_key(candidate)
                if normalized and normalized not in lookup:
                    lookup[normalized] = item
        return lookup

    def map_fields(self, fields, indicator_dicts):
        lookup = self.build_lookup(indicator_dicts)
        mapped = []
        unmatched = []

        for field in fields:
            label = field.get("label", "")
            value = field.get("value", "")
            normalized = self.normalize_key(label)

            indicator_dict = lookup.get(normalized)
            if indicator_dict is None:
                unmatched.append({"label": label, "value": value})
                continue

            mapped.append(
                {
                    "indicator_dict": indicator_dict,
                    "indicator_dict_id": indicator_dict.id,
                    "label": label,
                    "value": str(value).strip(),
                }
            )

        deduped = {}
        for item in mapped:
            deduped[item["indicator_dict_id"]] = item

        return {
            "mapped": list(deduped.values()),
            "unmatched": unmatched,
        }


mapping_service = OCRMappingService()


def get_ocr_provider(config):
    if config.get("OCR_USE_MOCK", True):
        return MockHuaweiOCRProvider()

    return HuaweiOCRProvider(
        endpoint=config.get("HUAWEI_OCR_ENDPOINT", ""),
        ak=config.get("HUAWEI_OCR_AK", ""),
        sk=config.get("HUAWEI_OCR_SK", ""),
        project_id=config.get("HUAWEI_PROJECT_ID", ""),
        api_path=config.get("OCR_API_PATH", "/v2/{project_id}/ocr/general-table"),
        pdf_max_pages=config.get("OCR_PDF_MAX_PAGES", 8),
    )
