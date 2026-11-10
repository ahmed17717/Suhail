"""LlamaCppGenerator with a fake `llama_cpp` module — verifies behaviour, not the model."""

import sys
import threading
import time
import types

import pytest

from suhail.errors import ConfigError, ModelNotFoundError
from suhail.knowledge.embeddings import build_embedding_function
from suhail.llm.generator import LlamaCppGenerator


class FakeLlama:
    instances = 0
    active = 0
    max_active = 0
    lock = threading.Lock()

    def __init__(self, **kwargs):
        type(self).instances += 1
        self.init_kwargs = kwargs
        self.calls = []

    def create_chat_completion(self, **kwargs):
        cls = type(self)
        with cls.lock:
            cls.active += 1
            cls.max_active = max(cls.max_active, cls.active)
        time.sleep(0.02)  # give racing threads a chance to overlap
        with cls.lock:
            cls.active -= 1
        self.calls.append(kwargs)
        return {"choices": [{"message": {"content": "  answer  "}}]}


@pytest.fixture
def fake_llama(monkeypatch):
    FakeLlama.instances = FakeLlama.active = FakeLlama.max_active = 0
    module = types.ModuleType("llama_cpp")
    module.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", module)
    return FakeLlama


@pytest.fixture
def weights(tmp_path):
    path = tmp_path / "model.gguf"
    path.write_bytes(b"weights")
    return path


def test_missing_weights_fail_fast_with_a_helpful_message(tmp_path):
    with pytest.raises(ModelNotFoundError, match="download_models"):
        LlamaCppGenerator(tmp_path / "nope.gguf")


def test_model_is_not_loaded_until_first_use(fake_llama, weights):
    LlamaCppGenerator(weights)
    assert fake_llama.instances == 0


def test_generate_passes_settings_through_and_strips_output(fake_llama, weights):
    gen = LlamaCppGenerator(weights, n_ctx=4096, n_gpu_layers=20, max_tokens=123)
    assert gen.generate([{"role": "user", "content": "hi"}]) == "answer"
    llm = gen._llm
    assert llm.init_kwargs["n_ctx"] == 4096 and llm.init_kwargs["n_gpu_layers"] == 20
    assert llm.calls[0]["max_tokens"] == 123 and llm.calls[0]["repeat_penalty"] == 1.15


def test_concurrent_users_load_once_and_never_infer_simultaneously(fake_llama, weights):
    gen = LlamaCppGenerator(weights)
    threads = [
        threading.Thread(target=gen.generate, args=([{"role": "user", "content": "q"}],))
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert fake_llama.instances == 1
    assert fake_llama.max_active == 1


def test_embedding_factory_explains_a_missing_model(monkeypatch):
    def boom(**_kwargs):
        raise OSError("not in cache")

    monkeypatch.setattr(
        "chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction", boom
    )
    with pytest.raises(ConfigError, match="download_models"):
        build_embedding_function("some-model")
