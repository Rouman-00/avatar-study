"""SQLite persistence for interview data. One row per answer, written
immediately as it comes in, keyed by participant number so it can later be
joined with the behavioral-trust task and the external questionnaire.
"""
import sqlite3

import config

DB_PATH = config.BASE_DIR / "data" / "study.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                participant_number TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                session_id TEXT PRIMARY KEY,
                participant_number TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                category TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                answered_at TEXT NOT NULL
            )
            """
        )


def upsert_participant(participant_number: str, created_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO participants (participant_number, created_at) VALUES (?, ?)",
            (participant_number, created_at),
        )


def create_session(session_id: str, participant_number: str, started_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO interview_sessions (session_id, participant_number, started_at) VALUES (?, ?, ?)",
            (session_id, participant_number, started_at),
        )


def insert_answer(
    session_id: str,
    category: str,
    question: str,
    answer: str,
    word_count: int,
    answered_at: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO interview_answers
                (session_id, category, question, answer, word_count, answered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, category, question, answer, word_count, answered_at),
        )


def finish_session(session_id: str, finished_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE interview_sessions SET finished_at = ? WHERE session_id = ?",
            (finished_at, session_id),
        )
