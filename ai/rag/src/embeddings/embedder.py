"""
Embedder Module for Arabic text embeddings
Supports both sentence-transformers models and standard transformers models with CUDA support.
"""

import torch
import logging
from typing import List, Union, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AraModernBERTEmbedder:
    """Embedder for Arabic text embeddings. Supports sentence-transformers and transformers models."""
    
    def __init__(self, model_name: str = "mohamed2811/Muffakir_Embedding_V2",
                 device: Optional[str] = None, batch_size: int = 32,
                 use_sentence_transformers: Optional[bool] = None):
        """
        Initialize the embedder.
        
        Args:
            model_name: Name of the model (sentence-transformers or transformers model)
            device: Device to use ('cuda' or 'cpu'). Auto-detects if None.
            batch_size: Batch size for encoding
            use_sentence_transformers: Whether to use sentence-transformers library.
                                      If None, auto-detects based on model name or tries sentence-transformers first.
        """
        self.model_name = model_name
        self.batch_size = batch_size
        
        # Set device
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        if self.device == 'cuda' and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available. Using CPU.")
            self.device = 'cpu'
        
        logger.info(f"Using device: {self.device}")
        
        # Determine if we should use sentence-transformers
        self.use_sentence_transformers = use_sentence_transformers
        if self.use_sentence_transformers is None:
            # Auto-detect: try sentence-transformers first for better compatibility
            self.use_sentence_transformers = True
        
        # Load model and tokenizer
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model (sentence-transformers or transformers)."""
        import os
        from pathlib import Path
        
        logger.info(f"Loading model: {self.model_name}")
        
        # Check if model is cached
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_cache_path = cache_dir / f"models--{self.model_name.replace('/', '--')}"
        is_cached = model_cache_path.exists() and any(model_cache_path.iterdir())
        
        if is_cached:
            logger.info(f"✓ Model found in cache: {model_cache_path}")
            logger.info("  Loading from cache (no download needed)")
        else:
            logger.info(f"⚠ Model not found in cache")
            logger.info(f"  Will download from HuggingFace (first time only)")
            logger.info(f"  Cache location: {cache_dir}")
            logger.info(f"  This may take several minutes depending on your internet connection")
        
        # Try sentence-transformers first if enabled
        if self.use_sentence_transformers:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Using sentence-transformers library")
                
                if is_cached:
                    logger.info("Loading model from cache...")
                else:
                    logger.info("Downloading model (this may take a while on first run)...")
                
                self.model = SentenceTransformer(self.model_name, device=self.device)
                self.tokenizer = None  # SentenceTransformer handles tokenization internally
                self.is_sentence_transformer = True
                
                if is_cached:
                    logger.info("✓ Model loaded successfully from cache using sentence-transformers")
                else:
                    logger.info("✓ Model downloaded and loaded successfully using sentence-transformers")
                return
            except ImportError:
                logger.warning("sentence-transformers not available, falling back to transformers")
                self.use_sentence_transformers = False
            except Exception as e:
                logger.warning(f"Failed to load with sentence-transformers: {str(e)}")
                logger.info("Falling back to transformers library")
                self.use_sentence_transformers = False
        
        # Fallback to transformers library
        try:
            from transformers import AutoTokenizer, AutoModel
        except ImportError:
            raise ImportError(
                "transformers is required. Install it with: pip install transformers"
            )
        
        logger.info("Using transformers library")
        self.is_sentence_transformer = False
        
        try:
            # from_pretrained automatically downloads if not cached
            # Cache location: ~/.cache/huggingface/hub/
            if is_cached:
                logger.info("Loading tokenizer from cache...")
            else:
                logger.info("Downloading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            if is_cached:
                logger.info("Loading model from cache...")
            else:
                logger.info("Downloading model (this may take a while on first run)...")
            self.model = AutoModel.from_pretrained(self.model_name)
            
            logger.info(f"Moving model to device: {self.device}")
            self.model.to(self.device)
            self.model.eval()
            
            if is_cached:
                logger.info("✓ Model loaded successfully from cache using transformers")
            else:
                logger.info("✓ Model downloaded and loaded successfully using transformers")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise
    
    def embed(self, text: Union[str, List[str]], 
              normalize: bool = True) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for text(s).
        
        Args:
            text: Single text string or list of texts
            normalize: Whether to normalize embeddings to unit vectors
            
        Returns:
            Embedding array(s) - single array for single text, list for multiple texts
        """
        is_single = isinstance(text, str)
        texts = [text] if is_single else text
        
        if not texts:
            return np.array([]) if is_single else []
        
        # Process in batches
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_embeddings = self._embed_batch(batch_texts, normalize)
            all_embeddings.extend(batch_embeddings)
        
        if is_single:
            return all_embeddings[0]
        return all_embeddings
    
    def _embed_batch(self, texts: List[str], normalize: bool) -> List[np.ndarray]:
        """Embed a batch of texts."""
        if self.is_sentence_transformer:
            # Use sentence-transformers encode method
            # SentenceTransformer handles normalization internally, but we can override
            embeddings = self.model.encode(
                texts,
                batch_size=len(texts),
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                show_progress_bar=False
            )
            return [emb for emb in embeddings]
        else:
            # Use transformers with manual pooling
            # Tokenize
            encoded = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors='pt'
            )
            
            # Move to device
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**encoded)
                # Use mean pooling of last hidden state
                embeddings = outputs.last_hidden_state
                # Mean pooling (average over sequence length, excluding padding)
                attention_mask = encoded['attention_mask']
                embeddings = (embeddings * attention_mask.unsqueeze(-1)).sum(1) / attention_mask.sum(1, keepdim=True)
                embeddings = embeddings.cpu().numpy()
            
            # Normalize if requested
            if normalize:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
                embeddings = embeddings / norms
            
            return [emb for emb in embeddings]
    
    def get_embedding_dim(self) -> int:
        """Get the dimension of embeddings."""
        if self.is_sentence_transformer:
            # For sentence-transformers, get dimension from model
            return self.model.get_sentence_embedding_dimension()
        else:
            # Get dimension from model config
            return self.model.config.hidden_size

