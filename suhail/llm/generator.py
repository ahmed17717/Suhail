"""Text generation behind a tiny interface, so the RAG pipeline never imports llama.cpp."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from suhail.errors import ModelNotFoundError

logger = logging.getLogger(__name__)


class Generator(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str: ...


@dataclass(frozen=True)
class SamplingParams:
    """Sampling settings tuned on real Arabic documents (conservative, low-drift)."""

    temperature: float = 0.6
    top_p: float = 0.8
    top_k: int = 20
    repeat_penalty: float = 1.15
    presence_penalty: float = 0.3
    frequency_penalty: float = 0.1


class LlamaCppGenerator:
    """Runs a local GGUF model via llama-cpp-python.

    Concurrency: a `Llama` instance is *not* safe for simultaneous calls, and
    Streamlit serves every browser session in its own thread. Loading and inference
    are therefore serialised with locks; concurrent users queue instead of crashing
    or corrupting each other's output.
    """

    def __init__(
        self,
        model_path: Path,
        *,
        n_ctx: int = 8192,
        n_threads: int = 4,
        n_gpu_layers: int = -1,
        max_tokens: int = 400,
        sampling: SamplingParams | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        if not self._model_path.is_file():
            raise ModelNotFoundError(
                f"LLM weights not found at {self._model_path}. "
                "Run: python -m scripts.download_models"
            )
        self._n_ctx = n_ctx
        self._n_threads = n_threads
        self._n_gpu_layers = n_gpu_layers
        self._max_tokens = max_tokens
        self._sampling = sampling or SamplingParams()
        self._llm = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    def _load(self):
        with self._load_lock:
            if self._llm is None:
                from llama_cpp import Llama  # heavy import, deferred until first use

                started = time.perf_counter()
                self._llm = Llama(
                    model_path=str(self._model_path),
                    n_ctx=self._n_ctx,
                    n_threads=self._n_threads,
                    n_gpu_layers=self._n_gpu_layers,
                    verbose=False,
                )
                logger.info(
                    "LLM loaded in %.1fs (%s)", time.perf_counter() - started, self._model_path.name
                )
        return self._llm

    def generate(self, messages: list[dict[str, str]]) -> str:
        llm = self._load()
        s = self._sampling
        with self._infer_lock:
            output = llm.create_chat_completion(
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=s.temperature,
                top_p=s.top_p,
                top_k=s.top_k,
                repeat_penalty=s.repeat_penalty,
                presence_penalty=s.presence_penalty,
                frequency_penalty=s.frequency_penalty,
            )
        return output["choices"][0]["message"]["content"].strip()
