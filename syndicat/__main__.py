# -*- coding: utf-8 -*-
"""Точка входа: python3 -m syndicat [--host 127.0.0.1] [--port 8777]."""

import argparse

from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python3 -m syndicat",
        description="Синдикат - локальная платформа учёта ТЧЧ и ценообразования")
    parser.add_argument("--host", default="127.0.0.1", help="адрес прослушивания")
    parser.add_argument("--port", type=int, default=8777, help="порт (по умолчанию 8777)")
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
