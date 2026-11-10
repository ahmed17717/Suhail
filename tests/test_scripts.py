"""CLI tools, exercised with the fake embedder so no model is needed."""

import sys

import pytest
from dotenv import dotenv_values

from scripts import manage
from suhail import bootstrap
from suhail.security import hash_password, verify_password
from tests.fakes import FakeEmbedding, OtherFakeEmbedding


@pytest.fixture
def cli(settings, monkeypatch, capsys):
    embedder = {"current": FakeEmbedding}
    monkeypatch.setattr(manage, "load_settings", lambda: settings)
    monkeypatch.setattr(
        manage,
        "build_knowledge",
        lambda s, **kw: bootstrap.build_knowledge(
            s, embedding_function=embedder["current"](), **kw
        ),
    )

    def run(*argv) -> tuple[int, str, str]:
        monkeypatch.setattr(sys, "argv", ["manage", *argv])
        code = manage.main()
        out = capsys.readouterr()
        return code, out.out, out.err

    run.embedder = embedder
    return run


def test_ingest_folder_then_list_skip_replace_delete_reindex(cli, tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("alpha policy text", "utf-8")
    (folder / "b.txt").write_text("beta policy text", "utf-8")
    (folder / "ignored.xlsx").write_bytes(b"x")

    code, out, _ = cli("ingest", str(folder))
    assert code == 0 and out.count("OK") == 2 and "ignored" not in out

    _, out, _ = cli("ingest", str(folder))
    assert out.count("SKIP") == 2

    _, out, _ = cli("ingest", str(folder), "--replace")
    assert out.count("OK") == 2

    _, out, _ = cli("list")
    assert "a.txt" in out and "b.txt" in out

    doc_id = out.splitlines()[0].split()[0]
    assert cli("delete", doc_id)[0] == 0
    assert cli("delete", "missing")[0] == 1

    code, out, _ = cli("reindex")
    assert code == 0 and "Re-indexed 1 documents" in out


def test_ingest_reports_failures_with_a_nonzero_exit_code(cli, tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    code, _, err = cli("ingest", str(bad))
    assert code == 1 and "FAIL" in err


def test_list_works_on_an_empty_knowledge_base(cli):
    assert "No documents" in cli("list")[1]


def test_generated_hash_survives_a_dotenv_round_trip(tmp_path):
    # The hash contains '$' and '+/=' — make sure an env file doesn't mangle it.
    stored = hash_password("round-trip-password")
    env = tmp_path / ".env"
    env.write_text(f"ADMIN_PASSWORD_HASH='{stored}'\n", "utf-8")
    loaded = dotenv_values(env)["ADMIN_PASSWORD_HASH"]
    assert loaded == stored and verify_password("round-trip-password", loaded)


def test_reindex_after_switching_embedding_model(cli, tmp_path):
    doc = tmp_path / "a.txt"
    doc.write_text("alpha policy text", "utf-8")
    cli("ingest", str(doc))

    cli.embedder["current"] = OtherFakeEmbedding  # simulate changing EMBEDDING_MODEL
    code, out, _ = cli("reindex")
    assert code == 0 and "Re-indexed 1 documents" in out
    assert cli("ingest", str(doc))[1].count("SKIP") == 1  # index opens normally afterwards


def test_reindex_aborts_before_touching_anything_if_an_original_is_missing(cli, settings, tmp_path):
    doc = tmp_path / "a.txt"
    doc.write_text("alpha policy text", "utf-8")
    cli("ingest", str(doc))
    next(settings.uploads_dir.iterdir()).unlink()

    cli.embedder["current"] = OtherFakeEmbedding
    code, _, err = cli("reindex")
    assert code == 1 and "a.txt" in err and "nothing was changed" in err
    # The old index must be untouched: it still opens with the OLD model and holds its chunk.
    # (Had the CLI dropped it before checking, this would be empty.)
    knowledge = bootstrap.build_knowledge(settings, embedding_function=FakeEmbedding())
    assert knowledge.store.count() == 1
