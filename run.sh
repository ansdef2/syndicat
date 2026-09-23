#!/usr/bin/env sh
# Запуск локальной платформы «Синдикат». Зависимостей нет: нужен только Python 3.9+.
# Интерпретатор называется по-разному: python3 в Linux и macOS, python или py
# в Windows, - поэтому берём первый, который действительно отзывается третьей версией.
cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3 python py; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  if [ "$candidate" = "py" ]; then
    if [ "$("$candidate" -3 -c 'import sys;print(sys.version_info[0])' 2>/dev/null)" = "3" ]; then
      PY="$candidate -3"
      break
    fi
  elif [ "$("$candidate" -c 'import sys;print(sys.version_info[0])' 2>/dev/null)" = "3" ]; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "Python 3 не найден." >&2
  echo "Установите его с https://www.python.org/downloads/ и при установке в Windows" >&2
  echo "отметьте «Add python.exe to PATH», затем откройте терминал заново." >&2
  exit 1
fi

# shellcheck disable=SC2086
exec $PY -m syndicat "$@"
