from suhail.llm.prompts import NO_ANSWER_TEXT, build_messages, clean_answer, system_prompt
from suhail.models import Turn


def test_system_prompt_names_the_assistant_and_embeds_the_fallback_sentence():
    prompt = system_prompt("سهيل")
    assert "اسمك سهيل" in prompt and NO_ANSWER_TEXT in prompt
    assert "/no_think" not in prompt


def test_message_order_and_context_placement():
    msgs = build_messages("سهيل", "ما هو؟", ["chunk A", "chunk B"], [Turn("q", "a")])
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "المعلومات المتاحة:\nchunk A\n\nchunk B\n\nالسؤال: ما هو؟"


def test_clean_answer_strips_trailing_self_assessment():
    assert clean_answer("الجواب هنا.\nهذه الإجابة صحيحة تماماً") == "الجواب هنا."
    assert clean_answer("  الجواب هنا  ") == "الجواب هنا"
    assert clean_answer("هذا الاجابة") == ""
