"""Record a ~45 second demo video of the running app (for a Fiverr gig or a README).

Start the app first with a real API key, then run:
    streamlit run app.py &
    python scripts/record_demo.py --url http://localhost:8501 --out recordings/demo.mp4

Needs: pip install playwright && playwright install chromium, plus ffmpeg on PATH.
Everything shown in the video is a real extraction by the configured model.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = sorted(p for p in (ROOT / "samples").iterdir() if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"})


def record(url: str, out: Path, width: int = 1280, height: int = 720) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": width, "height": height},
                                  record_video_dir=tmp, record_video_size={"width": width, "height": height})
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_selector("text=Invoice → Spreadsheet")
        page.wait_for_timeout(2500)

        # Upload the sample documents through the real file picker.
        page.locator("input[type=file]").set_input_files([str(s) for s in SAMPLES])
        page.wait_for_selector("text=Need review", timeout=180_000)
        page.wait_for_timeout(3000)

        # Slow scroll through the results so each part is readable.
        for _ in range(6):
            page.mouse.wheel(0, 220)
            page.wait_for_timeout(900)
        flagged = page.locator("summary", has_text="needs review").first
        if flagged.count():
            flagged.scroll_into_view_if_needed()
            page.wait_for_timeout(3500)
        page.mouse.wheel(0, -4000)
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Download Excel").hover()
        page.wait_for_timeout(2500)

        video_path = Path(page.video.path())
        ctx.close()
        browser.close()

        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            "-crf", "23", str(out.with_suffix(".mp4"))], check=True)
            print(f"Wrote {out.with_suffix('.mp4')}")
        else:
            shutil.copy(video_path, out.with_suffix(".webm"))
            print(f"ffmpeg not found; wrote {out.with_suffix('.webm')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--out", type=Path, default=ROOT / "recordings" / "demo.mp4")
    args = ap.parse_args()
    record(args.url, args.out)
