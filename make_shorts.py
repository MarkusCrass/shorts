#!/usr/bin/env python3
"""Скачивание турнирных клипов и нарезка вертикальных шортсов 9:16.

Использование:
  python make_shorts.py                    # скачать и нарезать все клипы из clips.json
  python make_shorts.py --only 01          # только клипы, чьё имя содержит "01"
  python make_shorts.py --list             # показать список клипов и выйти
  python make_shorts.py --no-download      # резать уже скачанные файлы из ./downloads
  python make_shorts.py --mode blur        # вертикаль через размытый фон вместо обрезки
  python make_shorts.py --no-hook          # не рисовать текст-хук на первых секундах
  python make_shorts.py --keep-video       # не удалять скачанные исходники после нарезки
  python make_shorts.py --dry-run          # только проверить конфиг, без сети и ffmpeg

Требуется: yt-dlp, ffmpeg (или imageio-ffmpeg).
Выход:
  ./shorts/<name>.mp4      — 1080x1920, H.264 + AAC, готово к загрузке в YouTube Shorts
  ./shorts/<name>.jpg      — превью/кадр из хука
  ./shorts/<name>.txt      — заголовок + описание + теги для загрузки
  ./shorts/uploads.json    — всё то же в одном файле
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(ROOT, "downloads")
SHORTS = os.path.join(ROOT, "shorts")

PYTHON = sys.executable  # тот же интерпретатор, из которого запущен скрипт

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

FONT_CANDIDATES = [
    os.environ.get("SHORTS_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\impact.ttf",
]


# ---------------------------------------------------------------- утилиты

class JobError(RuntimeError):
    pass


PROGRESS_LINE = re.compile(r"^\s*\[download\]\s+\d|ETA|\bfrag\b.*%", re.I)


def run(cmd, capture=False, quiet=False):
    """Запустить команду.

    capture=True — вернуть весь вывод, не печатая.
    quiet=False  — печатать прогресс построчно (служебные строки yt-dlp скрываются),
    в случае ошибки в исключение попадает хвост вывода, а не безликая команда.
    """
    printable = " ".join(str(c) for c in cmd)
    print("+", printable[:300] + ("…" if len(printable) > 300 else ""))
    if capture:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace")
        if proc.returncode != 0:
            tail = "\n".join(proc.stdout.strip().splitlines()[-25:])
            raise JobError(f"код {proc.returncode}:\n{tail}")
        return proc.stdout

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", bufsize=1) as proc:
        tail = []
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            tail.append(line)
            del tail[:-40]
            if not quiet and not PROGRESS_LINE.search(line):
                print("   ", line[:300])
        code = proc.wait()
    if code != 0:
        detail = "\n".join(tail[-25:]) or "(вывод пуст)"
        raise JobError(f"код {code}:\n{detail}")
    return ""


def find_bin(name, py_fallback=None):
    """Найти бинарник: сначала в PATH, потом через python-пакет."""
    path = shutil.which(name)
    if path:
        return path
    if py_fallback:
        try:
            mod = __import__(py_fallback)
            return mod.get_ffmpeg_exe()
        except Exception:
            return None
    return None


FFMPEG = None
FFPROBE = None


def ffmpeg_bin():
    global FFMPEG
    if FFMPEG is None:
        FFMPEG = find_bin("ffmpeg", "imageio_ffmpeg")
        if not FFMPEG:
            raise JobError("ffmpeg не найден. Установи: pip install imageio-ffmpeg "
                           "(или поставь ffmpeg в систему)")
    return FFMPEG


def ffprobe_bin():
    global FFPROBE
    if FFPROBE is None:
        FFPROBE = find_bin("ffprobe")
    return FFPROBE


def parse_time(value, default=0.0):
    """'01:02:03.5' | '02:03' | 123.4 -> секунды."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if ":" not in text:
        return float(text)
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


def fmt_time(seconds):
    seconds = max(0.0, float(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{int(h):02d}:{int(m):02d}:{s:05.2f}"
    return f"{int(m):02d}:{s:05.2f}"


def media_duration(path):
    """Длительность файла в секундах (ffprobe, а если его нет — разбор вывода ffmpeg)."""
    probe = ffprobe_bin()
    if probe:
        try:
            out = run([probe, "-v", "error", "-show_entries", "format=duration",
                       "-of", "csv=p=0", path], capture=True)
            return float(out.strip().splitlines()[0])
        except Exception:
            pass
    try:
        p = subprocess.run([ffmpeg_bin(), "-i", path], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stdout)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return None


def find_font(explicit=""):
    for path in ([explicit] if explicit else []) + FONT_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return ""


def slug(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "short"


# ---------------------------------------------------------------- скачивание

def yt_dlp_args():
    """Дополнительные аргументы yt-dlp из окружения (например, прокси)."""
    extra = os.environ.get("YTDLP_EXTRA_ARGS", "").strip()
    return extra.split() if extra else []


def cookies_file():
    """cookies.txt из окружения, корня проекта или ~/.config/shorts."""
    for path in (os.environ.get("YTDLP_COOKIES_FILE"),
                 os.path.join(ROOT, "cookies.txt"),
                 os.path.expanduser("~/.config/shorts/cookies.txt")):
        if path and os.path.exists(path):
            return path
    return ""


def cookies_from_browser():
    """Браузер для автоматического экспорта cookies при локальном запуске.

    Пример: SHORTS_COOKIES_FROM_BROWSER=chrome  (или firefox, edge, brave, chromium…)
    """
    return os.environ.get("SHORTS_COOKIES_FROM_BROWSER", "").strip()


# Клиенты YouTube: часть из них не требует логина с «серых» IP дата-центров,
# где обычный веб-клиент получает «Sign in to confirm you're not a bot».
YT_PLAYER_CLIENTS = ["default", "tv", "ios", "mweb", "web_safari"]


def _yt_extra_args(url):
    """Браузерные cookies и/или перебор player-клиентов для YouTube."""
    extra = yt_dlp_args()
    browser = cookies_from_browser()
    if browser:
        extra = extra + ["--cookies-from-browser", browser]
    if not re.search(r"(?:youtube\.com|youtu\.be)/", url):
        return extra
    if cookies_file() or browser:
        return extra  # с cookies достаточно обычного клиента
    forced = os.environ.get("YTDLP_PLAYER_CLIENTS", "").strip()
    clients = forced.split(",") if forced else YT_PLAYER_CLIENTS[:1]
    if clients and clients[0]:
        extra = extra + ["--extractor-args", f"youtube:player_client={','.join(clients)}"]
    return extra


def download_section(url, out_template, start=None, end=None):
    """Скачать клип (или только нужный отрезок) через yt-dlp, через python -m yt_dlp."""
    cmd = [PYTHON, "-m", "yt_dlp",
           "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
           "--merge-output-format", "mp4",
           "--no-playlist",
           "--retries", "5", "--fragment-retries", "5",
           "--no-warnings",
           "-o", out_template]
    is_youtube = bool(re.search(r"(?:youtube\.com|youtu\.be)/", url))
    if start is not None and end is not None and is_youtube:
        # качаем только нужный кусок: в разы быстрее на часовых записях.
        # для generic-сайтов (DLTV и т.п.) --download-sections не поддерживается
        cmd += ["--download-sections", f"*{fmt_time(start)}-{fmt_time(end)}",
                "--force-keyframes-at-cuts"]
    cookie = cookies_file()
    if cookie:
        cmd += ["--cookies", cookie]
    cmd += _yt_extra_args(url)
    cmd.append(url)
    run(cmd)


def direct_media_candidates(page_url):
    """Вытащить прямые ссылки на видео/плейлисты из HTML страницы (для не-YouTube сайтов)."""
    req = urllib.request.Request(page_url, headers={"User-Agent": UA,
                                                    "Referer": page_url})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    found = []
    for pattern in (r'https?:\\?/\\?/[^"\'\s<>]+?\.m3u8[^"\'\s<>]*',
                    r'https?:\\?/\\?/[^"\'\s<>]+?\.mp4[^"\'\s<>]*',
                    r'(?:file|src)\s*[:=]\s*"(https?://[^"]+\.(?:m3u8|mp4)[^"]*)"'):
        for match in re.findall(pattern, html):
            url = match.replace("\\/", "/").replace("\\u0026", "&")
            if url not in found:
                found.append(url)
    return found


def download_direct(page_url, dst):
    """Запасной путь для сайтов без поддержки в yt-dlp: качаем прямой mp4/hls через ffmpeg."""
    candidates = direct_media_candidates(page_url)
    if not candidates:
        raise JobError("не нашёл прямую ссылку на видео в HTML страницы")
    errors = []
    for url in candidates[:4]:
        try:
            run([ffmpeg_bin(), "-y", "-v", "warning",
                 "-headers", f"Referer: {page_url}\r\nUser-Agent: {UA}\r\n",
                 "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc", dst])
            if os.path.exists(dst) and os.path.getsize(dst) > 1024:
                return
        except Exception as exc:  # noqa: BLE001 — пробуем следующий кандидат
            errors.append(str(exc))
    raise JobError("не удалось скачать напрямую:\n" + "\n".join(errors))


BOT_CHECK_MARKERS = ("confirm you’re not a bot", "confirm you're not a bot",
                     "Sign in to confirm", "Failed to extract any player response",
                     "HTTP Error 429", "Too Many Requests")


def _is_bot_check(exc):
    return any(marker in str(exc) for marker in BOT_CHECK_MARKERS)


def download(job, dst, section=None):
    """Скачать исходник. Возвращает True, если файл начинается с начала отрезка.

    Сначала yt-dlp, при неудаче — прямой разбор страницы (тогда файл целиком).
    """
    url = job["url"]
    base, ext = os.path.splitext(dst)
    template = base + ".%(ext)s"
    start, end = section if section else (None, None)
    is_youtube = bool(re.search(r"(?:youtube\.com|youtu\.be)/", url))
    trimmed = bool(section) and is_youtube
    try:
        download_section(url, template, start, end)
    except Exception as exc:  # noqa: BLE001 — пробуем запасной путь
        if _is_bot_check(exc) and is_youtube and not (
                cookies_file() or cookies_from_browser()):
            # антибот YouTube: перебираем player-клиенты, которые обходят проверку
            saved = os.environ.get("YTDLP_PLAYER_CLIENTS")
            try:
                for client in YT_PLAYER_CLIENTS[1:]:
                    print(f"    YouTube просит логин — пробую клиент '{client}'…")
                    os.environ["YTDLP_PLAYER_CLIENTS"] = client
                    try:
                        download_section(url, template, start, end)
                        break
                    except JobError as retry_exc:
                        exc = retry_exc
                else:
                    raise exc
            finally:
                if saved is None:
                    os.environ.pop("YTDLP_PLAYER_CLIENTS", None)
                else:
                    os.environ["YTDLP_PLAYER_CLIENTS"] = saved
        else:
            reason = str(exc).strip().splitlines()
            reason = reason[-1] if reason else "неизвестная ошибка"
            print(f"WARN: yt-dlp не справился: {reason[:300]}")
            print("      пробую прямую ссылку со страницы…")
            download_direct(url, dst)
    if not os.path.exists(dst):
        # yt-dlp мог сохранить в другой контейнер
        for candidate in os.listdir(os.path.dirname(dst) or "."):
            full = os.path.join(os.path.dirname(dst) or ".", candidate)
            if full.startswith(base + ".") and candidate != os.path.basename(dst):
                os.replace(full, dst)
                break
    if not os.path.exists(dst):
        raise JobError(f"файл не появился: {dst}")
    return trimmed


# ---------------------------------------------------------------- нарезка

def wrap_hook(text, max_chars=20):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\\n".join(lines[:3])


def drawtext_filter(hook, seconds, font, position="top"):
    """Фильтр drawtext с текстом-хуком и мягким появлением/уходом."""
    if not hook or not font:
        return ""
    text = wrap_hook(hook)
    escaped = (text.replace("\\", "\\\\").replace(":", r"\:")
               .replace("'", r"\'").replace("%", r"\%").replace(",", r"\,"))
    size = 64 if len(hook) <= 42 else 54
    y_expr = "h*0.07" if position == "top" else "h*0.80"
    fade_out = seconds - 0.35
    alpha = (f"if(lt(t,0.35),t/0.35,"
             f"if(gt(t,{fade_out}),max(0,({seconds}-t)/0.35),1))")
    return (
        f"drawtext=fontfile={font}:text='{escaped}':fontsize={size}:"
        f"fontcolor=white:borderw=7:bordercolor=black@0.9:"
        f"line_spacing=14:box=1:boxcolor=black@0.35:boxborderw=24:"
        f"x=(w-text_w)/2:y={y_expr}:alpha='{alpha}':"
        f"enable='lt(t,{seconds})'"
    )


def build_vf(mode, hook, hook_seconds, font, position):
    if mode == "blur":
        chain = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
                 "crop=1080:1920,gblur=sigma=40[bg];[b]scale=1080:-2[fg];"
                 "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    else:
        chain = "crop=ih*9/16:ih,scale=1080:1920,setsar=1"
    hook_filter = drawtext_filter(hook, hook_seconds, font, position)
    return f"{chain},{hook_filter}" if hook_filter else chain


def cut_vertical(src, dst, start, duration, mode="crop", hook="", hook_seconds=3.5,
                 font="", position="top", crf=20, preset="medium"):
    vf = build_vf(mode, hook, hook_seconds, font, position)
    run([ffmpeg_bin(), "-y", "-v", "warning",
         "-ss", fmt_time(start), "-i", src, "-t", str(duration),
         "-vf", vf,
         "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
         "-movflags", "+faststart", "-avoid_negative_ts", "make_zero",
         dst])


def make_thumbnail(video, dst, at=1.0):
    try:
        run([ffmpeg_bin(), "-y", "-v", "error", "-ss", fmt_time(at), "-i", video,
             "-frames:v", "1", "-q:v", "3", dst])
    except Exception as exc:  # noqa: BLE001 — превью не критично
        print(f"WARN: превью не сделано: {exc}")


def hashtags(tags, extra=""):
    """Собрать хэштеги без дублей (регистр не важен)."""
    seen, parts = set(), []
    candidates = list(tags) + [chunk for chunk in extra.split() if chunk]
    for tag in candidates:
        if not tag:
            continue
        cleaned = re.sub(r"[^\w\d]+", "", tag.lstrip("#"))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append("#" + cleaned)
    return " ".join(parts)


def write_metadata(entry, path, global_tags):
    title = entry["final_title"][:100]
    desc_parts = []
    if entry.get("description"):
        desc_parts.append(entry["description"].strip())
    if entry.get("match"):
        desc_parts.append(f"Матч: {entry['match']}")
    if entry.get("url"):
        desc_parts.append(f"Источник: {entry['url']}")
    tags = list(dict.fromkeys(list(entry.get("tags") or []) + list(global_tags or [])))
    desc_parts.append(hashtags(tags, "#shorts #dota2"))
    desc_parts.append("Материал организаторов турнира. Добавь свой комментарий/озвучку "
                      "перед публикацией, чтобы не словить Content ID.")
    description = "\n\n".join(p for p in desc_parts if p)
    text = (f"ЗАГОЛОВОК (до 100 символов, {len(title)}):\n{title}\n\n"
            f"ОПИСАНИЕ:\n{description}\n\n"
            f"ТЕГИ (через запятую):\n{', '.join(tags)}\n")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return {"file": entry["file"], "title": title, "description": description,
            "tags": tags, "source_url": entry.get("url", ""),
            "start": entry.get("start", ""), "duration": entry.get("duration")}


# ---------------------------------------------------------------- конфиг

def load_jobs(path):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    defaults = config.get("defaults", {})
    jobs = config["jobs"]
    for job in jobs:
        for key, value in defaults.items():
            job.setdefault(key, value)
    return jobs, config.get("tags", [])


def expand_segments(job):
    """Один ролик может дать несколько шортсов: segment -> отдельный файл."""
    segments = job.get("segments")
    if not segments:
        return [job]
    expanded = []
    for index, segment in enumerate(segments, start=1):
        item = dict(job)
        item.pop("segments", None)
        item.update({k: v for k, v in segment.items() if v is not None})
        suffix = segment.get("name") or f"{index:02d}"
        item["source_name"] = job["name"]   # исходник общий для всех сегментов
        item["name"] = f"{job['name']}_{suffix}"
        expanded.append(item)
    return expanded


def validate(jobs):
    problems = []
    for job in jobs:
        for field in ("name", "url"):
            if not job.get(field):
                problems.append(f"{job.get('name', '?')}: нет поля {field}")
        if "start" in job:
            try:
                parse_time(job["start"])
            except ValueError:
                problems.append(f"{job['name']}: плохой start={job['start']!r}")
        try:
            duration = float(job.get("duration", 20))
            if not 5 <= duration <= 60:
                problems.append(f"{job['name']}: duration={duration} — для Shorts "
                                f"рекомендуется 15–60 сек")
        except (TypeError, ValueError):
            problems.append(f"{job['name']}: duration должен быть числом")
    return problems


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Нарезка вертикальных шортсов 9:16")
    parser.add_argument("--only", default="", help="подстрока имени клипа для фильтра")
    parser.add_argument("--no-download", action="store_true", help="не качать, резать локальные файлы")
    parser.add_argument("--keep-video", action="store_true", help="не удалять исходник после нарезки")
    parser.add_argument("--mode", choices=["crop", "blur"], default=None,
                        help="crop — центр 9:16, blur — вписать целиком на размытом фоне")
    parser.add_argument("--no-hook", action="store_true", help="не рисовать текст-хук")
    parser.add_argument("--hook-position", choices=["top", "bottom"], default="top")
    parser.add_argument("--hook-seconds", type=float, default=None,
                        help="сколько секунд держать хук (по умолчанию 3.5 или из конфига)")
    parser.add_argument("--font", default="", help="путь к .ttf для хука")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--config", default=os.path.join(ROOT, "clips.json"))
    parser.add_argument("--outdir", default=SHORTS)
    parser.add_argument("--dry-run", action="store_true", help="только проверить конфиг")
    parser.add_argument("--list", action="store_true", help="показать клипы и выйти")
    args = parser.parse_args()

    jobs, global_tags = load_jobs(args.config)
    if args.only:
        jobs = [j for j in jobs if args.only in j["name"]]
    jobs = [item for job in jobs for item in expand_segments(job)]
    if not jobs:
        print("Нет клипов для обработки.")
        return 0

    problems = validate(jobs)
    for problem in problems:
        print("CONFIG:", problem)

    if args.list:
        for job in jobs:
            print(f"{job['name']:<32} {job.get('start', '00:00:00'):>9} "
                  f"{job.get('duration', 20):>4}с  {job.get('title', '')}")
        return 0
    if args.dry_run:
        print(f"OK: {len(jobs)} клип(ов), конфиг читается. Проблем: {len(problems)}")
        return 0 if not problems else 1

    font = "" if args.no_hook else find_font(args.font)
    if not args.no_hook and not font:
        print("WARN: шрифт не найден — хуки рисоваться не будут (--font / SHORTS_FONT)")

    os.makedirs(DOWNLOADS, exist_ok=True)
    os.makedirs(args.outdir, exist_ok=True)
    manifest, failed, reasons = [], [], {}
    # один исходник может резаться на несколько сегментов — удаляем только после последнего
    uses_left = {}
    for item in jobs:
        key = slug(item.get("source_name", item["name"]))
        uses_left[key] = uses_left.get(key, 0) + 1

    for job in jobs:
        name = job["name"]
        mode = args.mode or job.get("mode", "crop")
        duration = float(job.get("duration", 20))
        start = parse_time(job.get("start", "00:00:00"))
        hook = "" if args.no_hook else (job.get("hook") or "")
        hook_seconds = args.hook_seconds or float(job.get("hook_seconds", 3.5))
        source_name = job.get("source_name", name)
        src = os.path.join(DOWNLOADS, slug(source_name) + ".mp4")
        dst = os.path.join(args.outdir, slug(name) + ".mp4")
        print(f"\n=== {name} ({mode}, {fmt_time(start)} + {duration:g}с) ===")
        try:
            seek = start  # если скачан весь файл, режем по таймкоду
            if not args.no_download:
                # качаем чуть больше, чем нужно, чтобы был запас на точный seek
                trimmed = download(job, src, section=(max(0.0, start - 2),
                                                     start + duration + 2))
                if trimmed:
                    seek = 0  # файл уже начинается с начала отрезка
            if not os.path.exists(src):
                raise JobError(f"исходник не найден: {src} (запусти без --no-download)")

            source_duration = media_duration(src)
            if seek and source_duration and start >= source_duration:
                raise JobError(f"start={fmt_time(start)} больше длительности файла "
                               f"({fmt_time(source_duration)}) — проверь таймкод "
                               f"(при скачивании отрезка время считается от 0)")

            cut_vertical(src, dst, seek,
                         duration, mode=mode, hook=hook, hook_seconds=hook_seconds,
                         font=font, position=args.hook_position,
                         crf=args.crf, preset=args.preset)
            if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
                raise JobError("ffmpeg не создал выходной файл")

            result_duration = media_duration(dst)
            make_thumbnail(dst, os.path.splitext(dst)[0] + ".jpg")
            entry = dict(job)
            entry.update({"file": os.path.basename(dst), "start": fmt_time(start),
                          "duration": result_duration or duration,
                          "final_title": job.get("title") or name})
            meta = write_metadata(entry, os.path.splitext(dst)[0] + ".txt", global_tags)
            manifest.append(meta)
            print(f"OK: {dst} ({fmt_time(result_duration) if result_duration else '?'})")
            uses_left[slug(source_name)] = uses_left.get(slug(source_name), 1) - 1
            if (not args.keep_video and uses_left[slug(source_name)] <= 0
                    and os.path.exists(src)):
                os.remove(src)
        except Exception as exc:  # noqa: BLE001 — один упавший клип не должен ломать остальные
            failed.append(name)
            reasons[name] = str(exc)
            print(f"FAIL: {name}: {exc}", file=sys.stderr)

    if manifest:
        manifest_path = os.path.join(args.outdir, "uploads.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        print(f"\nМетаданные: {manifest_path}")

    print(f"\nГотово: {len(manifest)} шортс(ов) в {args.outdir}")
    if failed:
        print("\nНе получилось: " + ", ".join(failed), file=sys.stderr)
        joined = " ".join(reasons.values()).lower()
        if "not a bot" in joined or "sign in to confirm" in joined:
            print("\nПодсказка: YouTube требует вход в аккаунт. Сделайте ОДНО из двух:\n"
                  "  1) установите расширение \"Get cookies.txt LOCALLY\", залогиньтесь в YouTube,\n"
                  "     экспортируйте youtube.com и положите файл cookies.txt рядом с make_shorts.py;\n"
                  "  2) или запустите с браузером: SHORTS_COOKIES_FROM_BROWSER=chrome\n"
                  "     (Windows: set SHORTS_COOKIES_FROM_BROWSER=chrome)", file=sys.stderr)
        if "503" in joined or "403" in joined or "dltv" in joined:
            print("\nПодсказка: DLTV не отдаёт видео вашему провайдеру/сети. Берите\n"
                  "  YouTube-вариант клипа (ссылки BLAST уже стоят в clips.json).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
