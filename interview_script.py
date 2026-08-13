"""Interview script: the concrete questions, category intros, and transition
phrases spoken by the avatar. This is the only file to edit to change what
the interviewer asks -- interview.py just plays it back.
"""

INTRODUCTION = (
    "Hello, and thank you for taking part in this study. I'm your interviewer "
    "for today, and I'll be asking you a few questions. There are no right or "
    "wrong answers -- please just answer as honestly as you can. Let's get started."
)

CLOSING = (
    "That was the last question. Thank you very much for your time and for "
    "your honest answers -- they are a great help for this study."
)

# Short, varied phrases said after each answer, before moving on to the next
# question. Cycled round-robin so it feels natural without being random.
TRANSITIONS = [
    "Thank you.",
    "Got it, thank you.",
    "Thanks for sharing that.",
    "Alright, thank you.",
]

# Category blocks, in the order they are asked. Each category can optionally
# have an "intro" sentence that is read once, right before its first
# question (e.g. explaining an answer format that differs from other
# categories).
CATEGORIES = [
    {
        "name": "satisfaction",
        "intro": None,
        "questions": [
            "How satisfied are you with what you have? Think of money, income and things you own.",
            "How satisfied are you with your health?",
            "How satisfied are you with your family life?",
        ],
    },
    {
        "name": "big_five",
        "intro": (
            "Now a few statements about your personality. To what extent do the "
            "following statements apply to you? Please tell me for each statement "
            "whether it does not apply to you at all, rather not apply, partly "
            "apply, rather apply, or apply completely."
        ),
        "questions": [
            "I am quite cautious, reserved.",
            "I tend to be critical of other people.",
            "I am thorough when completing my tasks.",
            "I tend to feel depressed, blue.",
            "I show a lot of enthusiasm and can easily inspire others.",
        ],
    },
    {
        "name": "health",
        "intro": None,
        "questions": [
            "Now thinking about your physical health, for how many days during "
            "the past 30 days was your physical health not good?",
        ],
    },
]

# Brief lead-in said once when moving from the previous category into this
# one (in addition to/instead of a category "intro" above). Keep these short
# -- one sentence, not a speech.
CATEGORY_TRANSITIONS = {
    "big_five": "Let's move on to a different set of questions.",
    "health": "One last topic.",
}


def build_steps() -> list[dict]:
    """Flatten CATEGORIES into an ordered list of interview steps.

    Each step is a dict with:
      - category: category name
      - question: the question text itself
      - lead_in: text to speak right before the question (category
        transition + category intro, combined). Only set on the first
        question of a category -- later questions in the same category rely
        on the per-answer TRANSITIONS phrase instead.
    """
    steps = []
    for cat_index, category in enumerate(CATEGORIES):
        lead_in_parts = []
        if cat_index > 0:
            cat_transition = CATEGORY_TRANSITIONS.get(category["name"])
            if cat_transition:
                lead_in_parts.append(cat_transition)
        if category.get("intro"):
            lead_in_parts.append(category["intro"])

        for q_index, question in enumerate(category["questions"]):
            steps.append(
                {
                    "category": category["name"],
                    "question": question,
                    "lead_in": " ".join(lead_in_parts) if q_index == 0 else "",
                }
            )
    return steps
