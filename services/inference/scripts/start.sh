#!/bin/bash
# PaddleOCR is loaded lazily on the first receipt request. PORT is set by Railway.
set -e
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
