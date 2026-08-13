"""Evaluation of interview answers. Currently just word counts (per answer
and total) -- the place to extend if more metrics are needed later.
"""


def count_words(text: str) -> int:
    return len(text.split())


def evaluate_answers(answers: list[dict]) -> dict:
    """answers: list of {"category": str, "question": str, "answer": str}.

    Returns the same answers enriched with a word_count each, plus the total
    word count across all of them.
    """
    scored = [
        {
            "category": answer["category"],
            "question": answer["question"],
            "answer": answer["answer"],
            "word_count": count_words(answer["answer"]),
        }
        for answer in answers
    ]
    total_word_count = sum(answer["word_count"] for answer in scored)
    return {"answers": scored, "total_word_count": total_word_count}
