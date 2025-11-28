"""
Pytest configuration and fixtures
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def sample_text():
    """Sample Arabic text for testing."""
    return """
    هذا نص تجريبي باللغة العربية.
    يحتوي على عدة فقرات للاختبار.
    
    الفقرة الثانية تحتوي على معلومات إضافية.
    يمكن استخدامها لاختبار نظام RAG.
    """

@pytest.fixture
def sample_egyptian_text():
    """Sample Egyptian dialect text for testing."""
    return """
    إيه اللي حصل؟ عايز أعرف إيه أنواع العقارات المتاحة.
    عندك معلومات عن الشقق؟ مش عايز حاجة كبيرة.
    """

@pytest.fixture
def sample_english_text():
    """Sample English text for testing."""
    return """
    This is a sample English text.
    It contains multiple paragraphs for testing.
    
    The second paragraph has additional information.
    It can be used to test the RAG system.
    """

@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent.parent / "data" / "raw"

@pytest.fixture
def test_docx_path(test_data_dir):
    """Path to test DOCX file."""
    # Try different possible names
    possible_names = ["test_document.docx", "TransIT_Profile.docx", "TransIT_Profile[1].docx"]
    for name in possible_names:
        path = test_data_dir / name
        if path.exists():
            return str(path)
    # If not found, return a path that might not exist (for mocking)
    return str(test_data_dir / "test_document.docx")

@pytest.fixture
def sample_txt_file(temp_dir, sample_text):
    """Create a sample text file."""
    file_path = Path(temp_dir) / "test.txt"
    file_path.write_text(sample_text, encoding='utf-8')
    return str(file_path)

@pytest.fixture
def gemini_api_key():
    """Get Gemini API key from environment or return None."""
    return os.getenv('GEMINI_API_KEY', None)

@pytest.fixture
def skip_if_no_gemini_key(gemini_api_key):
    """Skip test if Gemini API key is not available."""
    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set")

