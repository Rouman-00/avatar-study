"""Evaluation of interview answers. Currently just a word counter -- the
place to extend if more metrics are needed later.
"""


def count_words(text: str) -> int:
    return len(text.split())
