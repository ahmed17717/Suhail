"""Factory for the production embedding function (sentence-transformers).

Kept separate from `VectorStore` so the heavy ML dependency is imported lazily and
only in production; tests inject a tiny deterministic fake instead.
"""

from __future__ import annotations

import logging

from suhail.errors import ConfigError

logger = logging.getLogger(__name__)


def build_embedding_function(model_name: str, device: str = "cpu"):
    try:
        from chromadb.utils import embedding_functions

        # normalize_embeddings is pinned to False on purpose: SIMILARITY_THRESHOLD is
        # calibrated against these (un-normalised) L2 distances. Changing it, or the
        # model, requires re-indexing and re-tuning the threshold.
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name, device=device, normalize_embeddings=False
        )
    except ImportError as exc:
        raise ConfigError(
            "sentence-transformers is not installed. Run: pip install -r requirements.txt"
        ) from exc
    except Exception as exc:  # e.g. model not cached while HF_HUB_OFFLINE=1
        raise ConfigError(
            f"Embedding model {model_name!r} could not be loaded ({exc}). "
            "On a machine with internet run: python -m scripts.download_models, "
            "then copy the models/ folder to the server."
        ) from exc
