#!/usr/bin/env python3
"""
Convert downloaded TikTok audio-only slideshows (.m4a, .mp3) to full video (.mp4)
by fetching their image slides via gallery-dl and stitching them with ffmpeg.
"""

import csv
import json
import subprocess
import tempfile
import sys
from pathlib import Path
import requests

WORKSPACE = Path(__file__).parent.resolve()
DEFAULT_CSV = WORKSPACE / "synosys_test2_aligned_videos.csv"
DEFAULT_FOLDER = Path("/Volumes/bz_2tb/synosys files/lina-s paper/data/SynoSys_27.02.2026-15.04.2026.csv/tiktok_Oct13")
GALLERY_DL_BIN = "/Users/bulat/micromamba/envs/tiktok/bin/gallery-dl"
FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"


def load_manifest(csv_path):
    if not csv_path.exists():
        return {}, []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {r["video_id"]: r for r in reader}, reader.fieldnames


def save_manifest(csv_path, id_to_row, fieldnames):
    tmp_path = csv_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(id_to_row.values())
    tmp_path.replace(csv_path)


def convert_slideshow(audio_path, url, seconds_per_slide=3.0):
    video_id = audio_path.stem
    mp4_path = audio_path.with_suffix(".mp4")

    # Fetch slide image URLs via gallery-dl
    res = subprocess.run([GALLERY_DL_BIN, "-j", url], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"gallery-dl failed: {res.stderr.strip()[:100]}")

    try:
        data = json.loads(res.stdout)
    except Exception as e:
        raise RuntimeError(f"Failed to parse gallery-dl output: {e}")

    img_urls = [item[1] for item in data if len(item) > 1 and isinstance(item[1], str) and item[1].startswith("http")]
    if not img_urls:
        raise RuntimeError("No image slide URLs found")

    with tempfile.TemporaryDirectory() as tmpdir:
        valid_count = 0
        for u in img_urls:
            try:
                resp = requests.get(u, timeout=15)
                if resp.status_code == 200 and resp.content.startswith(b"\xff\xd8"):
                    p = Path(tmpdir) / f"slide_{valid_count:03d}.jpg"
                    p.write_bytes(resp.content)
                    valid_count += 1
            except Exception:
                continue

        if valid_count == 0:
            raise RuntimeError("No valid JPEG slide images downloaded")

        framerate = 1.0 / seconds_per_slide

        # Assemble with ffmpeg (re-encoding audio to AAC standard in MP4 container)
        cmd = [
            FFMPEG_BIN, "-y",
            "-framerate", str(framerate),
            "-i", str(Path(tmpdir) / "slide_%03d.jpg"),
            "-i", str(audio_path),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-r", "25",
            "-c:a", "aac",
            "-shortest",
            str(mp4_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {proc.stderr[-200:].strip()}")

    # Cleanup audio file if mp4 exists and is valid
    if mp4_path.exists() and mp4_path.stat().st_size > 1000:
        audio_path.unlink()
        return mp4_path

    raise RuntimeError("Generated MP4 file missing or empty")


def main():
    target_dir = DEFAULT_FOLDER
    if not target_dir.exists():
        print(f"Error: target folder not found: {target_dir}")
        sys.exit(1)

    # Collect both .m4a and .mp3 files (skipping macOS ._ resource forks)
    audio_files = sorted([
        f for f in target_dir.glob("*.*")
        if f.suffix.lower() in (".m4a", ".mp3") and not f.name.startswith("._")
    ])
    print(f"Found {len(audio_files)} audio slideshow files (.m4a/.mp3) to convert in {target_dir.name}")

    if not audio_files:
        print("Nothing to convert!")
        return

    id_to_row, fieldnames = load_manifest(DEFAULT_CSV)

    success_cnt = 0
    fail_cnt = 0

    for i, audio_file in enumerate(audio_files, 1):
        vid = audio_file.stem
        row = id_to_row.get(vid)
        url = row["url"] if row else f"https://www.tiktokv.com/share/video/{vid}/"

        print(f"[{i}/{len(audio_files)}] Converting {vid} ({audio_file.suffix})... ", end="", flush=True)

        try:
            mp4_path = convert_slideshow(audio_file, url)
            print("OK -> .mp4")
            success_cnt += 1
            if row:
                row["file_path"] = str(mp4_path)
                save_manifest(DEFAULT_CSV, id_to_row, fieldnames)
        except Exception as e:
            print(f"FAILED ({e})")
            fail_cnt += 1

    print(f"\nSlideshow Conversion Complete:")
    print(f"  Converted: {success_cnt}")
    print(f"  Failed:    {fail_cnt}")


if __name__ == "__main__":
    main()
