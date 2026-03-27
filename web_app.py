import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import streamlit as st

from ai_setuk_generator import TopicResult, UserProfile, load_topic_bank, local_generate, render_markdown
from integrations.google_sheets import append_personal_row, append_result_rows, check_google_sheet_ready
from utils.history_store import get_recent_history, save_history_event
from utils.local_db import DB_PATH, init_db, save_submission
from utils.material_extractor import build_material_index
from utils.openai_enhancer import has_openai_key
from utils.pdf_export import markdown_to_pdf_bytes


BRAND_OPTIONS = [
    "대치 수프리마 교과탐구",
    "수프리마 탐구설계 랩",
    "수프리마 세특 스튜디오",
]


def _bootstrap_env_from_secrets() -> None:
    cwd_secret = Path.cwd() / ".streamlit" / "secrets.toml"
    home_secret = Path.home() / ".streamlit" / "secrets.toml"
    if not cwd_secret.exists() and not home_secret.exists():
        return
    try:
        secrets = dict(st.secrets)
    except Exception:
        return
    for key in [
        "APPS_SCRIPT_WEB_APP_URL",
        "APPS_SCRIPT_TOKEN",
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "GOOGLE_SHEETS_ID",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ]:
        if key not in os.environ and key in secrets:
            os.environ[key] = str(secrets.get(key, ""))


def _inject_style() -> None:
    st.markdown(
        """
<style>
.hero-box {padding: 18px 20px; border-radius: 14px; background: linear-gradient(135deg,#0f1f3a 0%,#15355f 100%); color: #f5f8ff;}
.hero-title {font-size: 34px; font-weight: 800; margin-bottom: 4px;}
.hero-sub {font-size: 15px; opacity: 0.95;}
.report-card {border:1px solid #d9e1ee; border-radius: 12px; padding: 14px; background:#fbfdff;}
</style>
        """,
        unsafe_allow_html=True,
    )


def validate_required_fields(payload: Dict[str, str]) -> List[str]:
    missing = []
    for key, label in [
        ("teacher_name", "교사명"),
        ("teacher_school", "학교명"),
        ("student_name", "학생 이름"),
        ("student_phone", "학생 전화연락처"),
        ("student_email", "학생 메일주소"),
        ("parent_phone", "학부모 연락처"),
        ("grade", "학년"),
        ("subject", "과목"),
    ]:
        if not payload.get(key, "").strip():
            missing.append(label)
    return missing


def _render_result_detail(result: TopicResult) -> None:
    st.markdown("<div class='report-card'>", unsafe_allow_html=True)
    st.markdown(f"**[주제명]** {result.topic_title}")
    st.markdown(f"**[탐구활동 내용]** {result.topic_direction}")
    st.markdown("---")
    st.markdown("**[도서명/참고도서]**")
    for x in result.books or ["없음"]:
        st.write(f"- {x}")
    st.markdown("**[참고 논문/학술자료]**")
    for x in result.papers or ["없음"]:
        st.write(f"- {x}")
    st.markdown("**[참고 자료/사이트]**")
    for x in result.data_sources or ["없음"]:
        st.write(f"- {x}")
    st.markdown("---")
    st.markdown(f"**[탐구 결론]** {result.expected_conclusion}")
    st.markdown(f"**[세특 문장]** {result.setuk_sentence}")
    st.markdown("</div>", unsafe_allow_html=True)


def _single_result_markdown(profile: UserProfile, result: TopicResult, brand: str) -> str:
    lines = [
        f"# {brand} 보고서",
        "",
        f"[학생] {profile.student_name}",
        f"[학년] {profile.grade}",
        f"[과목] {profile.subject}",
        f"[관심 키워드] {', '.join(profile.interests) if profile.interests else '없음'}",
        f"[진로 힌트] {profile.career_hint}",
        "",
        "## 선택 주제 상세",
        f"[주제명] {result.topic_title}",
        f"[탐구활동 내용] {result.topic_direction}",
        "",
        "[도서명/참고도서]",
    ]
    lines.extend([f"- {x}" for x in result.books] or ["- 없음"])
    lines.extend(["", "[참고 논문/학술자료]"])
    lines.extend([f"- {x}" for x in result.papers] or ["- 없음"])
    lines.extend(["", "[참고 자료/사이트]"])
    lines.extend([f"- {x}" for x in result.data_sources] or ["- 없음"])
    lines.extend(["", f"[탐구 결론] {result.expected_conclusion}", f"[세특 문장] {result.setuk_sentence}"])
    return "\n".join(lines)


def main() -> None:
    _bootstrap_env_from_secrets()
    st.set_page_config(page_title="AI 탐구 주제·세특 생성기", layout="wide")
    _inject_style()
    init_db()

    if "generated_packets" not in st.session_state:
        st.session_state.generated_packets = []

    brand = st.selectbox("브랜드", BRAND_OPTIONS, index=0)
    st.markdown(
        f"<div class='hero-box'><div class='hero-title'>{brand}</div>"
        "<div class='hero-sub'>교사용 입력폼 · 주제 추천 선택 · 세특 보고서 다운로드</div></div>",
        unsafe_allow_html=True,
    )

    topic_bank = load_topic_bank()
    subjects = list(topic_bank.keys())
    recent_records = get_recent_history(days=7)
    st.info(f"최근 7일 누적 생성 건수: {len(recent_records)}건")
    st.caption(f"로컬 DB 파일: {DB_PATH}")

    sheet_ready, sheet_reason = check_google_sheet_ready()
    if sheet_ready:
        st.success(f"시트 연동 상태: {sheet_reason}")
    else:
        st.warning(f"시트 연동 미설정: {sheet_reason}")

    openai_ready = has_openai_key()
    st.info("OpenAI 고도화 상태: " + ("활성 가능" if openai_ready else "API 키 없음(로컬 생성 모드)"))

    with st.expander("자료 인덱스 상태", expanded=False):
        if st.button("PDF/HWPX 키워드 인덱스 새로고침"):
            build_material_index(force_refresh=True)
        idx = build_material_index(force_refresh=False)
        total = len(idx.get("items", []))
        extracted = sum(1 for x in idx.get("items", []) if x.get("extract_ok"))
        st.write(f"- 등록 자료: {total}개")
        st.write(f"- 본문 추출 성공: {extracted}개")

    with st.form("teacher_student_form"):
        st.subheader("교사 정보")
        t1, t2 = st.columns(2)
        with t1:
            teacher_name = st.text_input("교사명")
        with t2:
            teacher_school = st.text_input("학교명")

        st.subheader("학생 정보")
        c1, c2 = st.columns(2)
        with c1:
            student_name = st.text_input("학생 이름")
            student_phone = st.text_input("학생 전화연락처")
            parent_phone = st.text_input("학부모 연락처")
        with c2:
            student_email = st.text_input("학생 메일주소")
            grade = st.text_input("학년", placeholder="예: 고1")
            subject = st.selectbox("과목 선택", subjects, index=0)

        st.subheader("탐구 설정")
        interests_raw = st.text_input("관심 키워드 (쉼표 구분)", placeholder="예: 환경, 데이터, 미디어")
        career_hint = st.text_input("희망 진로/관심 분야", placeholder="예: 환경공학")
        recommendation_count = st.slider("추천 주제 개수", min_value=3, max_value=10, value=5, step=1)
        strict_dedup = st.checkbox("완전 중복 금지(같은 원주제 최대 2개)", value=True)
        use_openai = st.checkbox("OpenAI로 세특 문장 고도화", value=openai_ready)
        submitted = st.form_submit_button("추천 생성")

    if submitted:
        payload = {
            "teacher_name": teacher_name,
            "teacher_school": teacher_school,
            "student_name": student_name,
            "student_phone": student_phone,
            "student_email": student_email,
            "parent_phone": parent_phone,
            "grade": grade,
            "subject": subject,
        }
        missing = validate_required_fields(payload)
        if missing:
            st.error("필수 항목 누락: " + ", ".join(missing))
            return

        interests = [x.strip() for x in interests_raw.split(",") if x.strip()]
        profile = UserProfile(
            student_name=student_name.strip(),
            grade=grade.strip(),
            subject=subject,
            interests=interests,
            career_hint=career_hint.strip() or "융합 탐구",
        )

        results = local_generate(
            profile=profile,
            topic_bank=topic_bank,
            use_openai=use_openai,
            recommendation_count=recommendation_count,
            strict_dedup=strict_dedup,
        )
        if not results:
            st.error("과목 데이터가 없어 생성할 수 없습니다.")
            return

        created_at = datetime.now().isoformat(timespec="seconds")
        packet = {
            "created_at": created_at,
            "brand": brand,
            "teacher_name": teacher_name.strip(),
            "teacher_school": teacher_school.strip(),
            "student_name": student_name.strip(),
            "school_name": teacher_school.strip(),
            "student_phone": student_phone.strip(),
            "student_email": student_email.strip(),
            "parent_phone": parent_phone.strip(),
            "grade": grade.strip(),
            "subject": subject,
            "interests": interests,
            "career_hint": profile.career_hint,
            "result_count": len(results),
            "results": [asdict(r) for r in results],
            "profile": asdict(profile),
        }
        st.session_state.generated_packets.append(packet)
        save_history_event(packet)
        save_submission(packet)
        st.success(f"{student_name} 학생 추천 {len(results)}건이 생성되었습니다. 목록에서 1개를 선택해 상세를 확인하세요.")

        if sheet_ready:
            try:
                append_personal_row(
                    created_at=created_at,
                    student_name=packet["student_name"],
                    school_name=packet["school_name"],
                    student_phone=packet["student_phone"],
                    student_email=packet["student_email"],
                    parent_phone=packet["parent_phone"],
                    grade=packet["grade"],
                    teacher_name=packet["teacher_name"],
                )
                append_result_rows(
                    created_at=created_at,
                    student_name=packet["student_name"],
                    school_name=packet["school_name"],
                    subject=packet["subject"],
                    interests=packet["interests"],
                    career_hint=packet["career_hint"],
                    results=[TopicResult(**r) for r in packet["results"]],
                    teacher_name=packet["teacher_name"],
                )
                st.info("구글시트 저장 완료 (개인정보 + 생성결과)")
            except Exception as exc:
                st.warning(f"구글시트 저장 실패: {exc}")

    st.subheader("학생별 생성 결과")
    if not st.session_state.generated_packets:
        st.write("아직 생성된 학생 결과가 없습니다.")
    else:
        for idx, packet in enumerate(reversed(st.session_state.generated_packets), start=1):
            title = (
                f"{idx}. {packet['student_name']} | {packet['grade']} | {packet['subject']} | "
                f"{packet['created_at']}"
            )
            with st.expander(title, expanded=(idx == 1)):
                results = [TopicResult(**r) for r in packet["results"]]
                options = [f"{i+1}. {r.topic_title}" for i, r in enumerate(results)]
                selected_label = st.radio(
                    "추천 주제 목록",
                    options=options,
                    index=0,
                    key=f"radio_{idx}_{packet['created_at']}",
                )
                selected_idx = options.index(selected_label)
                selected_result = results[selected_idx]
                _render_result_detail(selected_result)

                profile = UserProfile(**packet["profile"])
                single_md = _single_result_markdown(profile, selected_result, packet.get("brand", brand))
                all_md = render_markdown(profile, results)
                single_pdf = markdown_to_pdf_bytes(single_md, title=f"{packet['brand']} 선택 주제 보고서")
                all_pdf = markdown_to_pdf_bytes(all_md, title=f"{packet['brand']} 전체 추천 보고서")
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                c1, c2 = st.columns(2)
                with c1:
                    if single_pdf.startswith(b"%PDF"):
                        st.download_button(
                            label="선택 주제 PDF 다운로드",
                            data=single_pdf,
                            file_name=f"{packet['student_name']}_{packet['subject']}_선택_{stamp}.pdf",
                            mime="application/pdf",
                            key=f"single_pdf_{idx}",
                        )
                with c2:
                    if all_pdf.startswith(b"%PDF"):
                        st.download_button(
                            label="전체 추천 PDF 다운로드",
                            data=all_pdf,
                            file_name=f"{packet['student_name']}_{packet['subject']}_전체_{stamp}.pdf",
                            mime="application/pdf",
                            key=f"all_pdf_{idx}",
                        )

    with st.expander("최근 7일 누적 로그", expanded=False):
        rows = get_recent_history(days=7)
        if not rows:
            st.write("최근 7일 기록이 없습니다.")
        else:
            for i, row in enumerate(reversed(rows), start=1):
                st.write(
                    f"{i}. {row.get('created_at')} | {row.get('student_name')} | "
                    f"{row.get('subject')} | 결과 {row.get('result_count')}건"
                )


if __name__ == "__main__":
    main()
