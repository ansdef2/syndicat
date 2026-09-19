# -*- coding: utf-8 -*-
"""Локальный HTTP-сервер платформы. Только стандартная библиотека."""

import json
import mimetypes
import os
import posixpath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from . import api

WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


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
        print(f"  {self.address_string()} {fmt % args}")

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


def serve(host: str = "127.0.0.1", port: int = 8777) -> None:
    httpd = ThreadingHTTPServer((host, port), SyndicatHandler)
    url = f"http://{host}:{port}/"
    print("  СИНДИКАТ · локальная платформа")
    print(f"  панель:      {url}")
    print(f"  API:         {url}api/overview")
    print(f"  выгрузка:    {url}api/export/calibration.csv")
    print("  Ctrl+C - остановка\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  остановлено")
    finally:
        httpd.server_close()
