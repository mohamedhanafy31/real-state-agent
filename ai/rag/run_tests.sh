#!/bin/bash
# Test runner script for RAG system

echo "Running RAG System Tests"
echo "========================"

# Run unit tests
echo ""
echo "Running unit tests..."
pytest tests/unit -v --tb=short

# Run integration tests (requires API key)
if [ -n "$GEMINI_API_KEY" ]; then
    echo ""
    echo "Running integration tests..."
    pytest tests/integration -v --tb=short
else
    echo ""
    echo "Skipping integration tests (GEMINI_API_KEY not set)"
fi

# Run all tests with coverage
echo ""
echo "Running all tests with coverage..."
pytest tests/ --cov=src --cov-report=html --cov-report=term

echo ""
echo "Tests completed!"
echo "Coverage report generated in htmlcov/index.html"

