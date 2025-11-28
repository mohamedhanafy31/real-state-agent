#!/bin/bash
# Script to run the FastAPI server

# Activate conda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate real-state-rag

# Set defaults if not set
export PORT=${PORT:-8000}
export HOST=${HOST:-0.0.0.0}
export RELOAD=${RELOAD:-true}  # Default to true for development

# Run the FastAPI server
cd "$(dirname "$0")"

# Use reload flag if RELOAD is true
if [ "$RELOAD" = "true" ]; then
    python -m uvicorn app.api:app --host $HOST --port $PORT --reload
else
    python -m uvicorn app.api:app --host $HOST --port $PORT
fi

