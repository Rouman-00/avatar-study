"""Interview session state machine, persistence, and the FastAPI routes that
drive it. The actual questions live in interview_script.py, the scoring
logic in interview_evaluation.py -- this module only manages state and I/O.
"""
import csv
import itertools
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
import interview_evaluation
import interview_script

router = APIRouter(prefix="/interview", tags=["interview"])

DATA_DIR = config.BASE_DIR / "data" / "interviews"
SUMMARY_CSV = DATA_DIR / "summary.csv"

_sessions: dict[str, "InterviewSession"] = {}
_transition_cycle = itertools.cycle(interview_script.TRANSITIONS)


class InterviewSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.steps = interview_script.build_steps()
        self.current_step = 0
        self.answers: list[dict] = []

    def current_question_text(self) -> str:
        step = self.steps[self.current_step]
        return " ".join(part for part in (step["lead_in"], step["question"]) if part)

    def record_answer(self, message: str) -> None:
        step = self.steps[self.current_step]
        self.answers.append(
            {"category": step["category"], "question": step["question"], "answer": message}
        )

    def is_finished(self) -> bool:
        return self.current_step >= len(self.steps)

    def advance(self) -> None:
        self.current_step += 1


def start_session() -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    session = InterviewSession(session_id)
    _sessions[session_id] = session
    text = interview_script.INTRODUCTION + " " + session.current_question_text()
    return session_id, text


def submit_answer(session_id: str, message: str) -> tuple[str, bool]:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unbekannte Interview-Session.")
    if session.is_finished():
        raise HTTPException(status_code=400, detail="Interview ist bereits beendet.")

    session.record_answer(message)
    _save_session(session)
    session.advance()

    if session.is_finished():
        _append_summary(session)
        return interview_script.CLOSING, True

    text = next(_transition_cycle) + " " + session.current_question_text()
    return text, False


def _save_session(session: InterviewSession) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    evaluation = interview_evaluation.evaluate_answers(session.answers)
    payload = {"session_id": session.session_id, "started_at": session.started_at, **evaluation}
    path = DATA_DIR / f"{session.session_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_summary(session: InterviewSession) -> None:
    evaluation = interview_evaluation.evaluate_answers(session.answers)
    is_new = not SUMMARY_CSV.exists()
    with SUMMARY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            header = ["session_id", "started_at"]
            header += [f"words_q{i + 1}" for i in range(len(evaluation["answers"]))]
            header += ["total_word_count"]
            writer.writerow(header)
        row = [session.session_id, session.started_at]
        row += [answer["word_count"] for answer in evaluation["answers"]]
        row += [evaluation["total_word_count"]]
        writer.writerow(row)


class AnswerInput(BaseModel):
    session_id: str
    message: str


@router.post("/start")
async def interview_start():
    session_id, text = start_session()
    return {"session_id": session_id, "text": text, "done": False}


@router.post("/answer")
async def interview_answer(payload: AnswerInput):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Leere Antwort.")
    text, done = submit_answer(payload.session_id, message)
    return {"text": text, "done": done}
