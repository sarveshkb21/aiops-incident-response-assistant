"""
docs/screenshots/capture.py - Automated demo-evidence capture

Starts the Streamlit app headlessly, drives the three demo queries from the
capture guide (README.md in this folder), and produces:

  * docs/screenshots/raw/<name>.png        - clean screenshots
  * docs/screenshots/<name>.png            - annotated versions (red callouts,
                                             positioned from the live DOM)
  * docs/video/demo_<timestamp>.webm       - screen recording of the session
                                             (YouTube accepts .webm directly)

Dev-only dependencies (not in requirements.txt):
    pip install playwright && python -m playwright install chromium

Quota note: each query costs 2 Gemini calls on the free tier (20/day).
A full 3-query run = 6 calls. Queries are spaced 20s apart.

Usage (from the repo root):
    python docs/screenshots/capture.py                 # all 3 queries + video
    python docs/screenshots/capture.py --queries 1     # subset (pipeline test)
    python docs/screenshots/capture.py --no-video
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHOTS = os.path.join(REPO, "docs", "screenshots")
RAW = os.path.join(SHOTS, "raw")
VIDEO_DIR = os.path.join(REPO, "docs", "video")

# (screenshot file, query, [(target, label), ...])
# targets: "trace" = routing badge line, "sources" = Sources: line,
#          "honesty" = the "I don't have a specific runbook" paragraph
SPECS = {
    1: {
        "file": "01_routed_query_with_sources.png",
        "query": "How do I resolve OOMKilled pods in Kubernetes?",
        "marks": [("trace", "Router hands off to the domain specialist"),
                  ("sources", "Answer cited to the team's own runbook")],
    },
    2: {
        "file": "02_general_agent_honesty.png",
        "query": "Our office printer says PC LOAD LETTER, what now?",
        "marks": [("trace", "No specialist fits — General agent handles it"),
                  ("honesty", "Admits the gap instead of inventing a source")],
    },
    3: {
        "file": "03_new_domain_cicd.png",
        "query": "GitHub Actions pipeline stuck in queued for two hours, blocking a hotfix",
        "marks": [("trace", "New CI/CD domain — one registry entry, no core changes"),
                  ("sources", "Retrieves from the newly ingested runbooks")],
    },
}

VIEWPORT = {"width": 1280, "height": 860}
# Screenshots are taken at a very tall viewport so the routing badge, the full
# answer, and the Sources line all render on screen at once — no scrolling, so
# measured element coordinates map 1:1 onto the screenshot.
TALL = {"width": 1280, "height": 3200}


def wait_port(port, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def wait_answer(page, prev_msgs, timeout=150):
    """Wait until a new assistant message is fully rendered (no spinners)."""
    end = time.time() + timeout
    while time.time() < end:
        msgs = page.locator('[data-testid="stChatMessage"]').count()
        spin = page.locator('[data-testid="stSpinner"]').count()
        if msgs >= prev_msgs + 2 and spin == 0:
            time.sleep(2.5)  # let markdown/badge finish painting
            if page.locator('[data-testid="stSpinner"]').count() == 0:
                return True
        time.sleep(1)
    return False


def find_box(page, kind):
    """Bounding box (viewport coords) of an annotation target in the last message."""
    last = page.locator('[data-testid="stChatMessage"]').last
    try:
        if kind == "trace":
            loc = last.locator("p", has_text="Router").first
        elif kind == "sources":
            loc = last.locator("em", has_text="Sources:").first
        elif kind == "honesty":
            loc = last.locator("p", has_text="specific runbook").first
        else:
            return None
        loc.wait_for(state="visible", timeout=5000)
        return loc.bounding_box()
    except Exception:
        return None


def annotate(src, dst, marks, crop_bottom=None):
    im = Image.open(src).convert("RGB")
    if crop_bottom and crop_bottom < im.height:
        im = im.crop((0, 0, im.width, crop_bottom))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 17)
    for bb, label in marks:
        if not bb:
            print(f"    (annotation target not found for: {label})")
            continue
        x0, y0 = bb["x"] - 8, bb["y"] - 6
        x1, y1 = bb["x"] + bb["width"] + 8, bb["y"] + bb["height"] + 6
        d.rounded_rectangle([x0, y0, x1, y1], radius=8, outline=(239, 68, 68), width=3)
        tw = d.textlength(label, font=font)
        th = 26
        lx = min(max(x0, 8), im.width - tw - 20)
        ly = y0 - th - 10 if y0 - th - 10 > 4 else min(y1 + 10, im.height - th - 6)
        d.rounded_rectangle([lx - 8, ly - 4, lx + tw + 8, ly + th - 4],
                            radius=6, fill=(239, 68, 68))
        d.text((lx, ly - 2), label, font=font, fill=(255, 255, 255))
    im.save(dst)


def capture_tall(page, spec):
    """Resize to the tall viewport, measure, screenshot, crop, annotate."""
    page.set_viewport_size(TALL)
    time.sleep(2.5)  # relayout
    marks = [(find_box(page, kind), label) for kind, label in spec["marks"]]
    # Crop just below the last message — the chat input is pinned to the
    # bottom of the (tall) viewport, so anchoring on it would keep a void.
    crop = None
    try:
        last_bb = page.locator('[data-testid="stChatMessage"]').last.bounding_box()
        if last_bb:
            crop = int(last_bb["y"] + last_bb["height"] + 30)
    except Exception:
        pass
    raw_path = os.path.join(RAW, spec["file"])
    page.screenshot(path=raw_path)
    annotate(raw_path, os.path.join(SHOTS, spec["file"]), marks, crop)
    page.set_viewport_size(VIEWPORT)
    time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", nargs="+", type=int, default=[1, 2, 3],
                    help="which spec numbers to run (default: all)")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--dry", action="store_true",
                    help="no queries / no quota: validate tall-viewport "
                         "geometry by annotating the app title")
    ap.add_argument("--port", type=int, default=8501)
    args = ap.parse_args()

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    print("Starting Streamlit ...", flush=True)
    app = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.headless=true", f"--server.port={args.port}",
         "--browser.gatherUsageStats=false"],
        cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(args.port):
            print("ERROR: Streamlit did not come up.")
            return 1

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx_kwargs = {"viewport": VIEWPORT}
            if not args.no_video:
                ctx_kwargs["record_video_dir"] = VIDEO_DIR
                ctx_kwargs["record_video_size"] = VIEWPORT
            ctx = browser.new_context(**ctx_kwargs)
            page = ctx.new_page()
            page.goto(f"http://localhost:{args.port}")
            page.wait_for_selector('[data-testid="stChatInput"] textarea',
                                   timeout=60000)
            time.sleep(3)  # let the sidebar settle

            if args.dry:
                page.set_viewport_size(TALL)
                time.sleep(2.5)
                title_bb = page.locator("h1").first.bounding_box()
                input_bb = page.locator('[data-testid="stChatInput"]').bounding_box()
                crop = int(input_bb["y"] + input_bb["height"] + 28) if input_bb else None
                raw_path = os.path.join(RAW, "dry_test.png")
                page.screenshot(path=raw_path)
                annotate(raw_path, os.path.join(RAW, "dry_test_annotated.png"),
                         [(title_bb, "geometry check: title box")], crop)
                print(f"dry run: raw/dry_test_annotated.png "
                      f"(title={title_bb}, crop={crop})", flush=True)
                ctx.close()
                browser.close()
                return 0

            for i, n in enumerate(args.queries):
                spec = SPECS[n]
                print(f"[{n}] {spec['query'][:70]}", flush=True)
                prev = page.locator('[data-testid="stChatMessage"]').count()
                box = page.locator('[data-testid="stChatInput"] textarea')
                box.click()
                box.fill(spec["query"])
                box.press("Enter")
                ok = wait_answer(page, prev)
                if not ok:
                    print("    WARNING: answer did not complete in time "
                          "(quota? check the app output)", flush=True)
                if page.locator('[data-testid="stAlert"]').count():
                    print("    WARNING: the app showed an alert (likely the "
                          "free-tier quota) — screenshot will reflect it",
                          flush=True)
                # Slow scroll through the answer so the video is watchable
                page.mouse.move(660, 430)
                for _ in range(7):
                    page.mouse.wheel(0, 380)
                    time.sleep(1.1)
                capture_tall(page, spec)
                print(f"    saved {spec['file']}", flush=True)
                if i < len(args.queries) - 1:
                    time.sleep(20)  # free-tier pacing between queries

            time.sleep(2)
            video = page.video if not args.no_video else None
            ctx.close()
            if video:
                src = video.path()
                stamp = datetime.now().strftime("%Y%m%d_%H%M")
                dst = os.path.join(VIDEO_DIR, f"demo_{stamp}.webm")
                os.replace(src, dst)
                print(f"video: {dst}", flush=True)
            browser.close()
    finally:
        app.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
