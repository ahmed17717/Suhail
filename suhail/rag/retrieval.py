"""Retrieval policy: how a question (plus conversation context) becomes context chunks.

Two searches are run:

* the **plain** question, and
* (for follow-ups) the previous question prepended to it, which rescues terse
  follow-ups such as "and what was the fine?".

They are merged, never substituted. Prepending history to a single query can steer
retrieval entirely away from a self-contained new question ("who is the defendant?"
right after "who is the judge?" would keep re-serving judge chunks). A plain
distance-sorted union is not enough either: enough history-flavoured chunks sitting
closer in the polluted query space would still push the question's own best match
out of the final `top_k`.

So the merge works like this:

1. drop chunks beyond the similarity threshold *first* — irrelevant results must not
   reserve slots;
2. reserve half of the slots for the plain question's best relevant chunks;
3. fill the remaining slots with the closest of everything else;
4. return the result closest-first.

It is a pure function, so the policy is unit-tested without a vector store.
"""

from __future__ import annotations

from collections.abc import Sequence

from suhail.models import RetrievedChunk


def merge_relevant(
    plain: Sequence[RetrievedChunk],
    augmented: Sequence[RetrievedChunk],
    *,
    top_k: int,
    max_distance: float,
) -> list[RetrievedChunk]:
    plain_ok = sorted((c for c in plain if c.distance < max_distance), key=lambda c: c.distance)
    augmented_ok = [c for c in augmented if c.distance < max_distance]

    best: dict[str, RetrievedChunk] = {}
    for chunk in [*plain_ok, *augmented_ok]:
        known = best.get(chunk.id)
        if known is None or chunk.distance < known.distance:
            best[chunk.id] = chunk

    reserved = (top_k + 1) // 2
    chosen = {c.id for c in plain_ok[:reserved]}
    for chunk in sorted(best.values(), key=lambda c: c.distance):
        if len(chosen) >= top_k:
            break
        chosen.add(chunk.id)

    return sorted((best[chunk_id] for chunk_id in chosen), key=lambda c: c.distance)
