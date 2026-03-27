import json
import os
import urllib.error
import urllib.request
from typing import Dict, List


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def refine_setuk_sentences(
    student_name: str,
    subject: str,
    career_hint: str,
    rows: List[Dict[str, str]],
) -> List[str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return [r.get("setuk_sentence", "") for r in rows]

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    system_prompt = (
        "당신은 한국 고교 생활기록부 세부능력특기사항 문장 작성 보조자다. "
        "교사 서술형 톤으로, 과장 없이 근거 중심으로 다듬어라."
    )

    user_payload = {
        "student_name": student_name,
        "subject": subject,
        "career_hint": career_hint,
        "rules": [
            "각 항목은 1~2문장으로 작성",
            "관찰-과정-성과-확장 흐름 유지",
            "개조식 금지, 완결된 문장",
            "민감정보/과장/단정 표현 금지",
        ],
        "items": [
            {
                "topic_title": r.get("topic_title", ""),
                "topic_direction": r.get("topic_direction", ""),
                "expected_conclusion": r.get("expected_conclusion", ""),
                "draft": r.get("setuk_sentence", ""),
            }
            for r in rows
        ],
        "output_format": {
            "type": "json",
            "schema": {"sentences": ["string"]},
        },
    }

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8", errors="ignore")
        parsed = json.loads(raw)
        content = parsed["choices"][0]["message"]["content"]
        obj = json.loads(content) if isinstance(content, str) else content
        sentences = obj.get("sentences", [])
        if isinstance(sentences, list) and len(sentences) == len(rows):
            return [str(s).strip() for s in sentences]
    except (KeyError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
        pass

    return [r.get("setuk_sentence", "") for r in rows]
