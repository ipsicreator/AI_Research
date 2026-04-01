import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import streamlit as st

from ai_setuk_generator import TopicResult, UserProfile, load_topic_bank, local_generate, render_markdown
from utils.history_store import get_recent_history, save_history_event
from utils.local_db import DB_PATH, init_db, save_consult_request, save_submission
from utils.material_extractor import build_material_index
from utils.openai_enhancer import has_openai_key
from utils.pdf_export import markdown_to_pdf_bytes


BRAND_NAME = "수프리마 AI 탐구·세특 생성기"
DISPLAY_COUNT_START = 10


def _bootstrap_env_from_secrets() -> None:
    cwd_secret = Path.cwd() / ".streamlit" / "secrets.toml"
    home_secret = Path.home() / ".streamlit" / "secrets.toml"
    if not cwd_secret.exists() and not home_secret.exists():
        return
    try:
        secrets = dict(st.secrets)
    except Exception:
        return

    for key in ["OPENAI_API_KEY", "OPENAPI_API_KEY", "openai_api_key", "OPENAI_MODEL"]:
        if key not in os.environ and key in secrets:
            os.environ[key] = str(secrets.get(key, ""))

    openai_section = secrets.get("openai", {})
    if isinstance(openai_section, dict):
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            section_key = str(openai_section.get("api_key", "")).strip()
            if section_key:
                os.environ["OPENAI_API_KEY"] = section_key
        if not os.environ.get("OPENAI_MODEL", "").strip():
            section_model = str(openai_section.get("model", "")).strip()
            if section_model:
                os.environ["OPENAI_MODEL"] = section_model

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        alias = os.environ.get("OPENAPI_API_KEY", "").strip()
        if alias:
            os.environ["OPENAI_API_KEY"] = alias


def _inject_style(ui_scale: float = 1.0, page_max_width: int = 1200) -> None:
    css = """
<style>
:root {
  --ui-scale: __UI_SCALE__;
  --page-max: __PAGE_MAX__px;
}
section.main > div.block-container {
  max-width: var(--page-max);
  margin-left: auto;
  margin-right: auto;
}
.hero-box {
  padding: calc(20px * var(--ui-scale));
  border-radius: calc(14px * var(--ui-scale));
  background: linear-gradient(135deg, #0b1e41 0%, #1a4a9a 100%);
  color: #f8fbff;
}
.hero-title {font-size: calc(30px * var(--ui-scale)); font-weight: 800; margin-bottom: 4px;}
.hero-sub {font-size: calc(14px * var(--ui-scale)); opacity: 0.95;}
.portal-card {
  border: 1px solid #dce5f5;
  border-radius: calc(16px * var(--ui-scale));
  padding: calc(18px * var(--ui-scale));
  background: linear-gradient(180deg, #f8fbff 0%, #f3f8ff 100%);
  min-height: calc(220px * var(--ui-scale));
}
.portal-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: #e8f0ff;
  color: #1f4aa8;
  font-size: calc(12px * var(--ui-scale));
  margin-bottom: 10px;
}
.portal-title {font-size: calc(24px * var(--ui-scale)); font-weight: 800; color: #0b1f42; margin-bottom: 8px;}
.portal-sub {font-size: calc(14px * var(--ui-scale)); color: #2f4469; margin-bottom: 14px;}
.report-card {
  border: 1px solid #d9e1ee;
  border-radius: calc(12px * var(--ui-scale));
  padding: calc(14px * var(--ui-scale));
  background: #fbfdff;
}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
  min-height: calc(42px * var(--ui-scale)) !important;
  border-radius: calc(10px * var(--ui-scale)) !important;
}
</style>
"""
    css = css.replace("__UI_SCALE__", f"{ui_scale:.2f}").replace("__PAGE_MAX__", str(page_max_width))
    st.markdown(css, unsafe_allow_html=True)


def validate_required_fields(payload: Dict[str, str]) -> List[str]:
    missing = []
    required = [
        ("consultant_name", "담당컨설턴트"),
        ("school_name", "학교명"),
        ("student_name", "학생 이름"),
        ("student_phone", "학생 연락처"),
        ("student_email", "학생 메일"),
        ("parent_phone", "학부모 연락처"),
        ("grade", "학년"),
        ("subject", "과목"),
        ("career_hint", "진로/학과"),
    ]
    for key, label in required:
        if not payload.get(key, "").strip():
            missing.append(label)
    return missing


def _render_result_detail(result: TopicResult) -> None:
    st.markdown("<div class='report-card'>", unsafe_allow_html=True)
    st.markdown(f"**주제명**: {result.topic_title}")
    st.markdown(f"**탐구활동 내용**: {result.topic_direction}")
    st.markdown("---")
    st.markdown("**참고 도서**")
    for x in result.books or ["없음"]:
        st.write(f"- {x}")
    st.markdown("**참고 논문/학술자료**")
    for x in result.papers or ["없음"]:
        st.write(f"- {x}")
    st.markdown("**참고 데이터/사이트**")
    for x in result.data_sources or ["없음"]:
        st.write(f"- {x}")
    st.markdown("---")
    st.markdown(f"**탐구 결론**: {result.expected_conclusion}")
    st.markdown(f"**세특 문장**: {result.setuk_sentence}")
    st.markdown("</div>", unsafe_allow_html=True)


def _single_result_markdown(profile: UserProfile, result: TopicResult, brand: str) -> str:
    lines = [
        f"# {brand} 보고서",
        "",
        f"[학생] {profile.student_name}",
        f"[학년] {profile.grade}",
        f"[과목] {profile.subject}",
        f"[관심키워드] {', '.join(profile.interests) if profile.interests else '없음'}",
        f"[진로 힌트] {profile.career_hint}",
        "",
        "## 선택 주제 상세",
        f"[주제명] {result.topic_title}",
        f"[탐구활동 내용] {result.topic_direction}",
        "",
        "[참고 도서]",
    ]
    lines.extend([f"- {x}" for x in result.books] or ["- 없음"])
    lines.extend(["", "[참고 논문/학술자료]"])
    lines.extend([f"- {x}" for x in result.papers] or ["- 없음"])
    lines.extend(["", "[참고 데이터/사이트]"])
    lines.extend([f"- {x}" for x in result.data_sources] or ["- 없음"])
    lines.extend(["", f"[탐구 결론] {result.expected_conclusion}", f"[세특 문장] {result.setuk_sentence}"])
    return "\n".join(lines)


def _render_service_shortcuts(current_view: str) -> None:
    st.markdown("#### 서비스 안내 및 바로가기")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**1. 나의 입시 위치 진단**")
        st.caption("학생부/컷 기반 진단")
        if current_view != "admission":
            if st.button("1번으로 이동", key=f"jump_admission_{current_view}", use_container_width=True):
                st.session_state.portal_view = "admission"
                st.rerun()
        else:
            st.success("현재 1번 서비스 이용 중")

    with c2:
        st.markdown("**2. AI탐구·세특 생성기**")
        st.caption("탐구 주제 및 세특 문장")
        if current_view != "setuk":
            if st.button("2번으로 이동", key=f"jump_setuk_{current_view}", use_container_width=True):
                st.session_state.portal_view = "setuk"
                st.rerun()
        else:
            st.success("현재 2번 서비스 이용 중")

    with c3:
        st.markdown("**3. 대치수프리마 입시 컨설팅 신청**")
        st.caption("신청 접수 후 후속 연락")
        if current_view != "consult":
            if st.button("3번 신청하기", key=f"jump_consult_{current_view}", use_container_width=True):
                st.session_state.portal_view = "consult"
                st.rerun()
        else:
            st.success("현재 3번 서비스 이용 중")


def _render_portal_home() -> None:
    st.markdown(
        """
        <div class='hero-box'>
            <div class='hero-title'>서비스 통합 포털</div>
            <div class='hero-sub'>원하는 서비스를 바로 선택해 시작하세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class='portal-card'>
                <div class='portal-chip'>01</div>
                <div class='portal-title'>나의 입시 위치 진단</div>
                <div class='portal-sub'>학생부 분석과 합격컷 기반의 진단 서비스</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("1번 서비스 열기", key="open_admission", use_container_width=True):
            st.session_state.portal_view = "admission"
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class='portal-card'>
                <div class='portal-chip'>02</div>
                <div class='portal-title'>AI탐구·세특 생성기</div>
                <div class='portal-sub'>교과/진로 기반 탐구 주제 추천 및 세특 문장 생성</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("2번 서비스 열기", key="open_setuk", use_container_width=True):
            st.session_state.portal_view = "setuk"
            st.rerun()

    with col3:
        st.markdown(
            """
            <div class='portal-card'>
                <div class='portal-chip'>03</div>
                <div class='portal-title'>대치수프리마 입시 컨설팅 신청</div>
                <div class='portal-sub'>상담 신청 접수 및 후속 연락</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("3번 서비스 열기", key="open_consult", use_container_width=True):
            st.session_state.portal_view = "consult"
            st.rerun()


def _render_admission_launcher() -> None:
    st.subheader("나의 입시 위치 진단")
    _render_service_shortcuts("admission")
    st.markdown("---")
    st.info("입시 위치 진단 앱은 별도 실행형입니다. URL 바로가기로 이동하세요.")
    launch_url = st.text_input(
        "입시진단 앱 URL",
        value=st.session_state.get("admission_app_url", "http://localhost:8502"),
    )
    st.session_state.admission_app_url = launch_url.strip()
    if launch_url.strip():
        st.link_button("입시진단 앱 열기", launch_url.strip(), use_container_width=True)
    st.caption("같은 PC에서 입시진단 앱을 켰다면 기본값은 http://localhost:8502 입니다.")


def _render_consult_form() -> None:
    st.subheader("대치수프리마 입시 컨설팅 신청")
    with st.form("consult_request_form"):
        c1, c2 = st.columns(2)
        with c1:
            parent_name = st.text_input("학부모 성함 *")
            phone = st.text_input("연락처 *")
            preferred_time = st.text_input("희망 연락 시간")
        with c2:
            student_name = st.text_input("학생명 *")
            student_grade = st.selectbox("학생 학년", ["고1", "고2", "고3", "N수"])
            email = st.text_input("이메일")
        note = st.text_area("상담 요청 내용", height=130)
        ok = st.form_submit_button("상담 신청 저장", use_container_width=True)

    if ok:
        if not parent_name.strip() or not student_name.strip() or not phone.strip():
            st.error("학부모 성함, 학생명, 연락처는 필수입니다.")
            return
        request_id = save_consult_request(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "parent_name": parent_name.strip(),
                "student_name": student_name.strip(),
                "student_grade": student_grade.strip(),
                "phone": phone.strip(),
                "email": email.strip(),
                "preferred_time": preferred_time.strip(),
                "note": note.strip(),
                "status": "new",
            }
        )
        st.success(f"상담 신청이 접수되었습니다. 접수번호: {request_id}")


def main() -> None:
    _bootstrap_env_from_secrets()
    st.set_page_config(page_title="서비스 통합 포털", layout="wide")
    init_db()

    if "ui_scale_mode" not in st.session_state:
        st.session_state.ui_scale_mode = "기본 (100%)"
    if "ui_width_mode" not in st.session_state:
        st.session_state.ui_width_mode = "1200px"

    with st.sidebar:
        st.markdown("### 화면 설정")
        st.selectbox("화면 배율", ["조금 작게 (90%)", "기본 (100%)", "조금 크게 (115%)"], key="ui_scale_mode")
        st.selectbox("최대 너비", ["960px", "1200px", "1400px"], key="ui_width_mode")

    scale_map = {"조금 작게 (90%)": 0.90, "기본 (100%)": 1.00, "조금 크게 (115%)": 1.15}
    width_map = {"960px": 960, "1200px": 1200, "1400px": 1400}
    _inject_style(
        ui_scale=scale_map.get(st.session_state.ui_scale_mode, 1.0),
        page_max_width=width_map.get(st.session_state.ui_width_mode, 1200),
    )

    if "portal_view" not in st.session_state:
        st.session_state.portal_view = "home"

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        if st.button("홈", use_container_width=True):
            st.session_state.portal_view = "home"
            st.rerun()
    with nav2:
        if st.button("1. 입시위치 진단", use_container_width=True):
            st.session_state.portal_view = "admission"
            st.rerun()
    with nav3:
        if st.button("2. AI탐구·세특", use_container_width=True):
            st.session_state.portal_view = "setuk"
            st.rerun()
    with nav4:
        if st.button("3. 컨설팅 신청", use_container_width=True):
            st.session_state.portal_view = "consult"
            st.rerun()

    st.markdown("---")
    if st.session_state.portal_view == "home":
        _render_portal_home()
        return
    if st.session_state.portal_view == "admission":
        _render_admission_launcher()
        return
    if st.session_state.portal_view == "consult":
        _render_consult_form()
        return

    # 2번: AI 탐구·세특 생성기
    if "generated_packets" not in st.session_state:
        st.session_state.generated_packets = []

    st.markdown(
        f"<div class='hero-box'><div class='hero-title'>{BRAND_NAME}</div>"
        "<div class='hero-sub'>교과 입력 → 주제 추천 → 세특 문장 생성 → 보고서 다운로드</div></div>",
        unsafe_allow_html=True,
    )
    _render_service_shortcuts("setuk")
    st.markdown("---")

    topic_bank = load_topic_bank()
    subjects = list(topic_bank.keys())
    recent_records = get_recent_history(days=7)
    st.info(f"최근 7일 생성 건수: {len(recent_records)}건")
    st.caption(f"로컬 DB 파일: {DB_PATH}")

    openai_ready = has_openai_key()
    st.info("OpenAI 상태: " + ("활성 가능" if openai_ready else "API 키 없음(로컬 생성 모드)"))

    with st.expander("자료 인덱스 상태", expanded=False):
        if st.button("PDF/HWPX 키워드 인덱스 새로고침"):
            build_material_index(force_refresh=True)
        idx = build_material_index(force_refresh=False)
        total = len(idx.get("items", []))
        extracted = sum(1 for x in idx.get("items", []) if x.get("extract_ok"))
        st.write(f"- 등록 자료: {total}개")
        st.write(f"- 본문 추출 성공: {extracted}개")

    with st.form("teacher_student_form"):
        st.subheader("컨설턴트 운영 정보")
        op1, op2 = st.columns([2, 3])
        with op1:
            consultant_name = st.text_input("담당컨설턴트")
        with op2:
            center_name = st.text_input("운영기관", value="대치수프리마 입시&코칭 센터")

        st.subheader("학생 정보")
        c1, c2 = st.columns(2)
        with c1:
            student_name = st.text_input("학생 이름")
            student_phone = st.text_input("학생 연락처")
            parent_phone = st.text_input("학부모 연락처")
        with c2:
            student_email = st.text_input("학생 메일주소")
            school_name = st.text_input("학교명")
            grade = st.selectbox("학년", ["중1", "중2", "중3", "고1", "고2", "고3"], index=3)

        st.subheader("탐구 흐름")
        subject = st.selectbox("1) 과목 선택", subjects, index=0)
        career_hint = st.text_input("2) 희망진로/학과", placeholder="예: 환경공학")
        interests_raw = st.text_input("3) 관심 키워드(쉼표 구분, 최대 3개)", placeholder="예: 환경, 데이터, 미디어")
        recommendation_count = st.slider("추천 주제 개수", min_value=3, max_value=10, value=5, step=1)
        strict_dedup = st.checkbox("완전 중복 금지(같은 주제 최대 2개)", value=True)
        use_openai = st.checkbox("OpenAI로 세특 문장 고도화", value=openai_ready)
        submitted = st.form_submit_button("추천 생성")

    if submitted:
        payload = {
            "consultant_name": consultant_name,
            "school_name": school_name,
            "student_name": student_name,
            "student_phone": student_phone,
            "student_email": student_email,
            "parent_phone": parent_phone,
            "grade": grade,
            "subject": subject,
            "career_hint": career_hint,
        }
        missing = validate_required_fields(payload)
        if missing:
            st.error("필수 항목 누락: " + ", ".join(missing))
            return

        interests = [x.strip() for x in interests_raw.split(",") if x.strip()]
        if len(interests) > 3:
            st.error("관심 키워드는 최대 3개까지 입력 가능합니다.")
            return

        profile = UserProfile(
            student_name=student_name.strip(),
            grade=grade.strip(),
            subject=subject,
            interests=interests,
            career_hint=career_hint.strip() or "통합 탐구",
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
            "brand": BRAND_NAME,
            "teacher_name": consultant_name.strip(),
            "teacher_school": center_name.strip(),
            "student_name": student_name.strip(),
            "school_name": school_name.strip(),
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
        st.success(f"{student_name} 학생 추천 {len(results)}건이 생성되었습니다.")

    st.subheader("학생별 생성 결과")
    if not st.session_state.generated_packets:
        st.write("아직 생성된 학생 결과가 없습니다.")
    else:
        for idx, packet in enumerate(reversed(st.session_state.generated_packets), start=DISPLAY_COUNT_START):
            title = f"{idx}. {packet['student_name']} | {packet['grade']} | {packet['subject']} | {packet['created_at']}"
            with st.expander(title, expanded=(idx == 1)):
                results = [TopicResult(**r) for r in packet["results"]]
                options = [f"{DISPLAY_COUNT_START + i}. {r.topic_title}" for i, r in enumerate(results)]
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
                single_md = _single_result_markdown(profile, selected_result, packet.get("brand", BRAND_NAME))
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

    with st.expander("최근 7일 생성 로그", expanded=False):
        rows = get_recent_history(days=7)
        if not rows:
            st.write("최근 7일 기록이 없습니다.")
        else:
            for i, row in enumerate(reversed(rows), start=DISPLAY_COUNT_START):
                st.write(
                    f"{i}. {row.get('created_at')} | {row.get('student_name')} | "
                    f"{row.get('subject')} | 결과 {row.get('result_count')}건"
                )


if __name__ == "__main__":
    main()
