#!/usr/bin/env python3
"""
Step 1: Align TikTok watch history with SynoSysTest02 BBI sessions.
Extracts videos watched while the SynoSys sensor was actively recording,
and outputs a clean CSV tracking download status.
"""

import json
import csv
import calendar
from datetime import datetime
from pathlib import Path

# Paths
WORKSPACE = Path(__file__).parent.resolve()
TIKTOK_JSON_PATH = WORKSPACE / "user_data_tiktok.json"
BBI_CSV_PATH = Path("/Volumes/bz_2tb/synosys files/lina-s paper/data/SynoSys_27.02.2026-15.04.2026.csv/bbi-(enhanced).csv")
OUTPUT_CSV_PATH = WORKSPACE / "synosys_test2_aligned_videos.csv"

def load_synosys_intervals(bbi_csv_path, target_user="SynoSysTest02", max_gap_seconds=300):
    """
    Parses BBI csv to find continuous recording intervals (UTC in ms).
    Consecutive rows with gap <= max_gap_seconds belong to the same session.
    """
    print(f"Reading BBI intervals from {bbi_csv_path.name} for {target_user}...")
    intervals = []
    curr_start = None
    prev_time = None
    
    with open(bbi_csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        fname_idx = header.index("User First Name")
        time_ms_idx = header.index("Start Time (ms)")
        
        for row in reader:
            if row[fname_idx] == target_user:
                t_ms = int(row[time_ms_idx])
                if prev_time is None:
                    curr_start = t_ms
                    prev_time = t_ms
                else:
                    if (t_ms - prev_time) > (max_gap_seconds * 1000):
                        intervals.append((curr_start, prev_time))
                        curr_start = t_ms
                    prev_time = t_ms
                    
    if curr_start is not None and prev_time is not None:
        intervals.append((curr_start, prev_time))
        
    print(f"Found {len(intervals)} active recording sessions for {target_user}.")
    return intervals

def is_within_intervals(ts_ms, intervals):
    # Binary search or simple interval check (since intervals count is small ~29)
    for s, e in intervals:
        if s <= ts_ms <= e:
            return True
        if s > ts_ms:
            break
    return False

def main():
    if not BBI_CSV_PATH.exists():
        print(f"Error: BBI file not found at {BBI_CSV_PATH}")
        return

    intervals = load_synosys_intervals(BBI_CSV_PATH)

    print(f"Reading TikTok watch history from {TIKTOK_JSON_PATH.name}...")
    with open(TIKTOK_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    vlist = data.get("Your Activity", {}).get("Watch History", {}).get("VideoList", [])
    print(f"Total TikTok watch events: {len(vlist)}")

    # Align
    aligned_videos = {} # video_id -> row dict (deduplicating multiple views of same video)
    
    for item in vlist:
        d_str = item.get("Date", "")
        link = item.get("Link", "")
        if not d_str or not link:
            continue
            
        # Parse UTC time
        dt = datetime.strptime(d_str, "%Y-%m-%d %H:%M:%S")
        ts_ms = calendar.timegm(dt.utctimetuple()) * 1000
        
        if is_within_intervals(ts_ms, intervals):
            # Extract video ID
            video_id = ""
            if "/video/" in link:
                video_id = link.split("/video/")[1].strip("/").split("?")[0]
            else:
                video_id = link.rstrip("/").split("/")[-1]
                
            if video_id not in aligned_videos:
                aligned_videos[video_id] = {
                    "video_id": video_id,
                    "first_watch_date_utc": d_str,
                    "url": link,
                    "status": "pending",
                    "file_path": "",
                    "error_msg": ""
                }

    print(f"Aligned unique videos: {len(aligned_videos)}")

    # Write output CSV
    fieldnames = ["video_id", "first_watch_date_utc", "url", "status", "file_path", "error_msg"]
    with open(OUTPUT_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in aligned_videos.values():
            writer.writerow(row)

    print(f"Saved aligned video manifest to: {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    main()

