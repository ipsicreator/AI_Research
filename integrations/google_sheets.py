import json
import os
import urllib.error
import urllib.request
from typing import List, Tuple

from ai_setuk_generator import TopicResult


PERSONAL_SHEET_NAME = "개인정보"
RESULT_SHEET_NAME = "생성결과"


def _apps_script_url() -> str:
    return os.getenv("APPS_SCRIPT_WEB_APP_URL", "").strip()


def _apps_script_token() -> str:
    return os.getenv("APPS_SCRIPT_TOKEN", "").strip()


def check_google_sheet_ready() -> Tuple[bool, str]:
    apps_script_url = _apps_script_url()
    if apps_script_url:
        return True, "Apps Script Web App 모드"

    service_account = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    sheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    if not service_account:
        return False, "APPS_SCRIPT_WEB_APP_URL 또는 GOOGLE_SERVICE_ACCOUNT_FILE 설정이 필요합니다."
    if not sheet_id:
        return False, "GOOGLE_SHEETS_ID 환경변수가 없습니다."
    if not os.path.exists(service_account):
        return False, f"서비스 계정 파일이 없습니다: {service_account}"
    return True, "Service Account 모드"


def _post_apps_script(payload: dict) -> None:
    url = _apps_script_url()
    if not url:
        raise RuntimeError("APPS_SCRIPT_WEB_APP_URL이 비어 있습니다.")

    body = dict(payload)
    token = _apps_script_token()
    if token:
        body["token"] = token

    request = urllib.request.Request(
        url=url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            if response.status >= 300:
                raise RuntimeError(f"Apps Script HTTP {response.status}: {raw}")
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    snippet = raw[:180].replace("\n", " ")
                    raise RuntimeError(
                        "Apps Script가 JSON 대신 HTML/오류 페이지를 반환했습니다. "
                        "배포 권한(링크가 있는 모든 사용자)과 웹앱 URL(/exec)을 확인하세요. "
                        f"응답 일부: {snippet}"
                    )
                if not parsed.get("ok", False):
                    raise RuntimeError(f"Apps Script 응답 오류: {raw}")
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Apps Script HTTPError {exc.code}: {message}") from exc


def _open_sheet(sheet_name: str):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    service_account = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    sheet_id = os.environ["GOOGLE_SHEETS_ID"]
    creds = Credentials.from_service_account_file(service_account, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    return worksheet


def append_personal_row(
    created_at: str,
    student_name: str,
    school_name: str,
    student_phone: str,
    student_email: str,
    parent_phone: str,
    grade: str,
    teacher_name: str = "",
) -> None:
    row = [created_at, student_name, school_name, student_phone, student_email, parent_phone, grade, teacher_name]
    headers = [
        "created_at",
        "student_name",
        "school_name",
        "student_phone",
        "student_email",
        "parent_phone",
        "grade",
        "teacher_name",
    ]

    if _apps_script_url():
        _post_apps_script(
            {
                "sheet_name": PERSONAL_SHEET_NAME,
                "headers": headers,
                "rows": [row],
            }
        )
        return

    ws = _open_sheet(PERSONAL_SHEET_NAME)
    if ws.acell("A1").value != "created_at":
        ws.update("A1:H1", [headers])
    ws.append_row(row, value_input_option="USER_ENTERED")


def append_result_rows(
    created_at: str,
    student_name: str,
    school_name: str,
    subject: str,
    interests: List[str],
    career_hint: str,
    results: List[TopicResult],
    teacher_name: str = "",
) -> None:
    headers = [
        "created_at",
        "student_name",
        "school_name",
        "teacher_name",
        "subject",
        "interests",
        "career_hint",
        "topic_title",
        "topic_direction",
        "books",
        "papers",
        "data_sources",
        "expected_conclusion",
        "setuk_sentence",
    ]
    interest_text = ", ".join(interests)
    rows = [
        [
            created_at,
            student_name,
            school_name,
            teacher_name,
            subject,
            interest_text,
            career_hint,
            row.topic_title,
            row.topic_direction,
            " | ".join(row.books),
            " | ".join(row.papers),
            " | ".join(row.data_sources),
            row.expected_conclusion,
            row.setuk_sentence,
        ]
        for row in results
    ]

    if _apps_script_url():
        _post_apps_script(
            {
                "sheet_name": RESULT_SHEET_NAME,
                "headers": headers,
                "rows": rows,
            }
        )
        return

    ws = _open_sheet(RESULT_SHEET_NAME)
    if ws.acell("A1").value != "created_at":
        ws.update("A1:N1", [headers])
    ws.append_rows(rows, value_input_option="USER_ENTERED")
