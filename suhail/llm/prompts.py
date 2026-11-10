"""Prompt construction — pure functions, no model, no I/O (so fully unit-testable).

The system prompt is in Arabic because the product is Arabic-first. Its contract:
answer *only* from the supplied context, say so plainly when the context doesn't
contain the answer, never invent, and format multi-part answers as lists.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from suhail.models import Turn

NO_ANSWER_TEXT = "لا تتوفر لدي معلومات كافية للإجابة على هذا السؤال من البيانات المتاحة."

_SYSTEM_PROMPT_TEMPLATE = (
    "اسمك {name}، وأنت المساعد الافتراضي الداخلي للشركة. "
    "إذا سُئلت عن اسمك أو هويتك أو من أنت، عرّف عن نفسك باسم {name}. "
    "أجب فقط بناءً على المعلومات المرفقة في رسالة المستخدم. "
    "إذا لم تجد إجابة واضحة في تلك المعلومات، قل بوضوح: "
    f"'{NO_ANSWER_TEXT}' "
    "لا تستخدم أي معرفة عامة خارج المعلومات المرفقة. لا تخترع معلومات. "
    "أجب بإجابة واحدة مباشرة فقط، ولا تقترح أسئلة أخرى ولا تكمل المحادثة نيابة عن المستخدم. "
    "إذا كانت الإجابة تحتوي على عدة عناصر أو خطوات أو نقاط، نظمها في نقاط "
    "(باستخدام - في بداية كل سطر) أو قائمة مرقمة بدلاً من كتابتها كفقرة متصلة. "
    "إذا كانت الإجابة جملة واحدة بسيطة، اكتبها كجملة عادية دون تنسيق إضافي."
)


def system_prompt(assistant_name: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(name=assistant_name)


def build_messages(
    assistant_name: str,
    question: str,
    context_chunks: Sequence[str],
    history: Sequence[Turn] = (),
) -> list[dict[str, str]]:
    """Chat messages: system prompt, recent turns, then context + the new question."""
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt(assistant_name)}]
    for turn in history:
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})

    context = "\n\n".join(context_chunks)
    messages.append(
        {"role": "user", "content": f"المعلومات المتاحة:\n{context}\n\nالسؤال: {question}"}
    )
    return messages


# The model occasionally appends a self-assessment ("هذه الإجابة ...") after the
# answer. It is noise for the reader, so everything from that phrase on is dropped.
_SELF_CHECK = re.compile(r"(هذه|هذا)\s+ال[إا]جابة.*", re.DOTALL)


def clean_answer(text: str) -> str:
    match = _SELF_CHECK.search(text)
    if match:
        text = text[: match.start()]
    return text.strip()
