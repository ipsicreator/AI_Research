import json
import os
import urllib.error
import urllib.request
from typing import Dict, List


def _resolve_openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key

    alias = os.getenv("OPENAPI_API_KEY", "").strip()
    if alias:
        os.environ["OPENAI_API_KEY"] = alias
        return alias

    # Streamlit Cloud: support both flat and section-style secrets.
    try:
        import streamlit as st  # type: ignore

        sec = st.secrets
        candidates = [
            sec.get("OPENAI_API_KEY", ""),
            sec.get("OPENAPI_API_KEY", ""),
            sec.get("openai_api_key", ""),
        ]
        if "openai" in sec:
            openai_section = sec.get("openai", {})
            if isinstance(openai_section, dict):
                candidates.extend(
                    [
                        openai_section.get("api_key", ""),
                        openai_section.get("OPENAI_API_KEY", ""),
                    ]
                )
        for c in candidates:
            v = str(c).strip()
            if v:
                os.environ["OPENAI_API_KEY"] = v
                return v
    except Exception:
        pass
    return ""


def _resolve_openai_model() -> str:
    model = os.getenv("OPENAI_MODEL", "").strip()
    if model:
        return model
    try:
        import streamlit as st  # type: ignore

        sec = st.secrets
        m1 = str(sec.get("OPENAI_MODEL", "")).strip()
        if m1:
            os.environ["OPENAI_MODEL"] = m1
            return m1
        if "openai" in sec:
            openai_section = sec.get("openai", {})
            if isinstance(openai_section, dict):
                m2 = str(openai_section.get("model", "")).strip()
                if m2:
                    os.environ["OPENAI_MODEL"] = m2
                    return m2
    except Exception:
        pass
    return "gpt-5.4-mini"


def has_openai_key() -> bool:
    return bool(_resolve_openai_key())


def refine_setuk_sentences(
    student_name: str,
    subject: str,
    career_hint: str,
    rows: List[Dict[str, str]],
) -> List[str]:
    api_key = _resolve_openai_key()
    if not api_key:
        return [r.get("setuk_sentence", "") for r in rows]

    model = _resolve_openai_model()
    system_prompt = (
        "당신은 한국 고교 생활기록부 세부능력특기사항 문장 작성 보조자다. "
        "교사 서술형 톤으로 과장 없이, 완결된 문장 1~2문장으로 작성한다."
    )

    results: List[str] = []
    for r in rows:
        draft = r.get("setuk_sentence", "").strip()
        user_payload = {
            "student_name": student_name,
            "subject": subject,
            "career_hint": career_hint,
            "topic_title": r.get("topic_title", ""),
            "topic_direction": r.get("topic_direction", ""),
            "expected_conclusion": r.get("expected_conclusion", ""),
            "draft": draft,
            "rules": [
                "관찰-과정-성과-확장 흐름 유지",
                "개조식 금지, 완결된 문장",
                "민감정보/과장/단정 표현 금지",
                "결과는 본문만 출력(설명/머리말 금지)",
            ],
        }

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.4,
            "max_completion_tokens": 500,
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

        refined = draft
        try:
            with urllib.request.urlopen(req, timeout=45) as res:
                raw = res.read().decode("utf-8", errors="ignore")
            parsed = json.loads(raw)
            content = str(parsed["choices"][0]["message"]["content"]).strip()
            # Basic completeness guard to reduce mid-cut display.
            if content:
                if content[-1] not in [".", "!", "?", "다", "요"]:
                    content = content.rstrip() + "."
                refined = content
        except (KeyError, ValueError, TypeError, urllib.error.URLError, urllib.error.HTTPError):
            refined = draft
        results.append(refined)

    return results
