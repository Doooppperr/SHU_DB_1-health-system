import base64
import json
import re
import unicodedata
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
    VALUE_ONLY_PATTERN = re.compile(r"^[<>≤≥≈~]?\s*[+-]?\d+(?:\.\d+)?(?:\s*[A-Za-z%/μµ0-9²]+)?$")

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
    def _coerce_cell_index(value):
        if isinstance(value, (list, tuple)) and value:
            return HuaweiOCRProvider._coerce_cell_index(value[0])
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
            if stripped.replace(".", "", 1).isdigit():
                as_float = float(stripped)
                if as_float.is_integer():
                    return int(as_float)
        return None

    @staticmethod
    def _extract_cells(node, collector):
        if isinstance(node, dict):
            keys = {k.lower(): k for k in node.keys()}
            row_key = keys.get("row") or keys.get("rows") or keys.get("row_index")
            col_key = keys.get("column") or keys.get("columns") or keys.get("col") or keys.get("column_index")
            text_key = keys.get("text") or keys.get("words") or keys.get("content") or keys.get("value")

            if row_key and col_key and text_key:
                row = node.get(row_key)
                col = node.get(col_key)
                text = node.get(text_key)
                row_index = HuaweiOCRProvider._coerce_cell_index(row)
                col_index = HuaweiOCRProvider._coerce_cell_index(col)
                if row_index is not None and col_index is not None and isinstance(text, str) and text.strip():
                    collector.append({"row": row_index, "col": col_index, "text": text.strip()})

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

        pipe_parts = [part.strip() for part in re.split(r"[|｜丨]", text) if part.strip()]
        if len(pipe_parts) >= 2:
            return pipe_parts[0], pipe_parts[1]

        code_row_match = re.match(
            r"^(?:[A-Za-z]{0,3}\d{1,4}[A-Za-z0-9-]*\s+)(?P<label>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9()（）/%\-·_.]{0,40})\s+(?P<value>[+-]?\d+(?:\.\d+)?(?:\s*[A-Za-z%/μµ0-9²]+)?)\b",
            text,
        )
        if code_row_match:
            return code_row_match.group("label").strip(), code_row_match.group("value").strip()

        table_row_match = re.match(
            r"^(?P<label>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9()（）/%\-·_.]{0,40})\s+(?P<value>[+-]?\d+(?:\.\d+)?(?:\s*[A-Za-z%/μµ0-9²]+)?)\s+[<>]?\s*\d+(?:\.\d+)?\s*[-~至]\s*[<>]?\s*\d+(?:\.\d+)?",
            text,
        )
        if table_row_match:
            return table_row_match.group("label").strip(), table_row_match.group("value").strip()

        number_tail = re.match(r"^(.+?)\s+([+-]?\d+(?:\.\d+)?(?:\s*[A-Za-z%/μµ0-9²]+)?)$", text)
        if number_tail:
            return number_tail.group(1).strip(), number_tail.group(2).strip()

        return None, None

    @classmethod
    def _is_value_like_line(cls, text: str) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return False
        return cls.VALUE_ONLY_PATTERN.match(normalized) is not None

    @classmethod
    def _is_label_like_line(cls, text: str) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return False
        if len(normalized) > 40:
            return False
        if cls._is_value_like_line(normalized):
            return False
        if normalized in {"检验结果", "检测结果", "结果"}:
            return False
        return re.search(r"[A-Za-z\u4e00-\u9fff]", normalized) is not None

    @staticmethod
    def _normalize_cell_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", (text or "")).strip().lower()
        return normalized

    @staticmethod
    def _is_header_like(label: str, value: str) -> bool:
        combined = f"{label} {value}"
        normalized = HuaweiOCRProvider._normalize_cell_text(combined)
        header_tokens = ["项目", "指标", "结果", "参考", "范围", "单位", "检测值", "检查项"]
        hit_count = sum(1 for token in header_tokens if token in normalized)
        return hit_count >= 2

    @staticmethod
    def _detect_table_columns(row_map):
        label_tokens = ["项目", "指标", "名称", "检查项", "检测项"]
        value_tokens = ["结果", "数值", "检测值", "结果值", "值"]

        column_hits = {}
        for row_index in sorted(row_map.keys())[:4]:
            for cell in row_map[row_index]:
                text = HuaweiOCRProvider._normalize_cell_text(cell.get("text", ""))
                if not text:
                    continue
                stats = column_hits.setdefault(cell["col"], {"label": 0, "value": 0})
                if any(token in text for token in label_tokens):
                    stats["label"] += 1
                if any(token in text for token in value_tokens):
                    stats["value"] += 1

        if not column_hits:
            return 0, 1

        label_col = max(column_hits.items(), key=lambda item: (item[1]["label"], -item[0]))[0]
        value_col = max(column_hits.items(), key=lambda item: (item[1]["value"], -item[0]))[0]

        if label_col == value_col:
            value_col = 1 if label_col == 0 else label_col + 1

        return label_col, value_col

    def _extract_fields(self, response_data):
        rows = []
        self._extract_cells(response_data, rows)

        fields = []
        table_field_count = 0

        if rows:
            row_map = {}
            for item in rows:
                row_map.setdefault(item["row"], []).append(item)

            label_col, value_col = self._detect_table_columns(row_map)

            for row_index in sorted(row_map.keys()):
                cols = sorted(row_map[row_index], key=lambda x: x["col"])
                if len(cols) < 2:
                    continue

                col_text_map = {cell["col"]: cell["text"].strip() for cell in cols if cell.get("text", "").strip()}
                if not col_text_map:
                    continue

                label = col_text_map.get(label_col)
                if not label:
                    label = col_text_map.get(min(col_text_map.keys()))

                value = col_text_map.get(value_col)
                if not value:
                    fallback_cols = [col for col in sorted(col_text_map.keys()) if col != label_col]
                    for col in fallback_cols:
                        candidate = col_text_map.get(col)
                        if candidate:
                            value = candidate
                            break

                if label and value:
                    if self._is_header_like(label, value):
                        continue
                    fields.append({"label": label, "value": value, "source": "table"})
                    table_field_count += 1

        # If table cells are already reliable, skip full-text fallback to avoid
        # polluting with metadata and reference-range fragments.
        if table_field_count < 3:
            lines = []
            self._extract_text_lines(response_data, lines)

            normalized_lines = []
            for line in lines:
                for part in re.split(r"[\r\n]+", str(line)):
                    cleaned = part.strip()
                    if cleaned:
                        normalized_lines.append(cleaned)

            line_index = 0
            while line_index < len(normalized_lines):
                line = normalized_lines[line_index]
                label, value = self._split_line_to_pair(line)
                if label and value:
                    fields.append({"label": label, "value": value, "source": "text"})
                    line_index += 1
                    continue

                if line_index + 1 < len(normalized_lines):
                    next_line = normalized_lines[line_index + 1]
                    if self._is_label_like_line(line) and self._is_value_like_line(next_line):
                        fields.append({"label": line, "value": next_line, "source": "text"})
                        line_index += 2
                        continue

                line_index += 1

        deduped = {}
        for field in fields:
            key = f"{field['label']}::{field['value']}"
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = field
                continue
            if existing.get("source") != "table" and field.get("source") == "table":
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
    BRACKET_CONTENT_PATTERN = re.compile(r"\([^)]*\)|（[^）]*）|\[[^\]]*\]|【[^】]*】")
    UNIT_TOKEN_PATTERN = re.compile(r"(mmol/?l|μmol/?l|umol/?l|mg/?dl|u/?l|kg/?m2|kg/m²|mmhg|%)", re.IGNORECASE)
    RANGE_VALUE_PATTERN = re.compile(r"^\s*[+-]?\d+(?:\.\d+)?\s*[-~至]\s*[+-]?\d+(?:\.\d+)?\s*$")
    NUMERIC_FRAGMENT_PATTERN = re.compile(r"^[<>≤≥≈~+\-]?\s*\d+(?:\.\d+)?(?:\s*[-~至]\s*[<>≤≥≈~+\-]?\s*\d+(?:\.\d+)?)?\s*$")
    NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")
    NOISE_LABEL_KEYWORDS = {
        "报告编号",
        "姓名",
        "性别",
        "年龄",
        "检查日期",
        "登记号",
        "体检机构",
        "医生建议",
        "结论",
        "建议",
        "地址",
        "电话",
        "套餐",
        "分院",
        "门诊部",
        "结论摘要",
        "参考范围",
        "单位",
    }
    NOISE_VALUE_KEYWORDS = {
        "建议",
        "复查",
        "饮食",
        "作息",
        "报告",
    }

    @staticmethod
    def normalize_key(text: str) -> str:
        return "".join(ch.lower() for ch in (text or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return unicodedata.normalize("NFKC", str(text or "")).strip()

    def _strip_bracket_content(self, text: str) -> str:
        return self.BRACKET_CONTENT_PATTERN.sub("", self._normalize_text(text)).strip()

    @staticmethod
    def _strip_common_affixes(text: str) -> str:
        prefixes = ["检测项目", "项目名称", "检查项目", "指标名称"]
        suffixes = ["检测结果", "结果值", "检测值", "结果", "数值", "指标", "项目", "检查"]

        stripped = text.strip()
        for prefix in prefixes:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :].strip()

        for suffix in suffixes:
            if stripped.endswith(suffix):
                stripped = stripped[: -len(suffix)].strip()

        return stripped

    def _strip_unit_tokens(self, text: str) -> str:
        return self.UNIT_TOKEN_PATTERN.sub("", text or "").strip()

    def _label_variants(self, label: str):
        raw = self._normalize_text(label)
        no_bracket = self._strip_bracket_content(raw)
        no_affix = self._strip_common_affixes(no_bracket)
        no_unit = self._strip_unit_tokens(no_affix)

        variant_specs = [
            ("raw_exact", raw, 1.0),
            ("strip_bracket_exact", no_bracket, 0.97),
            ("strip_affix_exact", no_affix, 0.95),
            ("strip_unit_exact", no_unit, 0.93),
        ]

        deduped = []
        seen = set()
        for reason, variant_text, score in variant_specs:
            key = self.normalize_key(variant_text)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append((reason, key, score))
        return deduped

    def _is_noise_field(self, label: str, value: str):
        normalized_label = self._normalize_text(label)
        normalized_value = self._normalize_text(value)
        compact_label = self.normalize_key(normalized_label)

        if not compact_label:
            return "empty_label"

        if any(keyword in normalized_label for keyword in self.NOISE_LABEL_KEYWORDS):
            return "metadata_label"

        if compact_label.isdigit() or self.NUMERIC_FRAGMENT_PATTERN.match(normalized_label):
            return "numeric_fragment_label"

        if self.NUMERIC_FRAGMENT_PATTERN.match(normalized_value):
            if re.search(r"[A-Za-z\u4e00-\u9fff]", normalized_label) is None:
                return "numeric_fragment_value"

        value_compact = normalized_value.replace(" ", "")
        if self.RANGE_VALUE_PATTERN.match(value_compact) and len(compact_label) <= 2:
            return "reference_range_fragment"

        if len(normalized_value) >= 20 and not self.NUMBER_PATTERN.search(normalized_value):
            if any(keyword in normalized_value for keyword in self.NOISE_VALUE_KEYWORDS):
                return "summary_text"

        return None

    def _match_indicator(self, label: str, lookup):
        for reason, key, score in self._label_variants(label):
            indicator_dict = lookup.get(key)
            if indicator_dict is not None:
                return indicator_dict, reason, score, key

        normalized_label = self.normalize_key(self._strip_unit_tokens(self._strip_common_affixes(self._strip_bracket_content(label))))
        if len(normalized_label) < 2:
            return None

        best_match = None
        for key, indicator_dict in lookup.items():
            if len(key) < 2:
                continue
            if key in normalized_label or normalized_label in key:
                ratio = min(len(key), len(normalized_label)) / max(len(key), len(normalized_label))
                score = 0.72 + 0.2 * ratio
                if best_match is None or score > best_match[2]:
                    best_match = (indicator_dict, "contains_match", score, key)

        return best_match

    @staticmethod
    def _ensure_alias_list(aliases):
        if aliases is None:
            return []
        if isinstance(aliases, list):
            return aliases
        if isinstance(aliases, str):
            try:
                parsed = json.loads(aliases)
                if isinstance(parsed, list):
                    return parsed
            except ValueError:
                return []
        return []

    def build_lookup(self, indicator_dicts):
        lookup = {}
        for item in indicator_dicts:
            aliases = self._ensure_alias_list(item.aliases)
            candidates = [item.code, item.name, *aliases]
            for candidate in candidates:
                for _reason, normalized, _score in self._label_variants(candidate):
                    if normalized and normalized not in lookup:
                        lookup[normalized] = item
        return lookup

    def map_fields(self, fields, indicator_dicts):
        lookup = self.build_lookup(indicator_dicts)
        mapped_by_indicator = {}
        candidate_mappings = []
        unmatched = []
        filtered = []

        for field_index, field in enumerate(fields or []):
            label = str(field.get("label", "")).strip()
            value = str(field.get("value", "")).strip()

            if not label and not value:
                continue

            noise_reason = self._is_noise_field(label, value)
            if noise_reason:
                filtered.append({"label": label, "value": value, "reason": noise_reason})
                continue

            matched = self._match_indicator(label, lookup)
            if matched is None:
                unmatched.append({"label": label, "value": value})
                continue

            indicator_dict, reason, score, matched_key = matched
            normalized_value = str(value).strip()

            candidate_payload = {
                "field_index": field_index,
                "label": label,
                "value": normalized_value,
                "indicator_dict_id": indicator_dict.id,
                "indicator_code": indicator_dict.code,
                "indicator_name": indicator_dict.name,
                "reason": reason,
                "score": round(float(score), 4),
                "matched_key": matched_key,
            }
            candidate_mappings.append(candidate_payload)

            current_best = mapped_by_indicator.get(indicator_dict.id)
            if current_best is None or candidate_payload["score"] > current_best["score"]:
                mapped_by_indicator[indicator_dict.id] = {
                    "indicator_dict": indicator_dict,
                    "indicator_dict_id": indicator_dict.id,
                    "label": label,
                    "value": normalized_value,
                    "reason": reason,
                    "score": candidate_payload["score"],
                    "matched_key": matched_key,
                    "field_index": field_index,
                }

        mapped = list(mapped_by_indicator.values())
        mapped.sort(key=lambda item: (-item["score"], item["indicator_dict_id"]))
        candidate_mappings.sort(key=lambda item: (-item["score"], item["field_index"]))

        diagnostics = {
            "total_fields": len(fields or []),
            "filtered_count": len(filtered),
            "candidate_count": len(candidate_mappings),
            "mapped_unique_count": len(mapped),
            "unmatched_count": len(unmatched),
        }

        return {
            "mapped": mapped,
            "candidate_mappings": candidate_mappings,
            "unmatched": unmatched,
            "filtered": filtered,
            "diagnostics": diagnostics,
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
