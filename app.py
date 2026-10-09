"""Streamlit demo: drop invoices in, get a checked spreadsheet out.

Run:  streamlit run app.py
Needs GEMINI_API_KEY (free) or ANTHROPIC_API_KEY in the environment or a .env file.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from extractor.export import invoices_frame, line_items_frame, to_csv, to_excel
from extractor.pipeline import SUPPORTED, process
from extractor.providers import available_providers, get_provider

SAMPLES_DIR = Path(__file__).parent / "samples"


def load_dotenv(path: Path = Path(__file__).parent / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()
st.set_page_config(page_title="Invoice to Spreadsheet", page_icon="📄", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      .status-ok {color:#1e7b4b; font-weight:600}
      .status-review {color:#a15c00; font-weight:600}
      .status-failed {color:#b42318; font-weight:600}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Invoice → Spreadsheet")
st.caption("Drop in invoices, receipts or scanned PDFs. AI reads them, every number gets checked, "
           "and anything that doesn't add up is flagged for review instead of guessed.")

providers = available_providers()
with st.sidebar:
    st.header("Settings")
    if providers:
        provider_name = st.selectbox("AI model", providers, format_func={"gemini": "Google Gemini",
                                                                          "claude": "Anthropic Claude"}.get)
    else:
        st.error("No API key found. Set GEMINI_API_KEY (free at aistudio.google.com/apikey) "
                 "or ANTHROPIC_API_KEY, then restart.")
        provider_name = None
    workers = st.slider("Files processed in parallel", 1, 8, 4)
    st.divider()
    st.markdown("**What gets checked**\n"
                "- quantity × unit price = line amount\n"
                "- line items add up to the subtotal\n"
                "- subtotal + tax + shipping − discount = total\n"
                "- totals and invoice number actually appear on the PDF\n"
                "- dates are valid and due date is after issue date")

uploads = st.file_uploader("Upload documents", type=[e.lstrip(".") for e in SUPPORTED], accept_multiple_files=True)
use_samples = st.button("Try with 5 sample documents", disabled=not provider_name)

files: list[tuple[str, bytes]] = []
if use_samples:
    files = [(p.name, p.read_bytes()) for p in sorted(SAMPLES_DIR.iterdir()) if p.suffix.lower() in SUPPORTED]
elif uploads:
    files = [(u.name, u.getvalue()) for u in uploads]

if files and provider_name:
    provider = get_provider(provider_name)
    progress = st.progress(0.0, text=f"Reading {len(files)} document(s)…")
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(process, name, data, provider) for name, data in files]
        for done, future in enumerate(futures, start=1):
            results.append(future.result())
            progress.progress(done / len(files), text=f"Processed {done} of {len(files)}")
    progress.empty()
    st.session_state["results"] = results

results = st.session_state.get("results")
if results:
    ok = sum(r.status == "ok" for r in results)
    review = sum(r.status == "needs review" for r in results)
    failed = sum(r.status == "failed" for r in results)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", len(results))
    c2.metric("Clean", ok)
    c3.metric("Need review", review)
    c4.metric("Failed", failed)

    st.subheader("Invoices")
    frame = invoices_frame(results)
    st.dataframe(frame, width="stretch", hide_index=True,
                 column_config={"issues": st.column_config.TextColumn(width="large")})

    d1, d2, _ = st.columns([1, 1, 4])
    d1.download_button("Download Excel", to_excel(results), "invoices.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    d2.download_button("Download CSV", to_csv(results), "invoices.csv", "text/csv")

    st.subheader("Details")
    for r in results:
        css = {"ok": "status-ok", "needs review": "status-review", "failed": "status-failed"}[r.status]
        with st.expander(f"{r.filename} — {r.status}", expanded=r.status != "ok"):
            st.markdown(f"<span class='{css}'>{r.status.upper()}</span>", unsafe_allow_html=True)
            if r.error:
                st.error(r.error)
                continue
            if not r.grounded:
                st.caption("Scanned or image file: arithmetic checks ran; text-layer cross-check not available.")
            for issue in r.issues:
                (st.error if issue.severity == "error" else st.warning)(issue.message)
            lines = line_items_frame([r]).drop(columns=["file", "invoice_number"])
            st.dataframe(lines, width="stretch", hide_index=True)
else:
    st.info("Upload documents or click **Try with 5 sample documents**. One of the samples has a "
            "subtotal that doesn't match its line items, so you can see a flag in action.")
