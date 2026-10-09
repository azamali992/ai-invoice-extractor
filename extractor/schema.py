"""Data model for an extracted invoice.

Every field is Optional on purpose: the model should return null when a value
is not on the document, never invent one. Fields have no defaults because the
Gemini structured-output schema treats every property as required, and that is
what we want (explicit null beats a silently missing key).
"""

from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: Optional[str] = Field(description="Item or service description as written")
    quantity: Optional[float] = Field(description="Quantity, null if not shown")
    unit_price: Optional[float] = Field(description="Price per unit, null if not shown")
    amount: Optional[float] = Field(description="Line total as printed on the document")


class Invoice(BaseModel):
    document_type: Optional[str] = Field(description="invoice, receipt, credit_note, purchase_order or other")
    vendor_name: Optional[str] = Field(description="Company that issued the document")
    vendor_address: Optional[str] = Field(description="Issuer address on one line")
    vendor_tax_id: Optional[str] = Field(description="VAT / GST / NTN / EIN of the issuer if printed")
    customer_name: Optional[str] = Field(description="Bill-to company or person")
    invoice_number: Optional[str] = Field(description="Invoice or receipt number exactly as printed")
    invoice_date: Optional[str] = Field(description="Issue date in YYYY-MM-DD")
    due_date: Optional[str] = Field(description="Payment due date in YYYY-MM-DD, null if not printed")
    currency: Optional[str] = Field(description="ISO 4217 code, e.g. USD, EUR, GBP, PKR")
    subtotal: Optional[float] = Field(description="Amount before tax and shipping")
    tax: Optional[float] = Field(description="Total tax amount")
    shipping: Optional[float] = Field(description="Shipping or delivery charge, null if none")
    discount: Optional[float] = Field(description="Discount as a positive number, null if none")
    total: Optional[float] = Field(description="Grand total the customer must pay")
    line_items: list[LineItem] = Field(description="Every line item row, in order")


EXTRACTION_PROMPT = """You are extracting data from a business document (invoice, receipt or similar).

Rules:
- Copy values exactly as printed. Do not calculate, correct or guess anything.
- If a value is not on the document, return null for it.
- Dates must be YYYY-MM-DD. If the day/month order is ambiguous, use the document's country convention.
- Money values are plain numbers: no currency symbols, no thousands separators.
- Discounts are positive numbers.
- Include every line item row; skip subtotal/tax/total rows.
"""
