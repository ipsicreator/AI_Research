import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from utils.material_extractor import recommend_materials
from utils.openai_enhancer import refine_setuk_sentences


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "topic_bank.json"
OUTPUT_DIR = BASE_DIR / "output"


@dataclass
class UserProfile:
    student_name: str
    grade: str
    subject: str
    interests: List[str]
    career_hint: str


@dataclass
class TopicResult:
    subject: str
    topic_title: str
    topic_direction: str
    books: List[str]
    papers: List[str]
    data_sources: List[str]
    expected_conclusion: str
    setuk_sentence: str


def load_topic_bank() -> Dict[str, List[Dict[str, Any]]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {DATA_PATH}")
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[\s,./]+", text.lower()) if t]


def _public_data_sources(subject: str) -> List[str]:
    common = [
        "KCI(한국학술지인용색인) 키워드 검색",
        "RISS(학술연구정보서비스) 주제 검색",
        "DBpia 주제 키워드 검색",
    ]
    subject_map = {
        "국어": ["국립국어원 어문 규범/언어 자료"],
        "영어": ["British Council 학습 자료", "VOA Learning English"],
        "수학": ["KOSIS(국가통계포털) 공개 데이터"],
        "사회탐구": ["통계청 KOSIS", "공공데이터포털(data.go.kr)"],
        "과학탐구": ["국가과학기술정보센터(NTIS) 공개 정보", "공공데이터포털(data.go.kr)"],
        "정보(IT)": ["AI Hub 공개 데이터 카탈로그", "공공데이터포털(data.go.kr)"],
    }
    return common + subject_map.get(subject, [])


def _rank_candidates(
    candidates: List[Dict[str, Any]],
    interests: List[str],
    extracted_keywords: List[str],
    k: int = 5,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    interest_tokens = set(_normalize_tokens(" ".join(interests)))
    source_tokens = set(_normalize_tokens(" ".join(extracted_keywords)))
    scored = []
    for row in candidates:
        corpus = " ".join(
            [
                row.get("title", ""),
                row.get("direction", ""),
                " ".join(row.get("books", [])),
                " ".join(row.get("papers", [])),
                row.get("conclusion_seed", ""),
            ]
        ).lower()
        interest_score = sum(1 for token in interest_tokens if token and token in corpus)
        source_score = sum(1 for token in source_tokens if token and token in corpus)
        total = interest_score * 2 + source_score
        scored.append((total, interest_score, source_score, row))
    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [x[3] for x in scored[: max(k, 1)]]


def _expanded_subject_pool(subject_pool: List[Dict[str, Any]], interests: List[str], target: int) -> List[Dict[str, Any]]:
    if len(subject_pool) >= target:
        return subject_pool
    expanded = list(subject_pool)
    views = ["비교 분석 관점", "정책 제안 관점", "데이터 검증 관점", "사례 적용 관점"]
    interest_hint = interests[0] if interests else "핵심 개념"
    idx = 0
    while len(expanded) < target and subject_pool:
        base = subject_pool[idx % len(subject_pool)]
        view = views[idx % len(views)]
        new_title = f"{base.get('title', '')} - {view}"
        new_direction = (
            f"{base.get('direction', '')} 추가로 '{interest_hint}' 키워드를 중심으로 "
            f"{view}에서 탐구 질문을 재구성한다."
        )
        expanded.append(
            {
                "title": new_title,
                "direction": new_direction,
                "books": list(base.get("books", [])),
                "papers": list(base.get("papers", [])),
                "conclusion_seed": base.get("conclusion_seed", ""),
            }
        )
        idx += 1

    # Add fusion-style synthetic topics to widen root diversity.
    if len(subject_pool) >= 2:
        for i in range(len(subject_pool)):
            for j in range(i + 1, len(subject_pool)):
                a = subject_pool[i]
                b = subject_pool[j]
                focus = interests[0] if interests else "핵심 개념"
                fusion_title = f"융합형 탐구: {a.get('title', '')} × {b.get('title', '')}"
                fusion_direction = (
                    f"{a.get('direction', '')}와 {b.get('direction', '')}를 연결해 "
                    f"'{focus}' 중심의 공통 변인을 설계하고 비교 검증한다."
                )
                expanded.append(
                    {
                        "title": fusion_title,
                        "direction": fusion_direction,
                        "books": list(dict.fromkeys(a.get("books", []) + b.get("books", []))),
                        "papers": list(dict.fromkeys(a.get("papers", []) + b.get("papers", []))),
                        "conclusion_seed": f"{a.get('conclusion_seed', '')}와 {b.get('conclusion_seed', '')}의 통합 해석",
                    }
                )
                if len(expanded) >= max(target, len(subject_pool) + 6):
                    return expanded
    return expanded


def _root_title(title: str) -> str:
    return title.split(" - ")[0].strip()


def _diversify_ranked(candidates: List[Dict[str, Any]], k: int, per_root_limit: int = 2) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    root_counts: Dict[str, int] = {}

    for row in candidates:
        root = _root_title(row.get("title", ""))
        count = root_counts.get(root, 0)
        if count >= per_root_limit:
            continue
        selected.append(row)
        root_counts[root] = count + 1
        if len(selected) >= k:
            return selected

    # Prefer unseen roots first for the remaining slots.
    if len(selected) < k:
        for row in candidates:
            if row in selected:
                continue
            root = _root_title(row.get("title", ""))
            if root in root_counts:
                continue
            selected.append(row)
            root_counts[root] = 1
            if len(selected) >= k:
                return selected

    if len(selected) < k:
        for row in candidates:
            if row in selected:
                continue
            selected.append(row)
            if len(selected) >= k:
                break
    return selected


def _round_robin_by_root(candidates: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for row in candidates:
        root = _root_title(row.get("title", ""))
        if root not in buckets:
            buckets[root] = []
            order.append(root)
        buckets[root].append(row)

    selected: List[Dict[str, Any]] = []
    while len(selected) < k:
        progressed = False
        for root in order:
            if buckets[root]:
                selected.append(buckets[root].pop(0))
                progressed = True
                if len(selected) >= k:
                    break
        if not progressed:
            break
    return selected


def _select_with_root_limit(
    candidates: List[Dict[str, Any]],
    k: int,
    per_root_limit: int = 2,
    hard_limit: bool = False,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    root_counts: Dict[str, int] = {}
    for row in candidates:
        root = _root_title(row.get("title", ""))
        cnt = root_counts.get(root, 0)
        if cnt >= per_root_limit:
            continue
        selected.append(row)
        root_counts[root] = cnt + 1
        if len(selected) >= k:
            return selected

    if hard_limit:
        return selected

    for row in candidates:
        if row in selected:
            continue
        selected.append(row)
        if len(selected) >= k:
            break
    return selected


def _build_teacher_style_setuk(
    profile: UserProfile,
    topic: Dict[str, Any],
    conclusion: str,
    extracted_keywords: List[str],
) -> str:
    kw = ", ".join(extracted_keywords[:3]) if extracted_keywords else "핵심 개념"
    interest_text = ", ".join(profile.interests) if profile.interests else "교과 핵심 개념"
    return (
        f"{profile.student_name} 학생은 {profile.subject} 수업에서 '{topic['title']}' 주제를 선정하여 "
        f"문제 상황을 구체화하고 자료 수집-분석-해석의 절차를 체계적으로 수행함. "
        f"특히 {interest_text} 관심사를 {kw}와 연결해 탐구 타당성을 높였으며, {conclusion}을 도출하는 과정에서 "
        f"근거 기반 추론 능력과 자기주도적 탐구 태도가 돋보임. 나아가 결과를 {profile.career_hint} 진로와 연계해 "
        f"후속 탐구 질문으로 확장하는 성찰 역량을 보임."
    )


def local_generate(
    profile: UserProfile,
    topic_bank: Dict[str, List[Dict[str, Any]]],
    use_openai: bool = True,
    recommendation_count: int = 5,
    strict_dedup: bool = False,
) -> List[TopicResult]:
    recommendation_count = max(3, min(10, recommendation_count))
    subject_pool = _expanded_subject_pool(
        topic_bank.get(profile.subject, []),
        profile.interests,
        max(recommendation_count * 2, 12),
    )
    material_context = recommend_materials(profile.subject, profile.interests, limit=4)
    extracted_keywords = material_context.get("keywords", [])
    ranked = _rank_candidates(
        subject_pool,
        profile.interests,
        extracted_keywords,
        k=max(recommendation_count * 3, recommendation_count),
    )
    diversified = _diversify_ranked(
        ranked,
        k=max(recommendation_count * 2, recommendation_count),
        per_root_limit=2,
    )
    round_robin = _round_robin_by_root(diversified, k=max(recommendation_count * 2, recommendation_count))
    chosen = _select_with_root_limit(
        round_robin,
        k=recommendation_count,
        per_root_limit=2,
        hard_limit=strict_dedup,
    )

    results: List[TopicResult] = []
    for topic in chosen:
        if extracted_keywords:
            conclusion = (
                f"{topic['conclusion_seed']} 및 {profile.career_hint} 관련 실천 가능성"
                f" (자료 핵심어: {', '.join(extracted_keywords[:2])})"
            )
        else:
            conclusion = f"{topic['conclusion_seed']} 및 {profile.career_hint} 관련 실천 가능성"

        draft = _build_teacher_style_setuk(profile, topic, conclusion, extracted_keywords)
        results.append(
            TopicResult(
                subject=profile.subject,
                topic_title=topic["title"],
                topic_direction=topic["direction"],
                books=list(topic.get("books", [])),
                papers=list(topic.get("papers", [])),
                data_sources=_public_data_sources(profile.subject),
                expected_conclusion=conclusion,
                setuk_sentence=draft,
            )
        )

    if use_openai and results:
        refined = refine_setuk_sentences(
            student_name=profile.student_name,
            subject=profile.subject,
            career_hint=profile.career_hint,
            rows=[
                {
                    "topic_title": r.topic_title,
                    "topic_direction": r.topic_direction,
                    "expected_conclusion": r.expected_conclusion,
                    "setuk_sentence": r.setuk_sentence,
                }
                for r in results
            ],
        )
        for i, sentence in enumerate(refined):
            if sentence:
                results[i].setuk_sentence = sentence
    return results


def render_markdown(profile: UserProfile, results: List[TopicResult]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {profile.student_name} 학생 탐구 주제 · 세특 생성 결과",
        "",
        f"- 생성 시각: {now}",
        f"- 학년: {profile.grade}",
        f"- 과목: {profile.subject}",
        f"- 관심 키워드: {', '.join(profile.interests) if profile.interests else '없음'}",
        f"- 진로 힌트: {profile.career_hint}",
        "",
    ]
    for idx, row in enumerate(results, start=1):
        lines.extend(
            [
                f"## 추천 {idx}",
                f"[주제명] {row.topic_title}",
                f"[탐구활동 내용] {row.topic_direction}",
                "[도서명/참고도서]",
            ]
        )
        lines.extend([f"- {x}" for x in row.books] or ["- 없음"])
        lines.extend(["", "[참고 논문/학술자료]"])
        lines.extend([f"- {x}" for x in row.papers] or ["- 없음"])
        lines.extend(["", "[참고 자료/사이트]"])
        lines.extend([f"- {x}" for x in row.data_sources] or ["- 없음"])
        lines.extend(
            [
                "",
                f"[탐구 결론] {row.expected_conclusion}",
                f"[세특 문장] {row.setuk_sentence}",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def save_output(markdown: str, profile: UserProfile) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^0-9a-zA-Z가-힣_-]+", "_", profile.student_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{safe_name}_{profile.subject}_{ts}.md"
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


def topic_results_to_dict(results: List[TopicResult]) -> List[Dict[str, Any]]:
    return [asdict(row) for row in results]
