import json

import pytest

from suhail.errors import RegistryError
from suhail.knowledge.registry import DocumentRegistry
from suhail.models import DocumentRecord


def rec(doc_id="d1", name="a.pdf", **kw):
    return DocumentRecord(doc_id=doc_id, name=name, doc_type=kw.pop("doc_type", "file"), **kw)


def test_add_get_all_remove_roundtrip(registry):
    registry.add(rec("d1", "a.pdf"))
    registry.add(rec("d2", "b", doc_type="manual", raw_text="نص"))
    assert [r.doc_id for r in registry.all()] == ["d1", "d2"]
    assert registry.get("d2").raw_text == "نص"
    assert registry.find_by_name("a.pdf") == "d1"
    assert registry.find_by_name("nope") is None
    registry.remove("d1")
    assert registry.get("d1") is None


def test_state_persists_across_instances(registry, settings):
    registry.add(rec("d1", "x.pdf", chunk_count=7))
    assert DocumentRegistry(settings.registry_path).get("d1").chunk_count == 7


def test_created_at_is_stamped(registry):
    assert registry.add(rec()).created_at


def test_loads_legacy_v0_format(settings):
    settings.registry_path.parent.mkdir(parents=True)
    settings.registry_path.write_text(
        json.dumps({"abc": {"name": "old.pdf", "type": "file", "raw_text": None}}),
        encoding="utf-8",
    )
    record = DocumentRegistry(settings.registry_path).get("abc")
    assert (record.name, record.stored_as, record.chunk_count) == ("old.pdf", None, 0)


def test_corrupt_registry_raises_instead_of_silently_resetting(settings):
    settings.registry_path.parent.mkdir(parents=True)
    settings.registry_path.write_text("{ truncated", encoding="utf-8")
    with pytest.raises(RegistryError):
        DocumentRegistry(settings.registry_path).all()


def test_failed_write_keeps_previous_file_and_leaves_no_temp_files(registry, settings, monkeypatch):
    registry.add(rec("d1", "keep.pdf"))
    monkeypatch.setattr("os.replace", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        registry.add(rec("d2", "lost.pdf"))
    monkeypatch.undo()
    assert [r.name for r in registry.all()] == ["keep.pdf"]
    assert list(settings.registry_path.parent.glob(".registry-*")) == []


def test_arabic_is_stored_readably_not_escaped(registry, settings):
    registry.add(rec("d1", "تقرير.pdf"))
    assert "تقرير.pdf" in settings.registry_path.read_text(encoding="utf-8")
