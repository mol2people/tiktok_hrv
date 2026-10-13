#!/usr/bin/env python3
"""
Multi-worker TikTok Downloader with live progress and thread-safe manifest updates.
Usage:
  python download_aligned_tiktok.py [--workers 3] [--limit 50] [--random]
"""

import argparse
import csv
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
import yt_dlp

# Defaults
WORKSPACE = Path(__file__).parent.resolve()
DEFAULT_CSV = WORKSPACE / "synosys_test2_aligned_videos.csv"
DEFAULT_DEST = Path("/Volumes/bz_2tb/synosys files/lina-s paper/data/SynoSys_27.02.2026-15.04.2026.csv/tiktok_Oct13")

csv_lock = Lock()


def parse_args():
    parser = argparse.ArgumentParser(description="Download aligned TikTok videos with concurrent workers.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to manifest CSV")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Destination directory for downloads")
    parser.add_argument("--workers", type=int, default=3, help="Number of concurrent workers (recommended: 2-4)")
    parser.add_argument("--limit", type=int, default=20, help="Number of videos to process (0 = all pending)")
    parser.add_argument("--random", action="store_true", help="Sample randomly from pending videos")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between starting requests per worker")
    return parser.parse_args()


def load_manifest(csv_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def save_manifest(csv_path, rows, fieldnames):
    with csv_lock:
        tmp_path = csv_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp_path.replace(csv_path)


def download_single_video(url, output_template):
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 2,
        "socket_timeout": 15,
        "retries": 2,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def process_video_task(row, output_template, csv_path, rows, fieldnames, progress_info):
    vid = row["video_id"]
    url = row["url"]

    try:
        filename = download_single_video(url, output_template)
        row["status"] = "downloaded"
        row["file_path"] = filename
        row["error_msg"] = ""
        status_msg = "OK"
        success = True
    except Exception as e:
        err_str = str(e).strip().replace("\n", " ")
        if len(err_str) > 80:
            err_str = err_str[:77] + "..."
        row["status"] = "failed"
        row["error_msg"] = err_str
        status_msg = f"FAILED ({err_str})"
        success = False

    # Checkpoint
    save_manifest(csv_path, rows, fieldnames)

    with csv_lock:
        progress_info["completed"] += 1
        cur = progress_info["completed"]
        total = progress_info["total"]
        print(f"[{cur}/{total}] {vid} -> {status_msg}")

    return success


def main():
    args = parse_args()

    if not args.csv.exists():
        print(f"Error: CSV manifest not found: {args.csv}")
        sys.exit(1)

    args.dest.mkdir(parents=True, exist_ok=True)

    rows, fieldnames = load_manifest(args.csv)
    total_in_manifest = len(rows)

    pending_rows = [r for r in rows if r.get("status") in ("pending", "")]

    if not pending_rows:
        print("No pending videos found in manifest!")
        return

    print(f"Loaded manifest: {total_in_manifest} total videos ({len(pending_rows)} pending).")
    print(f"Workers: {args.workers} | Destination: {args.dest}")

    if args.random:
        batch = random.sample(pending_rows, min(args.limit, len(pending_rows)))
    else:
        limit = args.limit if args.limit > 0 else len(pending_rows)
        batch = pending_rows[:limit]

    print(f"Starting batch of {len(batch)} videos with {args.workers} concurrent workers...\n")

    output_template = str(args.dest / "%(id)s.%(ext)s")
    progress_info = {"completed": 0, "total": len(batch)}

    start_time = time.time()
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for row in batch:
            f = executor.submit(
                process_video_task,
                row,
                output_template,
                args.csv,
                rows,
                fieldnames,
                progress_info,
            )
            futures.append(f)
            if args.delay > 0:
                time.sleep(args.delay)

        for future in as_completed(futures):
            if future.result():
                success_count += 1
            else:
                fail_count += 1

    elapsed = time.time() - start_time
    rate = len(batch) / elapsed if elapsed > 0 else 0

    print(f"\nBatch Complete in {elapsed:.1f}s ({rate:.2f} videos/sec):")
    print(f"  Downloaded: {success_count}")
    print(f"  Failed:     {fail_count}")
    print(f"  Manifest:   {args.csv}")


if __name__ == "__main__":
    main()
