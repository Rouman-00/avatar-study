"""Interview session state machine and the FastAPI routes that drive it.
Persistence lives in db.py (SQLite), the questions in interview_script.py,
the scoring logic in interview_evaluation.py -- this module only manages
state and wires the pieces together.
"""
import itertools
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
import db
import interview_evaluation
import interview_script

router = APIRouter(prefix="/interview", tags=["interview"])

_sessions: dict[str, "InterviewSession"] = {}
_transition_cycle = itertools.cycle(interview_script.TRANSITIONS)


class InterviewSession:
    def __init__(self, session_id: str, participant_number: str):
        self.session_id = session_id
        self.participant_number = participant_number
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.steps = interview_script.build_steps()
        self.current_step = 0

    def current_question_text(self) -> str:
        step = self.steps[self.current_step]
        return " ".join(part for part in (step["lead_in"], step["question"]) if part)

    def record_answer(self, message: str) -> dict:
        step = self.steps[self.current_step]
        return {"category": step["category"], "question": step["question"], "answer": message}

    def is_finished(self) -> bool:
        return self.current_step >= len(self.steps)

    def advance(self) -> None:
        self.current_step += 1


def start_session(participant_number: str) -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    session = InterviewSession(session_id, participant_number)
    _sessions[session_id] = session

    db.upsert_participant(participant_number, session.started_at)
    db.create_session(session_id, participant_number, session.started_at)

    text = interview_script.INTRODUCTION + " " + session.current_question_text()
    return session_id, text


def submit_answer(session_id: str, message: str) -> tuple[str, bool, str | None]:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unbekannte Interview-Session.")
    if session.is_finished():
        raise HTTPException(status_code=400, detail="Interview ist bereits beendet.")

    answered = session.record_answer(message)
    db.insert_answer(
        session_id=session_id,
        category=answered["category"],
        question=answered["question"],
        answer=answered["answer"],
        word_count=interview_evaluation.count_words(answered["answer"]),
        answered_at=datetime.now().isoformat(timespec="seconds"),
    )
    session.advance()

    if session.is_finished():
        db.finish_session(session_id, datetime.now().isoformat(timespec="seconds"))
        return interview_script.CLOSING, True, _build_survey_url(session.participant_number)

    text = next(_transition_cycle) + " " + session.current_question_text()
    return text, False, None


def _build_survey_url(participant_number: str) -> str | None:
    if not config.SURVEY_URL_TEMPLATE:
        return None
    return config.SURVEY_URL_TEMPLATE.format(participant_number=participant_number)


class StartInput(BaseModel):
    participant_number: str


class AnswerInput(BaseModel):
    session_id: str
    message: str


@router.post("/start")
async def interview_start(payload: StartInput):
    participant_number = payload.participant_number.strip()
    if not participant_number:
        raise HTTPException(status_code=400, detail="Teilnehmernummer fehlt.")
    session_id, text = start_session(participant_number)
    return {"session_id": session_id, "text": text, "done": False}


@router.post("/answer")
async def interview_answer(payload: AnswerInput):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Leere Antwort.")
    text, done, survey_url = submit_answer(payload.session_id, message)
    return {"text": text, "done": done, "survey_url": survey_url}
