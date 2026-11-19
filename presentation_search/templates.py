"""Private, owner-scoped template uploads, separate from the searchable library."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

MAX_TEMPLATE_BYTES = 16 * 1024 * 1024
MAX_TEMPLATE_BASE64 = ((MAX_TEMPLATE_BYTES + 2) // 3) * 4


class TemplateStore:
    def __init__(self, root: Path):
        self.root = root

    def create(self, owner: str, file_name: str, content_base64: str) -> dict:
        suffix = Path(file_name).suffix.lower()
        if (suffix not in {".pptx", ".potx"} or "/" in file_name or "\\" in file_name or ":" in file_name
                or any(ord(c) < 32 for c in file_name)):
            raise ValueError("Upload a .pptx or .potx template using its filename only.")
        if len(content_base64) > MAX_TEMPLATE_BASE64:
            raise ValueError("Template exceeds the 16 MiB upload limit.")
        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Template content must be valid base64 file bytes.") from None
        if not content or len(content) > MAX_TEMPLATE_BYTES:
            raise ValueError("Template must contain file bytes within the 16 MiB limit.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        template_id = uuid4().hex
        with TemporaryDirectory(dir=self.root) as temporary:
            folder = Path(temporary)
            template = folder / ("template" + suffix)
            template.write_bytes(content)
            template.chmod(0o600)
            from .templating import inspect_template

            try:
                details = inspect_template(template)
            except (ValueError, OSError):
                raise ValueError("The template is invalid or contains unsupported PowerPoint features.") from None
            metadata = {
                "templateId": template_id,
                "fileName": file_name,
                "slideWidth": details["slideWidth"],
                "slideHeight": details["slideHeight"],
                "layoutNames": details["layoutNames"],
                "warnings": details.get("warnings", []),
            }
            (folder / "metadata.json").write_text(json.dumps({
                "owner": owner, "sha256": hashlib.sha256(content).hexdigest(), **metadata,
            }, ensure_ascii=False), encoding="utf-8")
            folder.rename(self.root / template_id)
        return metadata

    def get(self, template_id: str, owner: str) -> tuple[dict, Path]:
        if not re.fullmatch("[0-9a-f]{32}", template_id):
            raise KeyError(template_id)
        folder = self.root / template_id
        try:
            record = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            if record.pop("owner") != owner:
                raise KeyError(template_id)
            digest = record.pop("sha256")
            path = folder / ("template" + Path(record["fileName"]).suffix.lower())
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise KeyError(template_id)
        except (OSError, ValueError):
            raise KeyError(template_id) from None
        return record, path
