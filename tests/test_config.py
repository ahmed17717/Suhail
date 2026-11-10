import pytest

from suhail.config import Settings
from suhail.errors import ConfigError


def test_defaults_when_environment_is_empty():
    s = Settings.from_env({})
    assert (s.top_k, s.similarity_threshold, s.chunk_size, s.chunk_overlap) == (6, 1.2, 350, 80)
    assert s.admin_password_hash == ""  # admin stays disabled until configured
    assert s.chroma_path == s.data_dir / "chroma_db"


def test_overrides_are_parsed_and_typed():
    s = Settings.from_env(
        {"TOP_K": "3", "SIMILARITY_THRESHOLD": "0.9", "PDF_RTL_FIX": "no", "DATA_DIR": "/srv/d"}
    )
    assert (s.top_k, s.similarity_threshold, s.pdf_rtl_fix) == (3, 0.9, False)
    assert str(s.uploads_dir) == "/srv/d/uploads"


@pytest.mark.parametrize(
    "env",
    [
        {"TOP_K": "abc"},
        {"TOP_K": "0"},
        {"SIMILARITY_THRESHOLD": "-1"},
        {"CHUNK_SIZE": "100", "CHUNK_OVERLAP": "100"},
        {"PDF_RTL_FIX": "maybe"},
        {"LOG_LEVEL": "LOUD"},
        {"MAX_UPLOAD_MB": "0"},
    ],
)
def test_invalid_values_fail_fast_with_a_clear_error(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_upload_limit_in_bytes():
    assert Settings.from_env({"MAX_UPLOAD_MB": "2"}).max_upload_bytes == 2 * 1024 * 1024


def test_env_example_stays_in_sync_with_the_code_defaults():
    # Guards against documentation drift: the template must parse, and every value it
    # documents must equal the real default.
    from dotenv import dotenv_values

    template = {k: v for k, v in dotenv_values(".env.example").items() if v}
    assert Settings.from_env(template) == Settings()
