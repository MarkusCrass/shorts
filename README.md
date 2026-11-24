# shorts — нарезка турнирных клипов для YouTube Shorts (Dota 2)

Конвейер: скачивание клипов через `yt-dlp` + нарезка вертикали **1080×1920 (9:16)**
через `ffmpeg`, с текстом-хуком на первых секундах, превью и готовыми
заголовком/описанием/тегами для загрузки.

## Вариант 1 — GitHub Actions (рекомендуется: скачивание идёт с серверов GitHub)

Песочницы/облака часто не пускают на YouTube и DLTV, а раннеры GitHub — пускают.
Поэтому основной путь такой:

1. Открой вкладку **Actions** в репозитории и включи Actions (если выключены).
2. Там же выбери workflow **Shorts** → **Run workflow**.
3. Через ~5–10 минут забери результат:
   - в **Releases** → тег [`shorts-latest`](../../releases/tag/shorts-latest) — mp4 + jpg-превью;
   - в артефактах запуска (`shorts-<номер>`) — mp4, jpg, txt с описаниями, `uploads.json`;
   - в summary запуска — список готовых шортсов.

Workflow: `.github/workflows/shorts.yml`. Параметры запуска: `only` (подстрока имени
клипа), `mode` (`crop`/`blur`), `no_hook` (без текста-хука).

> Если YouTube просит «подтвердите, что вы не робот», экспортируй cookies браузера
> в `cookies.txt` в корне репозитория (`yt-dlp --cookies-from-browser chrome --cookies cookies.txt`)
> и закоммить его в приватный репозиторий, либо удали `YTDLP_COOKIES_FILE` из workflow.

## Вариант 2 — локально

```bash
pip install -r requirements.txt      # yt-dlp + imageio-ffmpeg
python make_shorts.py                # все клипы из clips.json
python make_shorts.py --list         # показать список клипов
python make_shorts.py --only 01      # только клипы, в имени которых есть "01"
python make_shorts.py --mode blur    # вертикаль с размытым фоном вместо обрезки
python make_shorts.py --no-hook      # без текста-хука
python make_shorts.py --dry-run      # проверка конфига без сети и ffmpeg
```

Одним кликом: `run.sh` (Linux/macOS) или `run.bat` (Windows).

### Что на выходе (`shorts/`)

| Файл | Что внутри |
|---|---|
| `<name>.mp4` | 1080×1920, H.264 + AAC, хук на первых 3.5 сек, готово к Shorts |
| `<name>.jpg` | превью (кадр из хука) |
| `<name>.txt` | заголовок (≤100 симв.), описание, теги |
| `uploads.json` | те же метаданные для автозагрузки (например, через YouTube API) |

## `clips.json` — что резать

```json
{
  "defaults": {"duration": 20, "mode": "crop", "hook_seconds": 3.5},
  "tags": ["dota2", "shorts"],
  "jobs": [
    {
      "name": "01_satanic_ultrakill_fountain",
      "title": "Satanic УЛЬТРАКИЛЛ под фонтаном! PARIVISION vs Liquid #shorts",
      "url": "https://dltv.org/videos/4727-...",
      "start": "00:00:00",
      "duration": 20,
      "hook": "Ультракилл под фонтаном",
      "match": "PARIVISION vs Team Liquid, Blast Slam 9",
      "description": "Текст описания",
      "tags": ["parivision", "satanic"]
    }
  ]
}
```

Полезные поля:

- `mode` — `crop` (центр 9:16) или `blur` (вся картинка на размытом фоне);
- `hook` — короткий текст (2–4 слова) на первых секундах;
- `segments` — несколько шортсов из одного видео:

```json
{
  "name": "05_liquid_dokonca_highlight",
  "url": "https://www.youtube.com/watch?v=...",
  "duration": 20,
  "segments": [
    {"name": "first_blood", "start": "00:00:40", "hook": "Фёрст блад"},
    {"name": "mid_fight",   "start": "00:12:10", "hook": "Драка на миду", "mode": "blur"}
  ]
}
```

Скачивается один раз, режется на несколько файлов
(`05_liquid_dokonca_highlight_first_blood.mp4`, `..._mid_fight.mp4`).

### Про таймкоды

Клипы 1–3 и 6 на DLTV уже короткие — режутся с `00:00:00`.
У клипов 4–5 в конфиге стоят **заглушки `00:05:00`** — открой видео, найди момент
и впиши точный `start` в формате `HH:MM:SS`. Для 4-го момента подсказка из транскрипта:
«WS is on a monster kill, 11,000 net worth and he just can't die».

## Найденные клипы

1. **Satanic — ультракилл под фонтаном** (PARI vs Liquid, карта 3): https://dltv.org/videos/4727-parivision-vs-team-liquid-highlight-map-3-ultra-kill-by-satanic-under-the-fountain
2. **Вайп OG под базой NAVI** (NAVI vs OG, карта 1): https://dltv.org/videos/4728-natus-vincere-vs-og-highlight-map-1-team-wipe-for-og-under-navis-base
3. **No[o]ne — RP на двоих** (PARI vs Liquid, карта 1): https://dltv.org/videos/4724-parivision-vs-team-liquid-highlight-map-1-2-men-rp-by-noone-allows-parivision-to-win-the-fight
4. **Ws — соло выигрывает драку** (Aurora vs PARI): https://www.youtube.com/watch?v=a1K1eeMACdM (36:16)
5. **Liquid vs DO KONCA** — официальный хайлайт BLAST Slam IX: https://www.youtube.com/watch?v=1iSsp7unYAo (47:56)
6. **Team wipe for PARIVISION** (PARI vs Liquid, карта 1): https://dltv.org/videos/4725-parivision-vs-team-liquid-highlight-map-1-team-wipe-for-parivision

Ещё в запас: полный хайлайт PARIVISION vs Liquid — https://www.youtube.com/watch?v=odguY-kCJ8c (42:55).

> ⚠️ Важно: старый клип `ZBoyAXokVtw` («Furia vs Team Spirit — BLAST Rivals») оказался
> **Counter-Strike 2**, а не Dota 2. Он убран и заменён на Dota-хайлайт Liquid vs DO KONCA.

## Переменные окружения

| Переменная | Зачем |
|---|---|
| `YTDLP_COOKIES_FILE` | путь к `cookies.txt`, если YouTube требует вход |
| `SHORTS_FONT` | путь к `.ttf` для хука (кириллица поддерживается) |
| `YTDLP_EXTRA_ARGS` | доп. аргументы yt-dlp, например `--proxy socks5://127.0.0.1:1080` |

## Про авторские права

Это контент организаторов (BLAST, DLTV, BETBOOM, Dota 2 Rapier). Для публикации
добавь свой комментарий/текст/озвучку и проверь правила использования. Шортсы без
собственного вклада могут заблокировать по Content ID.
