"""Glue: file bytes -> provider -> checks -> Result."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from .checks import Issue, check_invoice, pdf_text
from .providers import Provider
from .schema import Invoice

SUPPORTED = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@dataclass
class Result:
    filename: str
    invoice: Invoice | None = None
    issues: list[Issue] = field(default_factory=list)
    error: str | None = None
    grounded: bool = False  # True when numbers were checked against the PDF text layer

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        return "needs review" if self.issues else "ok"


def mime_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return SUPPORTED.get(ext) or mimetypes.guess_type(filename)[0] or "application/octet-stream"


def process(filename: str, data: bytes, provider: Provider) -> Result:
    mime = mime_for(filename)
    if mime not in SUPPORTED.values():
        return Result(filename, error=f"unsupported file type: {Path(filename).suffix or 'none'}")
    try:
        invoice = provider.extract(data, mime)
    except Exception as exc:  # surface provider errors per file, don't kill the batch
        return Result(filename, error=f"{type(exc).__name__}: {exc}")
    text = pdf_text(data) if mime == "application/pdf" else ""
    return Result(filename, invoice=invoice, issues=check_invoice(invoice, text), grounded=bool(text.strip()))
