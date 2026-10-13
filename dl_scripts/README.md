# TikTok Downloader & Converter Pipeline

Aligns TikTok watch history with physiological BBI sensor intervals, downloads videos, and converts photo slideshows to `.mp4`.

---

## Prerequisites

- **Required file:** `user_data_tiktok.json` (TikTok GDPR export) must be placed in this folder.
- **Python packages:**
  ```bash
  pip install yt-dlp gallery-dl requests
  ```
- **System tool:** `ffmpeg` (installed via brew or package manager).

---

## 1. Align Watch History

Filter videos down to timestamps when the sensor was actively recording:

```bash
python align_synosys_tiktok.py
```
*Outputs `synosys_test2_aligned_videos.csv`.*

---

## 2. Download Videos

Download videos to the target drive (state checkpoints live in the CSV):

```bash
python download_aligned_tiktok.py --workers 1 --delay 1.0 --limit 0
```
*(Keep `--workers 1` and `--delay 1.0` to avoid TikTok IP blocks).*

---

## 3. Convert Photo Slideshows to `.mp4`

Photo carousels download as `.m4a` or `.mp3`. Run this to fetch the images and stitch them into 1080x1920 `.mp4` videos:

```bash
python convert_m4a_to_mp4.py
```
