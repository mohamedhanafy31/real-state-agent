#!/bin/bash
# Startup script for the orchestrator

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start the orchestrator
python -m uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8040} --reload

