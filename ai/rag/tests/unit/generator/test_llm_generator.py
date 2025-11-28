"""
Unit tests for LLMGenerator
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from src.generator.llm_generator import LLMGenerator


class TestLLMGenerator:
    """Test cases for LLMGenerator."""
    
    @pytest.fixture
    def api_key(self):
        """Get or create test API key."""
        return os.getenv('GEMINI_API_KEY', 'test-api-key')
    
    @pytest.fixture
    def generator(self, api_key):
        """Create generator instance with mocked client."""
        with patch('src.generator.llm_generator.genai') as mock_genai:
            mock_model = Mock()
            mock_genai.configure = Mock()
            mock_genai.GenerativeModel = Mock(return_value=mock_model)
            
            gen = LLMGenerator(api_key=api_key, model_name="gemini-pro")
            gen.client = mock_model
            return gen
    
    def test_init_with_api_key(self, api_key):
        """Test initialization with API key."""
        with patch('src.generator.llm_generator.genai'):
            generator = LLMGenerator(api_key=api_key)
            assert generator.api_key == api_key
            assert generator.model_name == "gemini-pro"
    
    def test_init_with_env_var(self):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'env-api-key'}):
            with patch('src.generator.llm_generator.genai'):
                generator = LLMGenerator()
                assert generator.api_key == 'env-api-key'
    
    def test_init_no_api_key(self):
        """Test initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Gemini API key not provided"):
                LLMGenerator()
    
    def test_generate(self, generator):
        """Test basic generation."""
        # Mock the response
        mock_response = Mock()
        mock_response.text = "Generated answer"
        generator.client.generate_content = Mock(return_value=mock_response)
        
        result = generator.generate("test prompt")
        
        assert result == "Generated answer"
        generator.client.generate_content.assert_called_once()
    
    def test_generate_with_context(self, generator):
        """Test generation with context."""
        mock_response = Mock()
        mock_response.text = "Answer with context"
        generator.client.generate_content = Mock(return_value=mock_response)
        
        context = ["Context 1", "Context 2"]
        result = generator.generate("prompt", context=context)
        
        assert result == "Answer with context"
        # Check that context was included in the prompt
        call_args = generator.client.generate_content.call_args[0][0]
        assert "Context 1" in call_args
        assert "Context 2" in call_args
    
    def test_generate_with_temperature(self, generator):
        """Test generation with temperature parameter."""
        mock_response = Mock()
        mock_response.text = "Answer"
        generator.client.generate_content = Mock(return_value=mock_response)
        
        generator.generate("prompt", temperature=0.5)
        
        # Check that temperature was passed in config
        call_kwargs = generator.client.generate_content.call_args[1]
        assert 'generation_config' in call_kwargs
        assert call_kwargs['generation_config']['temperature'] == 0.5
    
    def test_generate_with_max_tokens(self, generator):
        """Test generation with max_tokens parameter."""
        mock_response = Mock()
        mock_response.text = "Answer"
        generator.client.generate_content = Mock(return_value=mock_response)
        
        generator.generate("prompt", max_tokens=100)
        
        call_kwargs = generator.client.generate_content.call_args[1]
        assert call_kwargs['generation_config']['max_output_tokens'] == 100
    
    def test_generate_stream(self, generator):
        """Test streaming generation."""
        # Mock streaming response
        mock_chunk1 = Mock()
        mock_chunk1.text = "Chunk "
        mock_chunk2 = Mock()
        mock_chunk2.text = "1"
        mock_chunk3 = Mock()
        mock_chunk3.text = " 2"
        
        generator.client.generate_content = Mock(return_value=[
            mock_chunk1, mock_chunk2, mock_chunk3
        ])
        
        chunks = list(generator.generate_stream("prompt"))
        
        assert len(chunks) == 3
        assert chunks[0] == "Chunk "
        assert chunks[1] == "1"
        assert chunks[2] == " 2"
        
        # Check that stream=True was passed
        call_kwargs = generator.client.generate_content.call_args[1]
        assert call_kwargs['stream'] is True
    
    def test_build_prompt_without_context(self, generator):
        """Test prompt building without context."""
        prompt = generator._build_prompt("test question", None)
        assert prompt == "test question"
    
    def test_build_prompt_with_context(self, generator):
        """Test prompt building with context."""
        context = ["Context 1", "Context 2"]
        prompt = generator._build_prompt("test question", context)
        
        assert "test question" in prompt
        assert "Context 1" in prompt
        assert "Context 2" in prompt
        assert "السياق" in prompt  # Arabic word for context
    
    def test_generate_error_handling(self, generator):
        """Test error handling in generation."""
        generator.client.generate_content = Mock(side_effect=Exception("API Error"))
        
        with pytest.raises(Exception, match="API Error"):
            generator.generate("prompt")

