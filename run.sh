#!/usr/bin/env bash
# Start the dashboard locally. Requires DEMO_PASSWORD and a populated ./data directory (see README).
cd "$(dirname "$0")"
export PYTHONPATH="$PWD:$PWD/app:$PWD/swing:$PWD/backtest${PYTHONPATH:+:$PYTHONPATH}"
: "${DEMO_PASSWORD:?set DEMO_PASSWORD}"
exec streamlit run app/app.py --server.port "${PORT:-8501}"
