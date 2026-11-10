import pytest

from suhail.llm.prompts import NO_ANSWER_TEXT
from suhail.models import Turn
from suhail.rag.pipeline import MAX_QUESTION_CHARS, RagPipeline


@pytest.fixture
def loaded(store):
    store.add_document(
        "leave",
        "leave-policy.pdf",
        ["annual leave is thirty calendar days per year", "sick leave requires a medical report"],
        [2, 5],
    )
    store.add_document("hours", "hours.docx", ["office working hours are eight to four"], [None])
    return store


def test_grounded_answer_cites_document_and_page(loaded, pipeline, generator):
    generator.reply = "ثلاثون يوماً"
    answer = pipeline.answer("how many days of annual leave per year")
    assert answer.grounded and answer.text == "ثلاثون يوماً"
    assert answer.sources[0].doc_name == "leave-policy.pdf" and answer.sources[0].page == 2
    assert answer.latency_ms >= 0


def test_unrelated_question_gets_the_fallback_without_calling_the_model(
    loaded, pipeline, generator
):
    answer = pipeline.answer("zzz qqq xxx completely unrelated")
    assert answer.text == NO_ANSWER_TEXT
    assert not answer.grounded and answer.sources == ()
    assert generator.calls == []


def test_empty_knowledge_base_gets_the_fallback(pipeline, generator):
    assert pipeline.answer("anything at all").text == NO_ANSWER_TEXT
    assert generator.calls == []


def test_only_relevant_chunks_reach_the_prompt(loaded, pipeline, generator):
    pipeline.answer("annual leave days")
    user_prompt = generator.calls[0][-1]["content"]
    assert "annual leave is thirty" in user_prompt
    assert "office working hours" not in user_prompt


def test_history_is_included_and_limited_to_two_turns(loaded, pipeline, generator):
    history = [Turn(f"q{i}", f"a{i}") for i in range(5)]
    pipeline.answer("annual leave days", history)
    roles = [m["role"] for m in generator.calls[0]]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]
    assert generator.calls[0][1]["content"] == "q3"


def test_model_self_assessment_is_stripped(loaded, pipeline, generator):
    generator.reply = "ثلاثون يوماً. هذه الإجابة دقيقة وكاملة."
    assert pipeline.answer("annual leave days").text == "ثلاثون يوماً."


def test_sources_are_unique_per_document_and_page(store, generator):
    store.add_document(
        "d", "doc.pdf", ["leave alpha one", "leave alpha two", "leave alpha three"], [1, 1, 2]
    )
    pipe = RagPipeline(store, generator, assistant_name="س", top_k=6, similarity_threshold=1.45)
    sources = pipe.answer("leave alpha").sources
    assert sorted((s.doc_name, s.page) for s in sources) == [("doc.pdf", 1), ("doc.pdf", 2)]


@pytest.mark.parametrize("bad", ["", "   \n", "x" * (MAX_QUESTION_CHARS + 1)])
def test_invalid_questions_are_rejected(pipeline, bad):
    with pytest.raises(ValueError):
        pipeline.answer(bad)


def test_generator_failures_propagate_to_the_caller(loaded, store):
    from tests.fakes import FakeGenerator

    pipe = RagPipeline(
        store,
        FakeGenerator(error=RuntimeError("gpu oom")),
        assistant_name="س",
        top_k=4,
        similarity_threshold=1.2,
    )
    with pytest.raises(RuntimeError, match="gpu oom"):
        pipe.answer("annual leave days")


def test_logs_contain_metadata_but_never_the_question_text(loaded, pipeline, caplog):
    secret = "annual leave days confidential"
    with caplog.at_level("INFO", logger="suhail.rag.pipeline"):
        pipeline.answer(secret)
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "grounded=True" in logged and "nearest_distance" in logged
    assert "confidential" not in logged
