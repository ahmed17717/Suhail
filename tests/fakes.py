"""Deterministic test doubles — no network, no GPU, no model downloads."""

from __future__ import annotations

import hashlib
import math
import re

from chromadb import Documents, EmbeddingFunction, Embeddings

_WORD = re.compile(r"\w+", re.UNICODE)
DIMS = 512


class FakeEmbedding(EmbeddingFunction):
    """Hashed bag-of-words, L2-normalised: identical text -> distance 0,
    fully disjoint text -> distance sqrt(2). Good enough to test ranking logic."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        vectors = []
        for text in input:
            vec = [0.0] * DIMS
            for word in _WORD.findall(text.lower()):
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMS
                vec[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    @staticmethod
    def name() -> str:
        return "suhail-fake"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> FakeEmbedding:
        return FakeEmbedding()


class FakeGenerator:
    """Records the prompts it receives and returns a canned answer."""

    def __init__(self, reply: str = "إجابة تجريبية", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.reply


class OtherFakeEmbedding(FakeEmbedding):
    """A *different* model identity, to simulate switching EMBEDDING_MODEL."""

    @staticmethod
    def name() -> str:
        return "suhail-other-fake"

    @staticmethod
    def build_from_config(config: dict) -> OtherFakeEmbedding:
        return OtherFakeEmbedding()
