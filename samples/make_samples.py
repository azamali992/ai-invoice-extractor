"""Generate the sample documents used in the demo, tests and eval.

All companies are fictional. Writes PDFs/PNGs plus expected.json (ground truth)
into this folder. Run:  python samples/make_samples.py
"""

from __future__ import annotations

import io
import json
import random
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
random.seed(7)


def money(v: float, symbol: str = "") -> str:
    return f"{symbol}{v:,.2f}"


def draw_invoice(path: Path, d: dict, style: str) -> None:
    size = letter if style == "us" else A4
    c = canvas.Canvas(str(path), pagesize=size)
    w, h = size
    sym = d["symbol"]

    if style == "us":
        c.setFillColor(colors.HexColor("#1F3A5F"))
        c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(20 * mm, h - 20 * mm, d["vendor_name"])
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, h - 27 * mm, d["vendor_address"])
        c.setFont("Helvetica-Bold", 26)
        c.drawRightString(w - 20 * mm, h - 22 * mm, "INVOICE")
        c.setFillColor(colors.black)
        y = h - 52 * mm
    else:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, h - 25 * mm, d["vendor_name"])
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, h - 31 * mm, d["vendor_address"])
        if d.get("vendor_tax_id"):
            c.drawString(20 * mm, h - 36 * mm, f"VAT Reg No: {d['vendor_tax_id']}")
        c.setFont("Helvetica-Bold", 14)
        c.drawRightString(w - 20 * mm, h - 25 * mm, "Tax Invoice")
        c.setStrokeColor(colors.grey)
        c.line(20 * mm, h - 40 * mm, w - 20 * mm, h - 40 * mm)
        y = h - 50 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "BILL TO")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y - 5 * mm, d["customer_name"])
    meta = [("Invoice No:", d["invoice_number"]), ("Date:", d["date_printed"])]
    if d.get("due_printed"):
        meta.append(("Due:", d["due_printed"]))
    for i, (k, v) in enumerate(meta):
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(w - 55 * mm, y - i * 5 * mm, k)
        c.setFont("Helvetica", 9)
        c.drawString(w - 52 * mm, y - i * 5 * mm, v)

    y -= 25 * mm
    cols = [20 * mm, 110 * mm, 135 * mm, w - 20 * mm]
    c.setFillColor(colors.HexColor("#EEF2F6"))
    c.rect(18 * mm, y - 2 * mm, w - 36 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols[0], y, "Description")
    c.drawRightString(cols[1] + 10 * mm, y, "Qty")
    c.drawRightString(cols[2] + 20 * mm, y, "Unit price")
    c.drawRightString(cols[3], y, "Amount")
    c.setFont("Helvetica", 9)
    for item in d["line_items"]:
        y -= 7 * mm
        c.drawString(cols[0], y, item["description"])
        c.drawRightString(cols[1] + 10 * mm, y, f"{item['quantity']:g}")
        c.drawRightString(cols[2] + 20 * mm, y, money(item["unit_price"]))
        c.drawRightString(cols[3], y, money(item["amount"]))

    y -= 12 * mm
    rows = [("Subtotal", d["subtotal"])]
    if d.get("discount"):
        rows.append(("Discount", -d["discount"]))
    rows.append((d["tax_label"], d["tax"]))
    if d.get("shipping"):
        rows.append(("Shipping", d["shipping"]))
    for label, value in rows:
        c.drawRightString(w - 50 * mm, y, label)
        c.drawRightString(w - 20 * mm, y, money(value, sym))
        y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 50 * mm, y - 1 * mm, f"Total ({d['currency']})")
    c.drawRightString(w - 20 * mm, y - 1 * mm, money(d["total"], sym))

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, 20 * mm, "Thank you for your business. Payment by bank transfer within the stated terms.")
    c.save()


def draw_receipt_png(path: Path, d: dict) -> None:
    buf = io.BytesIO()
    w, h = 80 * mm, 82 * mm
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFont("Courier-Bold", 11)
    c.drawCentredString(w / 2, h - 12 * mm, d["vendor_name"])
    c.setFont("Courier", 8)
    c.drawCentredString(w / 2, h - 17 * mm, d["vendor_address"])
    c.drawString(5 * mm, h - 26 * mm, f"Receipt #{d['invoice_number']}")
    c.drawString(5 * mm, h - 31 * mm, d["date_printed"])
    y = h - 40 * mm
    for item in d["line_items"]:
        c.drawString(5 * mm, y, f"{item['quantity']:g} {item['description']}")
        c.drawRightString(w - 5 * mm, y, money(item["amount"]))
        y -= 5 * mm
    y -= 3 * mm
    for label, value in [("SUBTOTAL", d["subtotal"]), (d["tax_label"], d["tax"]), ("TOTAL", d["total"])]:
        c.setFont("Courier-Bold" if label == "TOTAL" else "Courier", 9)
        c.drawString(5 * mm, y, label)
        c.drawRightString(w - 5 * mm, y, money(value, d["symbol"]))
        y -= 5 * mm
    c.save()

    page = fitz.open(stream=buf.getvalue(), filetype="pdf")[0]
    img = Image.open(io.BytesIO(page.get_pixmap(dpi=200).tobytes("png"))).convert("L")
    img = img.rotate(1.8, expand=True, fillcolor=245).filter(ImageFilter.GaussianBlur(0.6))
    noise = Image.effect_noise(img.size, 18)
    img = Image.blend(img, noise, 0.08)
    img.convert("RGB").save(path, format="PNG", optimize=True)


def scan_pdf(src: Path, dst: Path) -> None:
    """Rasterise a PDF so it has no text layer, like a scanner output."""
    doc = fitz.open(src)
    out = fitz.open()
    for page in doc:
        pix = page.get_pixmap(dpi=150, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).rotate(-0.8, fillcolor=255)
        jpg = io.BytesIO()
        img.save(jpg, format="JPEG", quality=70)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=jpg.getvalue())
    out.save(dst)


def items(rows):
    return [{"description": d, "quantity": q, "unit_price": p, "amount": round(q * p, 2)} for d, q, p in rows]


SAMPLES = {
    "01_us_saas_invoice.pdf": dict(
        style="us", vendor_name="Northwind Cloud Labs", vendor_address="410 Harbor Ave, Suite 300, Seattle, WA 98104",
        vendor_tax_id=None, customer_name="Bluegate Logistics LLC", invoice_number="NCL-2026-0412",
        date_printed="Sep 14, 2026", invoice_date="2026-09-14", due_printed="Oct 14, 2026", due_date="2026-10-14",
        currency="USD", symbol="$", tax_label="Sales tax (10.1%)",
        line_items=items([("Platform subscription - Team plan (Sep)", 1, 1200.00),
                          ("Additional seats", 8, 45.00), ("Onboarding workshop", 2, 350.00)]),
        discount=None, shipping=None,
    ),
    "02_uk_supplier_vat.pdf": dict(
        style="uk", vendor_name="Ashford & Pell Supplies Ltd", vendor_address="12 Mill Lane, Leeds LS1 4AB, United Kingdom",
        vendor_tax_id="GB 284 1193 07", customer_name="Kestrel Cafe Group", invoice_number="AP-77810",
        date_printed="03/09/2026", invoice_date="2026-09-03", due_printed="03/10/2026", due_date="2026-10-03",
        currency="GBP", symbol="£", tax_label="VAT 20%",
        line_items=items([("Compostable cups 12oz (case of 1000)", 6, 64.50), ("Coffee filters (box)", 12, 8.75),
                          ("Napkins 2-ply (case)", 4, 22.00)]),
        discount=25.00, shipping=None,
    ),
    "03_wrong_subtotal.pdf": dict(
        style="us", vendor_name="Ridgeway Print Co.", vendor_address="88 Foundry St, Austin, TX 78701",
        vendor_tax_id=None, customer_name="Oakline Realty", invoice_number="RP-10933",
        date_printed="Aug 29, 2026", invoice_date="2026-08-29", due_printed=None, due_date=None,
        currency="USD", symbol="$", tax_label="Tax (8.25%)",
        line_items=items([("Business cards, 500 qty", 4, 38.00), ("Yard signs 18x24", 10, 14.50),
                          ("Brochure tri-fold, 1000 qty", 1, 289.00)]),
        discount=None, shipping=35.00, wrong_subtotal=True,
    ),
    "05_scanned_invoice.pdf": dict(
        style="uk", vendor_name="Brightwater Electrical", vendor_address="5 Station Rd, Bristol BS1 6QF, United Kingdom",
        vendor_tax_id="GB 611 4402 19", customer_name="Harbourside Dental Practice", invoice_number="BWE-3381",
        date_printed="22/09/2026", invoice_date="2026-09-22", due_printed=None, due_date=None,
        currency="GBP", symbol="£", tax_label="VAT 20%",
        line_items=items([("Emergency call-out", 1, 95.00), ("Labour (hours)", 3.5, 48.00),
                          ("LED panel 600x600", 4, 31.20)]),
        discount=None, shipping=None, scanned=True,
    ),
}

RECEIPT = dict(
    vendor_name="CORNER GROCER", vendor_address="221 Elm St, Toronto ON", invoice_number="004417",
    date_printed="2026-09-30 18:42", invoice_date="2026-09-30", currency="CAD", symbol="$", tax_label="HST 13%",
    customer_name=None, vendor_tax_id=None, due_date=None,
    line_items=items([("Olive oil 1L", 1, 12.99), ("Basmati rice 2kg", 2, 6.49), ("Eggs dozen", 1, 4.79)]),
)


def finish_totals(d: dict, tax_rate: float) -> None:
    lines = round(sum(i["amount"] for i in d["line_items"]), 2)
    d["subtotal"] = lines
    taxable = lines - (d.get("discount") or 0)
    d["tax"] = round(taxable * tax_rate, 2)
    d["total"] = round(taxable + d["tax"] + (d.get("shipping") or 0), 2)


def main() -> None:
    rates = {"01": 0.101, "02": 0.20, "03": 0.0825, "05": 0.20}
    expected = {}
    for name, d in SAMPLES.items():
        finish_totals(d, rates[name[:2]])
        if d.get("wrong_subtotal"):
            # Printed subtotal is wrong by 90.00 (a typo-style error); the total follows the wrong subtotal.
            d["subtotal"] = round(d["subtotal"] + 90.00, 2)
            d["tax"] = round(d["subtotal"] * 0.0825, 2)
            d["total"] = round(d["subtotal"] + d["tax"] + d["shipping"], 2)
        target = OUT / name
        if d.get("scanned"):
            tmp = OUT / "_tmp.pdf"
            draw_invoice(tmp, d, d["style"])
            scan_pdf(tmp, target)
            tmp.unlink()
        else:
            draw_invoice(target, d, d["style"])
        expected[name] = {k: d.get(k) for k in (
            "vendor_name", "customer_name", "vendor_tax_id", "invoice_number", "invoice_date", "due_date",
            "currency", "subtotal", "tax", "shipping", "discount", "total")}
        expected[name]["line_items"] = d["line_items"]
        expected[name]["should_flag"] = bool(d.get("wrong_subtotal"))

    finish_totals(RECEIPT, 0.13)
    draw_receipt_png(OUT / "04_phone_receipt.png", RECEIPT)
    expected["04_phone_receipt.png"] = {k: RECEIPT.get(k) for k in (
        "vendor_name", "customer_name", "vendor_tax_id", "invoice_number", "invoice_date", "due_date",
        "currency", "subtotal", "tax", "total")} | {"shipping": None, "discount": None,
                                                    "line_items": [dict(i, unit_price=None) for i in RECEIPT["line_items"]],
                                                    "should_flag": False}

    (OUT / "expected.json").write_text(json.dumps(dict(sorted(expected.items())), indent=2))
    print("wrote", ", ".join(sorted(expected)))


if __name__ == "__main__":
    main()
