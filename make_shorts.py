#!/usr/bin/env python3
"""Скачивание турнирных клипов и нарезка вертикальных шортсов 9:16.

Использование:
  python make_shorts.py                 # скачать и нарезать все клипы из clips.json
  python make_shorts.py --only 01       # только клипы, чьё имя содержит "01"
  python make_shorts.py --no-download   # резать уже скачанные файлы из ./downloads
  python make_shorts.py --mode blur     # вертикаль через размытый фон вместо обрезки по центру

Требуется: yt-dlp, ffmpeg (или imageio-ffmpeg).
Выход: ./shorts/<name>.mp4 — 1080x1920, 15-20 сек, готово к загрузке в YouTube Shorts.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(ROOT, "downloads")
SHORTS = os.path.join(ROOT, "shorts")

PYTHON = sys.executable  # тот же интерпретатор, из которого запущен скрипт


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def download(url, out_template):
    # yt-dlp вызываем через python -m yt_dlp, чтобы не зависеть от наличия yt-dlp в PATH.
    run([PYTHON, "-m", "yt_dlp", "-f",
         "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
         "--merge-output-format", "mp4", "-o", out_template, url])


def cut_vertical(src, dst, start, duration, mode):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg не найден. Установи: pip install imageio-ffmpeg", file=sys.stderr)
        sys.exit(1)
    if mode == "blur":
        # Вписать картинку целиком + размытый фон по краям (не теряем края экрана).
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,gblur=sigma=40[bg];[b]scale=1080:-2[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2")
    else:
        # Обрезать центр 9:16 (стандарт для шортсов).
        vf = ("crop=ih*9/16:ih,scale=1080:1920")
    run([ffmpeg, "-y", "-ss", start, "-i", src, "-t", str(duration),
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", dst])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="подстрока имени клипа для фильтра")
    ap.add_argument("--no-download", action="store_true", help="не качать, резать локальные файлы")
    ap.add_argument("--mode", choices=["crop", "blur"], default="crop")
    ap.add_argument("--config", default=os.path.join(ROOT, "clips.json"))
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        jobs = json.load(f)["jobs"]
    if args.only:
        jobs = [j for j in jobs if args.only in j["name"]]
    if not jobs:
        print("Нет клипов для обработки.")
        return

    os.makedirs(DOWNLOADS, exist_ok=True)
    os.makedirs(SHORTS, exist_ok=True)

    for job in jobs:
        name = job["name"]
        src = os.path.join(DOWNLOADS, name + ".mp4")
        dst = os.path.join(SHORTS, name + ".mp4")
        print(f"\n=== {name} ===")
        if not args.no_download:
            download(job["url"], os.path.join(DOWNLOADS, name + ".%(ext)s"))
        if not os.path.exists(src):
            print(f"WARN: файл {src} не найден, пропускаю. Проверь скачивание вручную.")
            continue
        cut_vertical(src, dst, job.get("start", "00:00:00"), job.get("duration", 20), args.mode)
        print(f"OK: {dst}")

    print("\nГотово. Шортсы в папке:", SHORTS)


if __name__ == "__main__":
    main()
