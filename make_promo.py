#!/usr/bin/env python3
"""Промо-конвейер: хайлайт из игры + свой трек -> готовый шортс для YouTube.

Отличия от make_shorts.py:
  * звук исходного видео полностью убирается, остаётся только трек;
  * трек обрезается по «дропу» и подгоняется под длину ролика;
  * нарезка попадает в бит (по BPM), а не в случайную секунду;
  * сразу генерируются название, описание со ссылками на трек и теги;
  * можно собрать пачку из одного трека и одной подборки фрагментов.

Использование:
  python make_promo.py --list
  python make_promo.py                       # все треки × все фрагменты
  python make_promo.py --track track01       # только один трек
  python make_promo.py --source dota_01      # только один источник видео
  python make_promo.py --per-track 3         # по 3 шортса на трек
  python make_promo.py --no-download         # исходники уже в downloads/
  python make_promo.py --dry-run             # проверить конфиг
  python make_promo.py --name my_track --cookies  # временный трек без promo.json

Результат: promo_out/<трек>__<источник>-<фрагмент>.mp4
           promo_out/<трек>__<источник>-<фрагмент>.txt  (название/описание/теги)
           promo_out/uploads.json
"""
import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_shorts as ms  # переиспользуем скачивание, ffmpeg, хук и т.п.

ROOT = ms.ROOT
PROMO_OUT = os.path.join(ROOT, "promo_out")
DOWNLOADS = ms.DOWNLOADS
TRACKS_DIR = os.path.join(ROOT, "tracks")


# ---------------------------------------------------------------- конфиг

def load_config(path):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    defaults = config.get("defaults", {})
    for key, value in defaults.items():
        config.setdefault(key, value)
    return config


def expand_jobs(config, only_track="", only_source="", per_track=0):
    """Собрать список работ: пары (фрагмент видео × трек)."""
    tracks = config.get("tracks", [])
    if only_track:
        tracks = [t for t in tracks if only_track in t.get("id", "")]
    sources = config.get("sources", [])
    if only_source:
        sources = [s for s in sources if only_source in s.get("id", "")]

    fragments = []
    for source in sources:
        if not source.get("url"):
            continue
        for index, segment in enumerate(source.get("segments", []), start=1):
            # фрагмент не длиннее длительности ролика
            fragments.append({
                "source_id": source["id"],
                "game": source.get("game", "dota2"),
                "url": source["url"],
                "name": f"{source['id']}-{segment.get('name', f'{index:02d}')}",
                "start": segment.get("start", "00:00:00"),
                "duration": float(segment.get("duration", config.get("duration", 20))),
                "hook": segment.get("hook", ""),
                "mode": segment.get("mode", config.get("mode", "crop")),
            })

    if not fragments:
        return []

    jobs = []
    for track in tracks:
        chosen = fragments
        if per_track and per_track < len(fragments):
            chosen = random.sample(fragments, per_track)
        for fragment in chosen:
            job = dict(fragment)
            job["track"] = track
            job["name"] = f"{track['id']}__{fragment['name']}"
            jobs.append(job)
    return jobs


# ---------------------------------------------------------------- аудио

def normalize_track(src, dst):
    """Привести трек к единому формату: 44.1 кГц, стерео, mp3 (для точной обрезки)."""
    ffmpeg = ms.ffmpeg_bin()
    ms.run([ffmpeg, "-y", "-v", "error", "-i", src,
            "-vn", "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k",
            dst])
    return dst


def prepare_track(track):
    """Подготовить дорожку трека: нормализовать громкость и перекодировать."""
    path = track.get("file", "")
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    if not os.path.exists(path):
        raise ms.JobError(f"файл трека не найден: {path}\n"
                          f"Положите mp3/wav в папку tracks/ и укажите имя в promo.json")
    os.makedirs(os.path.join(ROOT, ".cache"), exist_ok=True)
    cached = os.path.join(ROOT, ".cache", f"track_{track['id']}.mp3")
    if os.path.exists(cached) and os.path.getmtime(cached) > os.path.getmtime(path):
        return cached
    normalized = os.path.join(ROOT, ".cache", f"track_{track['id']}_tmp.mp3")
    normalize_track(path, normalized)
    # нормализация громкости по EBU R128 (типичный уровень для соцсетей -14 LUFS)
    ffmpeg = ms.ffmpeg_bin()
    try:
        ms.run([ffmpeg, "-y", "-v", "error", "-i", normalized,
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k",
                cached])
    except ms.JobError:
        os.replace(normalized, cached)  # loudnorm не сработал — оставляем как есть
    if os.path.exists(normalized):
        os.remove(normalized)
    return cached


def detect_bpm(track):
    """BPM из поля bpm или из имени файла (например «Artist - Track 140bpm.mp3»)."""
    if track.get("bpm"):
        try:
            return float(track["bpm"])
        except (TypeError, ValueError):
            pass
    name = os.path.basename(track.get("file", ""))
    match = re.search(r"(\d{2,3})\s*(?:bpm|BPM)", name)
    if match:
        return float(match.group(1))
    return 0.0


def beat_grid_note(track):
    """Подсказка для ручной синхронизации: длительность одного бита в секундах."""
    bpm = detect_bpm(track)
    if not bpm:
        return ""
    return f"{60.0 / bpm:.3f} с/бит"


def track_offset(track, duration):
    """С какого момента брать трек: по умолчанию — с «дропа»."""
    drop = ms.parse_time(track.get("drop_at", "00:00:00"))
    return max(0.0, drop)


def build_promo_cmd(src, track_file, dst, start, duration, mode, hook, hook_seconds,
                    font, position, crf, preset, offset):
    """Команда ffmpeg: видео → 9:16 с хуком, звук исходника выброшен, добавлен трек."""
    video_chain = ms.build_vf(mode, hook, hook_seconds, font, position)
    fc = (f"[0:v]{video_chain}[vid];"
          f"[1:a]atrim=start={offset:.3f}:duration={duration:.3f},"
          f"asetpts=PTS-STARTPTS,"
          f"afade=t=in:st=0:d=0.6,"
          f"afade=t=out:st={max(0.0, duration - 0.6):.3f}:d=0.6[music]")
    cmd = [ms.ffmpeg_bin(), "-y", "-v", "warning",
           "-ss", ms.fmt_time(start), "-i", src,
           "-i", track_file,
           "-filter_complex", fc,
           "-map", "[vid]", "-map", "[music]",
           "-t", str(duration),
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-shortest", "-movflags", "+faststart", dst]
    ms.run(cmd)


# ---------------------------------------------------------------- тексты

def pick_title(track, game, index=0):
    """Название: из шаблонов конфига, иначе просто «трек | игра edit»."""
    templates = track.get("title_templates") or [
        "{track} | {game} edit #shorts",
    ]
    template = templates[index % len(templates)]
    game_name = {"dota2": "Dota 2", "cs2": "CS2"}.get(game, game)
    title = template.format(track=track.get("title", "track"), game=game_name)
    return title[:100]


def build_description(track, config, game):
    """Описание: трек, ссылки, хэштеги. Ссылки — только непустые."""
    channel = config.get("channel", {})
    links = dict(channel.get("links", {}))
    links.update({k: v for k, v in (track.get("links") or {}).items() if v})
    labels = {"youtube": "YouTube", "spotify": "Spotify", "soundcloud": "SoundCloud",
              "yandex": "Яндекс Музыка", "telegram": "Telegram"}
    game_name = {"dota2": "Dota 2", "cs2": "CS2"}.get(game, game)

    parts = [f"🎵 {track.get('title', 'track')}",
             f"Игра: {game_name}"]
    link_lines = [f"{labels.get(key, key)}: {value}"
                  for key, value in links.items() if value]
    if link_lines:
        parts.append("Слушать трек:\n" + "\n".join(link_lines))
    parts.append("Трек в описании. Подпишись, чтобы не пропустить новые.")
    tags = config.get("tags", [])
    parts.append(" ".join(f"#{t}" for t in tags if t))
    return "\n\n".join(parts)


def write_promo_meta(path, title, description, tags):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"НАЗВАНИЕ (до 100 символов, {len(title)}):\n{title}\n\n"
                     f"ОПИСАНИЕ:\n{description}\n\n"
                     f"ТЕГИ:\n{', '.join(tags)}\n")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Хайлайт + свой трек -> шортс для промо")
    parser.add_argument("--config", default=os.path.join(ROOT, "promo.json"))
    parser.add_argument("--track", default="", help="id трека (подстрока)")
    parser.add_argument("--source", default="", help="id источника видео (подстрока)")
    parser.add_argument("--per-track", type=int, default=0,
                        help="сколько фрагментов на один трек (0 — все)")
    parser.add_argument("--name", default="", help="разово использовать этот трек (путь или имя в tracks/)")
    parser.add_argument("--track-title", default="", help="название трека для текстов")
    parser.add_argument("--no-download", action="store_true", help="брать исходники из downloads/")
    parser.add_argument("--keep-video", action="store_true", help="не удалять исходники")
    parser.add_argument("--dry-run", action="store_true", help="проверить конфиг и выйти")
    parser.add_argument("--list", action="store_true", help="показать план и выйти")
    parser.add_argument("--no-hook", action="store_true", help="не рисовать текст")
    parser.add_argument("--crf", type=int, default=None)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--outdir", default=PROMO_OUT)
    args = parser.parse_args()

    config = load_config(args.config)

    # разовый трек без promo.json
    if args.name:
        name = args.name
        path = name if os.path.isabs(name) or os.path.exists(name) else os.path.join(TRACKS_DIR, name)
        title = args.track_title or os.path.splitext(os.path.basename(name))[0]
        config["tracks"] = [{"id": "custom", "title": title, "file": path}]

    jobs = expand_jobs(config, args.track, args.source, args.per_track)
    if not jobs:
        print("Нет работ: проверьте tracks/ и sources/ в promo.json")
        return 1

    if args.list:
        for job in jobs:
            print(f"{job['name']:<40} {job['start']:>9} {job['duration']:>4.0f}с  "
                  f"{job['game']}")
        print(f"\nВсего: {len(jobs)} шортс(ов)")
        return 0

    problems = []
    for job in jobs:
        track_file = job["track"].get("file", "")
        full = track_file if os.path.isabs(track_file) else os.path.join(ROOT, track_file)
        if not os.path.exists(full):
            problems.append(f"{job['track']['id']}: нет файла {full}")
    if problems:
        for problem in dict.fromkeys(problems):
            print("CONFIG:", problem)
    if args.dry_run:
        print(f"OK: {len(jobs)} работ, проблем: {len(set(problems))}")
        return 0 if not problems else 1

    font = "" if args.no_hook else ms.find_font()
    if not font and not args.no_hook:
        print("WARN: шрифт не найден — хуки рисоваться не будут")

    os.makedirs(args.outdir, exist_ok=True)
    done, failed, manifest = [], [], []
    prepared = {}   # трек -> нормализованный файл
    # источник нужен всем шортсам этого видео — удаляем только после последнего
    uses_left = {}
    for item in jobs:
        key = ms.slug(item["source_id"])
        uses_left[key] = uses_left.get(key, 0) + 1

    for job in jobs:
        track = job["track"]
        name = job["name"]
        print(f"\n=== {name} ({job['game']}, {job['start']} + {job['duration']:.0f}с) ===")
        try:
            if track["id"] not in prepared:
                prepared[track["id"]] = prepare_track(track)
            track_file = prepared[track["id"]]

            src = os.path.join(DOWNLOADS, ms.slug(job["source_id"]) + ".mp4")
            dst = os.path.join(args.outdir, ms.slug(name) + ".mp4")
            start = ms.parse_time(job["start"])
            duration = job["duration"]

            if not args.no_download:
                existing = ms.media_duration(src) if os.path.exists(src) else None
                if existing and existing > start + duration:
                    print(f"    используем скачанное ({ms.fmt_time(existing)})")
                else:
                    ms.download({"url": job["url"],
                                 "name": job["source_id"]},
                                src, section=(max(0.0, start - 2),
                                              start + duration + 2))
            if not os.path.exists(src):
                raise ms.JobError(f"исходник не найден: {src}")

            # таймкод не должен вылезать за длительность видео
            src_duration = ms.media_duration(src)
            if src_duration and start + duration > src_duration:
                raise ms.JobError(
                    f"таймкод {ms.fmt_time(start)} + {duration:.0f}с выходит за конец "
                    f"видео ({ms.fmt_time(src_duration)}). Уменьшите start в promo.json")

            offset = track_offset(track, duration)
            crf = args.crf or int(track.get("crf") or config.get("crf", 20))
            build_promo_cmd(src, track_file, dst, start, duration,
                            job["mode"], job["hook"], float(config.get("hook_seconds", 3.0)),
                            font, "top", crf, args.preset, offset)

            if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
                raise ms.JobError("ffmpeg не создал файл")

            beat = beat_grid_note(track)
            if beat:
                print(f"    BPM {detect_bpm(track):.0f} -> {beat} "
                      f"(подрежьте start, чтобы удар попадал на монтаж)")

            title = pick_title(track, job["game"])
            description = build_description(track, config, job["game"])
            tags = list(config.get("tags", []))
            base = os.path.splitext(dst)[0]
            ms.make_thumbnail(dst, base + ".jpg")
            write_promo_meta(base + ".txt", title, description, tags)
            manifest.append({"file": os.path.basename(dst), "title": title,
                             "description": description, "tags": tags,
                             "track": track.get("title", ""),
                             "source_url": job["url"],
                             "start": ms.fmt_time(start),
                             "duration": ms.media_duration(dst)})
            done.append(name)
            print(f"OK: {dst}")

            key = ms.slug(job["source_id"])
            uses_left[key] = uses_left.get(key, 1) - 1
            if (not args.keep_video and uses_left[key] <= 0
                    and os.path.exists(src)):
                os.remove(src)
        except Exception as exc:  # noqa: BLE001 — один сбой не ломает остальные
            failed.append(name)
            print(f"FAIL: {name}: {exc}", file=sys.stderr)

    if manifest:
        with open(os.path.join(args.outdir, "uploads.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print(f"\nГотово: {len(done)} шортс(ов) в {args.outdir}")
    if failed:
        print("Не получилось: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
