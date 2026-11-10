from __future__ import annotations

import pytest

from suhail.config import Settings
from suhail.ingestion.service import IngestionService
from suhail.knowledge.registry import DocumentRegistry
from suhail.knowledge.vector_store import VectorStore
from suhail.rag.pipeline import RagPipeline
from tests.fakes import FakeEmbedding, FakeGenerator


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data", llm_model_path=tmp_path / "missing.gguf")


@pytest.fixture
def store(settings) -> VectorStore:
    return VectorStore(settings.chroma_path, FakeEmbedding())


@pytest.fixture
def registry(settings) -> DocumentRegistry:
    return DocumentRegistry(settings.registry_path)


@pytest.fixture
def ingestion(store, registry, settings) -> IngestionService:
    return IngestionService(
        store,
        registry,
        settings.uploads_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        fix_rtl=False,
        max_upload_bytes=1024 * 1024,
    )


@pytest.fixture
def generator() -> FakeGenerator:
    return FakeGenerator()


@pytest.fixture
def pipeline(store, generator) -> RagPipeline:
    return RagPipeline(store, generator, assistant_name="سهيل", top_k=6, similarity_threshold=1.2)
