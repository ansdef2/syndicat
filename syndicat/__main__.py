# -*- coding: utf-8 -*-
"""Точка входа: python3 -m syndicat [--host 127.0.0.1] [--port 8777] [--log]."""

import argparse
import sys

import os

from .server import open_log, serve


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python3 -m syndicat",
        description="Синдикат - локальная платформа учёта ТЧЧ и ценообразования")
    parser.add_argument("--host", default="127.0.0.1", help="адрес прослушивания")
    parser.add_argument("--port", type=int, default=8777, help="порт (по умолчанию 8777)")
    parser.add_argument("--log", nargs="?", const="syndicat.log", default=None,
                        metavar="ФАЙЛ",
                        help="писать журнал в файл (по умолчанию syndicat.log); "
                             "при запуске без консоли включается сам")
    args = parser.parse_args()

    log_path = args.log
    if log_path is None and sys.stdout is None:
        # Запуск под pythonw.exe: консоли нет, поэтому журнал кладём рядом с проектом
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "syndicat.log")
    if log_path:
        open_log(log_path)

    serve(args.host, args.port)


if __name__ == "__main__":
    main()
