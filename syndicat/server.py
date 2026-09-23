# -*- coding: utf-8 -*-
"""Локальный HTTP-сервер платформы. Только стандартная библиотека."""

import datetime
import json
import mimetypes
import os
import posixpath
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from . import api

WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


_LOG_FILE = None


def open_log(path: str) -> None:
    """Журнал в файл - единственный способ что-то узнать при фоновом запуске.

    Под pythonw.exe в Windows консоли нет вовсе: sys.stdout равен None,
    и перенаправление оболочки до процесса не доходит. Поэтому сервер
    пишет журнал сам, в UTF-8, с отметками времени.
    """
    global _LOG_FILE
    try:
        _LOG_FILE = open(path, "a", encoding="utf-8", buffering=1)
    except OSError as exc:
        _LOG_FILE = None
        say(f"  журнал {path} недоступен: {exc}")


def say(text: str = "") -> None:
    """Вывод, безопасный при запуске без консоли и при любой кодовой странице."""
    stamped = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}" if text else ""
    if _LOG_FILE is not None:
        try:
            _LOG_FILE.write(stamped + "\n")
        except (ValueError, OSError):
            pass
    try:
        print(text, flush=True)
    except (AttributeError, ValueError, OSError, UnicodeEncodeError):
        pass


class SyndicatHandler(BaseHTTPRequestHandler):
    server_version = "Syndicat/1.0"

    # --- вспомогательное ----------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str, cache: bool = False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=60" if cache else "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def log_message(self, fmt, *args):   # компактный однострочный лог
        say(f"  {self.address_string()} {fmt % args}")

    # --- маршрутизация ------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/export/calibration.csv":
            from urllib.parse import parse_qs
            body = ("﻿" + api.calibration_csv(parse_qs(parsed.query or ""))).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition",
                             'attachment; filename="syndicat-calibration.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/api/"):
            data, error = api.dispatch(path, parsed.query)
            if error:
                self._json(error[0], dict(error=error[1], path=path))
            else:
                self._json(200, data)
            return

        self._static(path)

    do_HEAD = do_GET

    def _static(self, path: str):
        if path in ("/", ""):
            path = "/index.html"
        safe = posixpath.normpath(path).lstrip("/")
        if safe.startswith(".."):
            self._json(403, dict(error="путь вне корня"))
            return
        full = os.path.join(WEB_ROOT, safe)
        if not os.path.isfile(full):
            self._json(404, dict(error=f"файл не найден: /{safe}"))
            return
        ctype, _ = mimetypes.guess_type(full)
        if ctype and ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype = f"{ctype}; charset=utf-8"
        with open(full, "rb") as fh:
            self._send(200, fh.read(), ctype or "application/octet-stream", cache=True)


def local_address() -> str:
    """Адрес машины в локальной сети - для доступа с другого устройства."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 1))   # адрес из TEST-NET-1: пакет не уходит
        return probe.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        probe.close()


def serve(host: str = "127.0.0.1", port: int = 8777) -> None:
    if sys.stdout is not None:
        try:                      # кириллица в консоли Windows без кодовой страницы
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    try:
        httpd = ThreadingHTTPServer((host, port), SyndicatHandler)
    except OSError as exc:
        # Самая частая причина - платформа уже запущена и держит порт.
        say(f"  Порт {port} занят: {exc}")
        say(f"  Либо платформа уже работает - откройте http://127.0.0.1:{port}/,")
        say("  либо остановите её (stop.cmd в Windows) или возьмите другой порт:")
        say(f"  python3 -m syndicat --port {port + 1}")
        raise SystemExit(2)
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{shown}:{port}/"
    say("  СИНДИКАТ · локальная платформа")
    say(f"  панель:      {url}")
    say(f"  API:         {url}api/overview")
    say(f"  выгрузка:    {url}api/export/calibration.csv")
    if host in ("0.0.0.0", "::"):
        say(f"  в локальной сети: http://{local_address()}:{port}/")
        say("  внимание: панель открыта всем в сети, авторизации в ней нет")
    say("  Ctrl+C - остановка\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        say("\n  остановлено")
    finally:
        httpd.server_close()
