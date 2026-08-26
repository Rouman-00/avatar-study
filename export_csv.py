"""Dumps the interview_answers table (joined with session/participant info)
to a CSV for statistical analysis (R/SPSS/JASP). Run after data collection:

    python export_csv.py
"""
import csv
import sqlite3

import config
import db

OUTPUT_PATH = config.BASE_DIR / "data" / "interview_answers_export.csv"

QUERY = """
    SELECT
        p.participant_number,
        s.session_id,
        s.started_at,
        s.finished_at,
        a.category,
        a.question,
        a.answer,
        a.word_count,
        a.answered_at
    FROM interview_answers a
    JOIN interview_sessions s ON s.session_id = a.session_id
    JOIN participants p ON p.participant_number = s.participant_number
    ORDER BY p.participant_number, s.started_at, a.id
"""


def main() -> None:
    with sqlite3.connect(db.DB_PATH) as conn:
        cursor = conn.execute(QUERY)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"{len(rows)} Antworten exportiert nach {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
