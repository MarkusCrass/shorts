# shorts — нарезка турнирных клипов для YouTube Shorts (Dota 2)

Конвейер: скачивание клипов через `yt-dlp` + нарезка вертикали **1080×1920 (9:16)**
через `ffmpeg`, с текстом-хуком на первых секундах, превью и готовыми
заголовком/описанием/тегами для загрузки.

## Что проверено на практике (важно прочитать)

| Путь | Результат проверки |
|---|---|
| Скачивание с серверов GitHub Actions | ❌ YouTube: **«Sign in to confirm you're not a bot»** — все 10 player-клиентов (tv, ios, web, android, android_vr, web_embedded…) получают `LOGIN_REQUIRED` с дата-центровых IP. Нужны **cookies** (см. ниже) |
| Скачивание с серверов GitHub Actions | ❌ DLTV: **HTTP 503 / 403** (антибот блокирует дата-центры). Нужен тот же обход или прокси |
| Нарезка ffmpeg | ✅ проверено: `crop` и `blur` дают ровно 1080×1920, H.264 + AAC |
| Хук, превью, несколько сегментов из одного файла, метаданные | ✅ проверено на тестовом видео |
| Запуск в песочнице Arena | ❌ TLS-обрыв до YouTube/DLTV — только GitHub/PyPI |

Вывод: **без cookies YouTube видео не скачается ни на раннере, ни из облака.**
Дальше — два рабочих сценария.

## Сценарий A — свой компьютер (работает сразу, нужен ваш Chrome/Firefox)

```bash
pip install -r requirements.txt

# раз — cookies берутся прямо из браузера, где вы залогинены в YouTube
SHORTS_COOKIES_FROM_BROWSER=chrome python make_shorts.py

# или разово экспортировать cookies в файл
# (в браузере установите расширение "Get cookies.txt LOCALLY" → экспорт youtube.com)
python make_shorts.py            # подхватит ./cookies.txt автоматически
```

Windows: `set SHORTS_COOKIES_FROM_BROWSER=chrome && python make_shorts.py`
или просто `run.bat` (если `cookies.txt` лежит рядом).

DLTV локально качается как обычный сайт — антибот режет только дата-центры.
Если DLTV всё же ругается, переключите клипы 01/03/06 на YouTube-версии
(в `clips.json` уже стоят YouTube-ссылки BLAST).

## Сценарий B — GitHub Actions (автоматизация, требует cookies-секрет)

1. Экспортируйте `cookies.txt` из браузера, где залогинены в YouTube.
2. Закодируйте: `base64 -w 0 cookies.txt` (Linux) / `certutil -encode cookies.txt c.txt` (Windows).
3. GitHub → **Settings → Secrets and variables → Actions → New repository secret**:
   имя `YOUTUBE_COOKIES`, значение — base64-строка.
   (Для DLTV можно добавить второй секрет-куки `DLTV_COOKIES` — тот же формат.)
4. **Actions → Shorts → Run workflow**.

Workflow (`.github/workflows/shorts.yml`) делает:
- `make_shorts.py` качает клипы (только нужные отрезки для YouTube) и режет;
- публикует артефакт `shorts-<номер>` (mp4 + jpg + txt + uploads.json) на 7 дней;
- обновляет релиз [`shorts-latest`](../../releases/tag/shorts-latest) — оттуда удобно скачать;
- пишет отчёт в summary;
- при `publish_log=<номер issue>` копирует хвост лога в issue (issue #3 — для диагностики).

Параметры запуска: `only` (подстрока имени клипа), `mode` (`crop`/`blur`),
`no_hook`, `diagnose` (только проверить доступ к YouTube/DLTV на раннере).

> ⚠️ Не используйте личный аккаунт Google для cookies — заведите отдельный.
> Секреты в публичном репозитории видны только самому репозиторию, но cookies = вход в аккаунт.

## Сценарий C — локальная нарезка уже скачанных файлов (без сети вообще)

```bash
# положите видео в downloads/<имя_клипа>.mp4
python make_shorts.py --no-download
python make_shorts.py --no-download --only 04 --mode blur
```

## Что на выходе (`shorts/`)

| Файл | Что внутри |
|---|---|
| `<name>.mp4` | 1080×1920, H.264 + AAC, хук на первых 3.5 сек |
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
      "title": "Satanic УЛЬТРАКИЛЛ под фонтаном! #shorts",
      "url": "https://www.youtube.com/watch?v=odguY-kCJ8c",
      "start": "00:02:00",
      "duration": 20,
      "hook": "Ультракилл под фонтаном",
      "match": "PARIVISION vs Team Liquid, Blast Slam 9"
    }
  ]
}
```

Поля: `hook` (текст на первых секундах), `mode`, `match`, `description`, `tags`,
`segments` — несколько шортсов из одного ролика (скачается один раз):

```json
{
  "name": "05_liquid_dokonca_highlight",
  "url": "https://www.youtube.com/watch?v=1iSsp7unYAo",
  "segments": [
    {"name": "first_blood", "start": "00:00:40", "hook": "Фёрст блад"},
    {"name": "mid_fight", "start": "00:12:10", "hook": "Драка на миду", "mode": "blur"}
  ]
}
```

### Таймкоды — что уже сделано и что осталось

| Клип | Источник | start | Статус |
|---|---|---|---|
| 01 Satanic — ультракилл | YouTube `odguY-kCJ8c` (42:55) | 00:02:00 | ⚠️ заглушка |
| 02 NAVI vs OG — вайп | YouTube `BmI5EyBMeXY` (26:48) | 00:00:00 | старт верный, момент ~ в начале |
| 03 No[o]ne — RP на двоих | YouTube `odguY-kCJ8c` | 00:08:00 | ⚠️ заглушка |
| 04 Ws — соло | YouTube `a1K1eeMACdM` (36:16) | 00:05:00 | ⚠️ заглушка (подсказка: «WS is on a monster kill, 11,000 net worth and he just can't die») |
| 05 Liquid vs DO KONCA | YouTube `1iSsp7unYAo` (47:56) | 00:05:00 | ⚠️ заглушка |
| 06 PARIVISION — тимвайп | YouTube `odguY-kCJ8c` | 00:16:00 | ⚠️ заглушка |

Как поставить точный таймкод: откройте видео на YouTube, найдите момент,
правый клик по таймлайну → **«Копировать URL с указанием времени»**, из ссылки
возьмите значение `t=` (например `t=4m12s` → `00:04:12`) и впишите в `start`.
Клипы 01/03/06 используют один ролик — старты обязаны различаться.

## Управление

```bash
python make_shorts.py --list         # список клипов
python make_shorts.py --dry-run      # проверка конфига
python make_shorts.py --only 04      # один клип
python make_shorts.py --mode blur    # вся картинка на размытом фоне
python make_shorts.py --no-hook      # без текста
python make_shorts.py --keep-video   # не удалять исходники
python make_shorts.py --hook-position bottom --hook-seconds 5
```

Переменные окружения:

| Переменная | Зачем |
|---|---|
| `SHORTS_COOKIES_FROM_BROWSER` | `chrome`/`firefox`/`edge`/`brave` — cookies прямо из браузера (локально) |
| `YTDLP_COOKIES_FILE` | путь к `cookies.txt` (по умолчанию ищется `./cookies.txt`) |
| `YTDLP_PLAYER_CLIENTS` | свои player-клиенты, через запятую |
| `YTDLP_EXTRA_ARGS` | любые доп. флаги yt-dlp, например `--proxy socks5://127.0.0.1:1080` |
| `SHORTS_FONT` | путь к `.ttf` для хука (кириллица поддерживается) |

## Про авторские права

Это контент организаторов (BLAST, DLTV, BETBOOM, Dota 2 Rapier). Для публикации
добавьте свой комментарий/текст/озвучку и проверьте правила использования. Шортсы
без собственного вклада могут заблокировать по Content ID.
