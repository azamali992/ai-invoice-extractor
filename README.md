# Invoice → Spreadsheet

Drop in invoices, receipts or scanned PDFs and get one Excel file back. An LLM reads the documents, then plain Python checks every number before anything reaches the sheet. If the line items don't add up to the subtotal, or the total isn't actually printed on the PDF, the row is flagged for a person instead of quietly passed through.

## What it does

- Reads text PDFs, scanned PDFs and phone photos (PNG, JPG, WebP). No separate OCR step, the model reads the page directly.
- Extracts vendor, invoice number, dates, currency, subtotal, tax, shipping, discount, total and every line item.
- Runs deterministic checks after extraction:
  - quantity × unit price = line amount
  - line items sum to the subtotal
  - subtotal + tax + shipping − discount = total
  - on text PDFs, the totals and invoice number must literally appear on the page (catches the model "fixing" or inventing a value)
  - dates parse, due date isn't before issue date, issue date isn't in the future
- Exports to Excel with two sheets (Invoices, Line items). Flagged cells are highlighted.

The checks are the point. An LLM on its own will sometimes return a clean-looking total that isn't on the document. Here that gets caught and shown, not trusted.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env        # put your key in .env
streamlit run app.py
```

You need one API key:

| Variable | Where to get it | Cost |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | free tier is enough to try it |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys | pay as you go |

Optional: `GEMINI_MODEL` (default `gemini-flash-latest`), `ANTHROPIC_MODEL` (default `claude-haiku-4-5`).

Click **Try with 5 sample documents** to see it work. One sample has a subtotal that is off by 90.00, so you'll see a flag.

## Batch mode

```bash
python cli.py path/to/folder -o invoices.xlsx --provider gemini
python cli.py samples/ -o out.xlsx --eval samples/expected.json   # also prints field accuracy
```

## Samples and tests

`samples/` has five fictional documents: a US SaaS invoice, a UK VAT invoice with a discount, an invoice with a wrong subtotal, a skewed phone photo of a receipt, and a scanned PDF with no text layer. `samples/expected.json` is the ground truth. Regenerate them with `python samples/make_samples.py`.

```bash
pytest -q
```

Tests don't need an API key. A stub provider returns known values so the checks, grounding and Excel export are tested on their own.

## Layout

```
extractor/
  schema.py      Pydantic model + extraction prompt
  providers.py   Gemini and Claude, both with structured output
  checks.py      the deterministic checks
  pipeline.py    file -> provider -> checks -> Result
  export.py      Excel / CSV
app.py           Streamlit UI
cli.py           batch mode + accuracy eval
```

## Adapting it

New document type (purchase orders, bank statements, delivery notes): add fields to `schema.py` and checks to `checks.py`. Output somewhere other than Excel (Google Sheets, Airtable, QuickBooks import CSV): add a function next to `to_excel` in `export.py`.

Built by [Azam Ali](https://github.com/azamali992). If you want this set up on your own documents, get in touch.
