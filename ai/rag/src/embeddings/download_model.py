"""
Utility script to pre-download the embedding model.
This ensures the model is cached before the server starts.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def download_embedding_model(model_name: str = "mohamed2811/Muffakir_Embedding_V2", 
                            cache_dir: str = None):
    """
    Pre-download the embedding model to cache.
    
    Args:
        model_name: Name of the model to download
        cache_dir: Optional cache directory (default: ~/.cache/huggingface/hub)
    """
    import logging
    from transformers import AutoTokenizer, AutoModel
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("Pre-downloading Embedding Model")
    logger.info("="*60)
    logger.info(f"Model: {model_name}")
    
    if cache_dir:
        logger.info(f"Cache directory: {cache_dir}")
        os.environ['HF_HOME'] = cache_dir
    
    try:
        logger.info("\n[1/2] Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        logger.info("✓ Tokenizer downloaded successfully")
        
        logger.info("\n[2/2] Downloading model (this may take a while)...")
        model = AutoModel.from_pretrained(model_name)
        logger.info("✓ Model downloaded successfully")
        
        # Get cache location
        from huggingface_hub import snapshot_download
        cache_path = snapshot_download(repo_id=model_name, cache_dir=cache_dir)
        
        logger.info("\n" + "="*60)
        logger.info("✓ Model pre-downloaded successfully!")
        logger.info(f"Cache location: {cache_path}")
        logger.info("="*60)
        
        return True
    
    except Exception as e:
        logger.error(f"\n✗ Error downloading model: {str(e)}")
        logger.error("The model will be downloaded automatically on first use.")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pre-download embedding model")
    parser.add_argument(
        "--model-name",
        default="mohamed2811/Muffakir_Embedding_V2",
        help="Model name to download"
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Cache directory (default: ~/.cache/huggingface/hub)"
    )
    
    args = parser.parse_args()
    
    success = download_embedding_model(
        model_name=args.model_name,
        cache_dir=args.cache_dir
    )
    
    sys.exit(0 if success else 1)

