"""Deterministic checks on top of the LLM output.

The model reads the document; these checks decide whether a person needs to
look at it. Nothing here calls an LLM, so the checks are cheap, repeatable and
explainable to a client ("the line items add up to 1,240 but the subtotal says
1,420").
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .schema import Invoice

REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total"]
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass
class Issue:
    field: str
    severity: str  # "error" = numbers don't reconcile, "warning" = missing or unverifiable
    message: str


def _close(a: float, b: float) -> bool:
    # Rounding-level tolerance only: a few cents, or 0.01% on large amounts.
    return abs(a - b) <= max(0.05, 0.0001 * max(abs(a), abs(b)))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def pdf_text(data: bytes) -> str:
    """Text layer of a PDF. Empty string for scanned PDFs or non-PDF input."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""


def _numbers_in(text: str) -> list[float]:
    out = []
    for match in NUMBER_RE.findall(text):
        try:
            out.append(float(match.replace(",", "")))
        except ValueError:
            pass
    return out


def check_invoice(inv: Invoice, source_text: str = "", today: date | None = None) -> list[Issue]:
    today = today or date.today()
    issues: list[Issue] = []

    for name in REQUIRED_FIELDS:
        if getattr(inv, name) in (None, ""):
            issues.append(Issue(name, "warning", f"{name.replace('_', ' ')} not found on the document"))

    # Dates
    inv_date = _parse_date(inv.invoice_date)
    due = _parse_date(inv.due_date)
    if inv.invoice_date and not inv_date:
        issues.append(Issue("invoice_date", "warning", f"could not read date '{inv.invoice_date}'"))
    if inv_date and inv_date > today + timedelta(days=1):
        issues.append(Issue("invoice_date", "warning", f"invoice date {inv_date} is in the future"))
    if inv_date and due and due < inv_date:
        issues.append(Issue("due_date", "error", f"due date {due} is before invoice date {inv_date}"))

    # Line item arithmetic
    for i, item in enumerate(inv.line_items, start=1):
        if item.quantity is not None and item.unit_price is not None and item.amount is not None:
            expected = item.quantity * item.unit_price
            if not _close(expected, item.amount):
                issues.append(Issue(
                    f"line_items[{i}]", "error",
                    f"line {i}: {item.quantity:g} x {item.unit_price:,.2f} = {expected:,.2f}, "
                    f"but the line says {item.amount:,.2f}",
                ))

    amounts = [it.amount for it in inv.line_items if it.amount is not None]
    lines_sum = sum(amounts) if amounts else None
    tax = inv.tax or 0.0
    shipping = inv.shipping or 0.0
    discount = inv.discount or 0.0

    if lines_sum is not None and inv.subtotal is not None and not _close(lines_sum, inv.subtotal):
        issues.append(Issue(
            "subtotal", "error",
            f"line items add up to {lines_sum:,.2f} but the subtotal says {inv.subtotal:,.2f}",
        ))

    base = inv.subtotal if inv.subtotal is not None else lines_sum
    if base is not None and inv.total is not None:
        expected_total = base + tax + shipping - discount
        if not _close(expected_total, inv.total):
            issues.append(Issue(
                "total", "error",
                f"subtotal + tax + shipping - discount = {expected_total:,.2f}, "
                f"but the total says {inv.total:,.2f}",
            ))

    # Grounding: every key number should literally appear on a text-based PDF.
    # Catches the model "fixing" or inventing a value.
    if source_text:
        numbers = _numbers_in(source_text)
        for name in ("subtotal", "tax", "total"):
            value = getattr(inv, name)
            if value is not None and not any(abs(n - value) < 0.005 for n in numbers):
                issues.append(Issue(name, "warning", f"{name} {value:,.2f} does not appear on the document"))
        if inv.invoice_number:
            squashed = re.sub(r"\s+", "", source_text).lower()
            if re.sub(r"\s+", "", inv.invoice_number).lower() not in squashed:
                issues.append(Issue("invoice_number", "warning",
                                    f"invoice number '{inv.invoice_number}' does not appear on the document"))

    return issues
