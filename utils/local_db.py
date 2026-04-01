import json
import sqlite3
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "app_data.db"


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                brand TEXT,
                teacher_name TEXT,
                teacher_school TEXT,
                student_name TEXT,
                school_name TEXT,
                student_phone TEXT,
                student_email TEXT,
                parent_phone TEXT,
                grade TEXT,
                subject TEXT,
                interests_json TEXT,
                career_hint TEXT,
                result_count INTEGER,
                payload_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS result_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                rank_no INTEGER NOT NULL,
                topic_title TEXT,
                topic_direction TEXT,
                books_json TEXT,
                papers_json TEXT,
                data_sources_json TEXT,
                expected_conclusion TEXT,
                setuk_sentence TEXT,
                FOREIGN KEY(submission_id) REFERENCES submissions(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS consult_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                parent_name TEXT,
                student_name TEXT,
                student_grade TEXT,
                phone TEXT,
                email TEXT,
                preferred_time TEXT,
                note TEXT,
                status TEXT DEFAULT 'new'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_submission(packet: Dict[str, Any], db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO submissions (
                created_at, brand, teacher_name, teacher_school,
                student_name, school_name, student_phone, student_email,
                parent_phone, grade, subject, interests_json,
                career_hint, result_count, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet.get("created_at", ""),
                packet.get("brand", ""),
                packet.get("teacher_name", ""),
                packet.get("teacher_school", ""),
                packet.get("student_name", ""),
                packet.get("school_name", ""),
                packet.get("student_phone", ""),
                packet.get("student_email", ""),
                packet.get("parent_phone", ""),
                packet.get("grade", ""),
                packet.get("subject", ""),
                json.dumps(packet.get("interests", []), ensure_ascii=False),
                packet.get("career_hint", ""),
                int(packet.get("result_count", 0)),
                json.dumps(packet, ensure_ascii=False),
            ),
        )
        submission_id = int(cur.lastrowid)

        for i, row in enumerate(packet.get("results", []), start=1):
            cur.execute(
                """
                INSERT INTO result_items (
                    submission_id, rank_no, topic_title, topic_direction,
                    books_json, papers_json, data_sources_json,
                    expected_conclusion, setuk_sentence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    i,
                    row.get("topic_title", ""),
                    row.get("topic_direction", ""),
                    json.dumps(row.get("books", []), ensure_ascii=False),
                    json.dumps(row.get("papers", []), ensure_ascii=False),
                    json.dumps(row.get("data_sources", []), ensure_ascii=False),
                    row.get("expected_conclusion", ""),
                    row.get("setuk_sentence", ""),
                ),
            )
        conn.commit()
        return submission_id
    finally:
        conn.close()


def save_consult_request(payload: Dict[str, Any], db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO consult_requests (
                created_at, parent_name, student_name, student_grade,
                phone, email, preferred_time, note, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("created_at", ""),
                payload.get("parent_name", ""),
                payload.get("student_name", ""),
                payload.get("student_grade", ""),
                payload.get("phone", ""),
                payload.get("email", ""),
                payload.get("preferred_time", ""),
                payload.get("note", ""),
                payload.get("status", "new"),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()
