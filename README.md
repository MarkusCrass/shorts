# shorts — нарезка турнирных клипов для YouTube Shorts

Готовый конвейер: скачивание клипов (YouTube + DLTV) через `yt-dlp` и нарезка
вертикальных шортсов **1080×1920 (9:16), 15–20 сек** через `ffmpeg`.

## Что внутри

| Файл | Зачем |
|---|---|
| `clips.json` | Список клипов: ссылка, таймкод начала, длительность, заголовок |
| `make_shorts.py` | Скачивает и режет. Выход — папка `shorts/*.mp4` |

## Найденные клипы (все 5 + бонус)

1. **Satanic — ультракилл под фонтаном** (PARI vs Liquid, карта 3):
   https://dltv.org/videos/4727-parivision-vs-team-liquid-highlight-map-3-ultra-kill-by-satanic-under-the-fountain
2. **Вайп OG под базой NAVI** (NAVI vs OG, карта 1):
   https://dltv.org/videos/4728-natus-vincere-vs-og-highlight-map-1-team-wipe-for-og-under-navis-base
3. **No[o]ne — RP на двоих** (PARI vs Liquid, карта 1):
   https://dltv.org/videos/4724-parivision-vs-team-liquid-highlight-map-1-2-men-rp-by-noone-allows-parivision-to-win-the-fight
   (полный хайлайт серии: https://www.youtube.com/watch?v=odguY-kCJ8c)
4. **Ws — соло выигрывает драку** (Aurora vs PARI):
   https://www.youtube.com/watch?v=a1K1eeMACdM (36:16, таймкод уточнить вручную)
5. **FURIA vs Spirit — клатчи гранд-финала** (BETBOOM Highlights):
   https://www.youtube.com/watch?v=ZBoyAXokVtw (1:25:32, таймкод выбрать вручную)
6. Бонус: **Team wipe for Parivision** (PARI vs Liquid, карта 1):
   https://dltv.org/videos/4725-parivision-vs-team-liquid-highlight-map-1-team-wipe-for-parivision

Клипы 1–3 и 6 на DLTV уже короткие — режутся с `start=00:00:00`.
Для клипов 4–5 в `clips.json` стоят **заглушки `start=00:05:00`** — открой видео,
найди момент и впиши точный `start` в формате `HH:MM:SS`.

## Как запустить (на своём компьютере)

```bash
pip install yt-dlp imageio-ffmpeg
python3 make_shorts.py            # все клипы
python3 make_shorts.py --only 01  # только один клип
python3 make_shorts.py --mode blur  # вертикаль с размытым фоном вместо обрезки
```

> ⚠️ Сеть песочницы Arena не пускает на YouTube/DLTV (разрешён только
> GitHub/PyPI), поэтому скачивание из песочницы недоступно — запусти скрипт
> локально, где есть обычный интернет. Конвейер нарезки проверен в песочнице
> на тестовом видео: выход 1080×1920, 20 сек, H.264 + AAC.

## Про авторские права

Это контент организаторов (BLAST, DLTV, BETBOOM). Для публикации добавь свой
комментарий/текст/озвучку и проверь правила использования. Шортсы без
собственного вклада могут заблокировать по Content ID.
