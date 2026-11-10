"""Central configuration.

Everything tunable comes from environment variables (see `.env.example`), is
validated once at startup, and is exposed as an immutable `Settings` object.
Nothing else in the code base reads `os.environ`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from suhail.errors import ConfigError

DEFAULT_WELCOME = "أنا مساعدك الافتراضي سهيل، في خدمتك."


def _get_int(env: Mapping[str, str], key: str, default: int, *, minimum: int | None = None) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ConfigError(f"{key} must be >= {minimum}, got {value}")
    return value


def _get_float(env: Mapping[str, str], key: str, default: float, *, minimum: float = 0.0) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{key} must be >= {minimum}, got {value}")
    return value


def _get_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{key} must be a boolean (true/false), got {raw!r}")


@dataclass(frozen=True)
class Settings:
    # --- branding / UI -----------------------------------------------------
    app_title: str = "Suhail — المساعد الافتراضي"
    welcome_message: str = DEFAULT_WELCOME
    assistant_name: str = "سهيل"
    assets_dir: Path = Path("assets")

    # --- storage -----------------------------------------------------------
    data_dir: Path = Path("data")

    # --- retrieval ---------------------------------------------------------
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_device: str = "cpu"
    top_k: int = 6
    # Chroma L2 distance cut-off. Calibrated empirically for the model above;
    # re-tune with `make eval` if you change the embedding model.
    similarity_threshold: float = 1.2
    chunk_size: int = 350
    chunk_overlap: int = 80

    # --- generation --------------------------------------------------------
    llm_model_path: Path = Path("models/Qwen2.5-14B-Instruct-Q4_K_M.gguf")
    llm_n_ctx: int = 8192
    llm_n_threads: int = 4
    llm_n_gpu_layers: int = -1  # -1 = offload every layer that fits
    llm_max_tokens: int = 400
    llm_temperature: float = 0.6

    # --- ingestion ---------------------------------------------------------
    max_upload_mb: int = 20
    pdf_rtl_fix: bool = True

    # --- admin / ops -------------------------------------------------------
    admin_password_hash: str = ""
    admin_session_minutes: int = 30
    log_level: str = "INFO"

    # ---- derived paths ----------------------------------------------------
    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma_db"

    @property
    def registry_path(self) -> Path:
        return self.data_dir / "doc_registry.json"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    # ---- construction -----------------------------------------------------
    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        defaults = cls()
        settings = cls(
            app_title=env.get("APP_TITLE", "").strip() or defaults.app_title,
            welcome_message=env.get("WELCOME_MESSAGE", "").strip() or defaults.welcome_message,
            assistant_name=env.get("ASSISTANT_NAME", "").strip() or defaults.assistant_name,
            assets_dir=Path(env.get("ASSETS_DIR", "").strip() or defaults.assets_dir),
            data_dir=Path(env.get("DATA_DIR", "").strip() or defaults.data_dir),
            embedding_model=env.get("EMBEDDING_MODEL", "").strip() or defaults.embedding_model,
            embedding_device=env.get("EMBEDDING_DEVICE", "").strip() or defaults.embedding_device,
            top_k=_get_int(env, "TOP_K", defaults.top_k, minimum=1),
            similarity_threshold=_get_float(
                env, "SIMILARITY_THRESHOLD", defaults.similarity_threshold, minimum=0.0
            ),
            chunk_size=_get_int(env, "CHUNK_SIZE", defaults.chunk_size, minimum=50),
            chunk_overlap=_get_int(env, "CHUNK_OVERLAP", defaults.chunk_overlap, minimum=0),
            llm_model_path=Path(env.get("LLM_MODEL_PATH", "").strip() or defaults.llm_model_path),
            llm_n_ctx=_get_int(env, "LLM_N_CTX", defaults.llm_n_ctx, minimum=512),
            llm_n_threads=_get_int(env, "LLM_N_THREADS", defaults.llm_n_threads, minimum=1),
            llm_n_gpu_layers=_get_int(env, "LLM_N_GPU_LAYERS", defaults.llm_n_gpu_layers),
            llm_max_tokens=_get_int(env, "LLM_MAX_TOKENS", defaults.llm_max_tokens, minimum=16),
            llm_temperature=_get_float(env, "LLM_TEMPERATURE", defaults.llm_temperature),
            max_upload_mb=_get_int(env, "MAX_UPLOAD_MB", defaults.max_upload_mb, minimum=1),
            pdf_rtl_fix=_get_bool(env, "PDF_RTL_FIX", defaults.pdf_rtl_fix),
            admin_password_hash=env.get("ADMIN_PASSWORD_HASH", "").strip(),
            admin_session_minutes=_get_int(
                env, "ADMIN_SESSION_MINUTES", defaults.admin_session_minutes, minimum=1
            ),
            log_level=(env.get("LOG_LEVEL", "").strip() or defaults.log_level).upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.chunk_overlap >= self.chunk_size:
            raise ConfigError(
                f"CHUNK_OVERLAP ({self.chunk_overlap}) must be smaller than "
                f"CHUNK_SIZE ({self.chunk_size})"
            )
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError(f"LOG_LEVEL must be DEBUG/INFO/WARNING/ERROR, got {self.log_level}")
