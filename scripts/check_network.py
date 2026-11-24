#!/usr/bin/env python3
"""Быстрая диагностика сети раннера: что доступно, а что блокируется.

Пишет отчёт в $GITHUB_STEP_SUMMARY, если переменная задана.
"""
import os
import socket
import subprocess
import sys
import urllib.request

TARGETS = [
    "https://www.youtube.com/",
    "https://dltv.org/",
    "https://s3.dltv.org/",
    "https://i.ytimg.com/",
    "https://github.com/",
]


def check(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return f"OK {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {type(exc).__name__}: {str(exc)[:160]}"


def dns(host):
    try:
        infos = socket.getaddrinfo(host, 443)
        return ", ".join(sorted({i[4][0] for i in infos})[:3])
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {exc}"


YT_URL = "https://www.youtube.com/watch?v=a1K1eeMACdM"
YT_CLIENTS = ["tv", "web_safari", "ios", "mweb", "android", "web", "tv_embedded",
              "android_vr", "web_embedded", "default"]


def probe_yt_clients():
    """Какой player_client YouTube пускает с этого IP (для дата-центровых раннеров)."""
    results = []
    for client in YT_CLIENTS:
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--simulate",
               "--extractor-args", f"youtube:player_client={client}",
               "--print", "%(title).50s", YT_URL]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            results.append((client, "TIMEOUT"))
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            results.append((client, "OK: " + proc.stdout.strip().splitlines()[-1][:60]))
        else:
            tail = (proc.stderr or "").strip().splitlines()
            reason = tail[-1][:140] if tail else "нет вывода"
            for marker in ("Sign in to confirm", "not a bot", "429",
                           "Failed to extract any player response",
                           "Video unavailable", "Private video"):
                if marker in reason:
                    reason = marker
                    break
            results.append((client, "FAIL: " + reason))
    return results


def main():
    lines = ["| Хост | DNS | HTTP |", "|---|---|---|"]
    for url in TARGETS:
        host = url.split("//", 1)[1].strip("/")
        lines.append(f"| {host} | {dns(host)} | {check(url)} |")
    # что видит yt-dlp
    try:
        out = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                             capture_output=True, text=True).stdout.strip()
        lines.append(f"\nyt-dlp: {out}")
        probe = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--no-warnings", "--simulate",
             "--print", "%(title)s (%(duration)s c)", "https://dltv.org/videos/4727"],
            capture_output=True, text=True, timeout=60)
        lines.append(f"\nyt-dlp dltv: rc={probe.returncode}\n```\n"
                     f"{(probe.stdout + probe.stderr)[-1200:]}\n```")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"\nyt-dlp: FAIL {exc}")

    lines.append("\n| player_client | результат |")
    lines.append("|---|---|")
    for client, result in probe_yt_clients():
        lines.append(f"| {client} | {result} |")

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Диагностика сети\n" + report + "\n")


if __name__ == "__main__":
    main()
