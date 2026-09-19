#!/usr/bin/env sh
# Запуск локальной платформы «Синдикат». Зависимостей нет: только Python 3.9+.
cd "$(dirname "$0")" || exit 1
exec python3 -m syndicat "$@"
