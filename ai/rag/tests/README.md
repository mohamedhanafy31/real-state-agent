# Test Suite Documentation

This directory contains comprehensive unit and integration tests for the RAG system.

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── unit/                    # Unit tests for individual components
│   ├── ingestion/          # Tests for loader, cleaner, chunker
│   ├── embeddings/         # Tests for embedder
│   ├── vector_store/       # Tests for FAISS store
│   ├── retrieval/          # Tests for retriever
│   ├── generator/          # Tests for LLM generator
│   ├── pipeline/           # Tests for old pipeline components
│   └── rag_graph/          # Tests for LangGraph nodes and graph
│       ├── test_nodes.py   # Tests for individual nodes
│       └── test_graph.py   # Tests for graph structure
└── integration/            # Integration tests for full workflow
    ├── test_full_pipeline.py      # Tests for old RAGPipeline
    └── test_langgraph_pipeline.py # Tests for LangGraph pipeline
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run only unit tests
```bash
pytest tests/unit/
```

### Run only integration tests
```bash
pytest tests/integration/
```

### Run LangGraph-specific tests
```bash
pytest tests/unit/rag_graph/
pytest tests/integration/test_langgraph_pipeline.py
```

### Run specific test file
```bash
pytest tests/unit/ingestion/test_loader.py
```

### Run with coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run using the test script
```bash
./run_tests.sh
```

## Test Categories

### Unit Tests

- **Ingestion Tests**: Test document loading, text cleaning, and chunking
- **Embedding Tests**: Test embedding generation with Arabic BERT models
- **Vector Store Tests**: Test FAISS index operations (add, search, save/load)
- **Retrieval Tests**: Test retrieval logic and query processing
- **Generator Tests**: Test LLM generation (mocked for unit tests)
- **LangGraph Node Tests**: Test individual LangGraph nodes (ingestion and query nodes)
- **LangGraph Graph Tests**: Test graph building and structure

### Integration Tests

- **Full Pipeline Tests** (`test_full_pipeline.py`): Test old RAGPipeline class (legacy)
- **LangGraph Pipeline Tests** (`test_langgraph_pipeline.py`): Test new LangGraph-based pipeline
- **End-to-End Tests**: Test with real documents (requires test document in `data/raw/`)

## Test Requirements

1. **Unit Tests**: Can run without external dependencies (mocked APIs)
2. **Integration Tests**: Require:
   - `GEMINI_API_KEY` environment variable (for generator tests)
   - Test document in `data/raw/test_document.docx` or `data/raw/TransIT_Profile.docx`
3. **LangGraph Tests**: Require:
   - `pytest-asyncio` for async test support
   - LangGraph and LangChain dependencies
   - Same requirements as integration tests for full workflow tests

## Skipping Tests

Some tests may be skipped if:
- Required dependencies are not installed (e.g., `python-docx`)
- Test files are not available
- API keys are not set
- GPU is not available (tests use CPU by default)

## Test Fixtures

Common fixtures available in `conftest.py`:
- `temp_dir`: Temporary directory for test files
- `sample_text`: Sample Arabic text
- `sample_egyptian_text`: Sample Egyptian dialect text
- `test_docx_path`: Path to test DOCX file
- `gemini_api_key`: Gemini API key from environment
- `skip_if_no_gemini_key`: Skip test if API key not available

## Writing New Tests

1. Place unit tests in `tests/unit/<module>/`
2. Place integration tests in `tests/integration/`
3. Use fixtures from `conftest.py` when possible
4. Mark slow tests with `@pytest.mark.slow`
5. Mark API-dependent tests with `@pytest.mark.requires_api`

## Example Test

```python
import pytest
from src.ingestion.loader import DocumentLoader

def test_load_text_file(sample_txt_file):
    loader = DocumentLoader()
    result = loader.load_file(sample_txt_file)
    assert 'content' in result
    assert 'metadata' in result
```

