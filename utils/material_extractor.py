import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_PATH = BASE_DIR / "data" / "source_materials.json"
OUTPUT_DIR = BASE_DIR / "output"
INDEX_CACHE = OUTPUT_DIR / "material_index.json"


STOPWORDS = {
    "그리고", "또한", "대한", "위한", "에서", "으로", "하다", "있다", "없다", "수업", "탐구",
    "활동", "학생", "주제", "분석", "자료", "결과", "과정", "연구", "내용", "정리", "기반",
    "school", "student", "study", "data", "result", "using", "with", "from", "that", "this",
}


def load_source_materials() -> List[Dict]:
    if not SOURCE_PATH.exists():
        return []
    with SOURCE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
    except Exception:
        return ""


def _extract_hwpx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            text_chunks = []
            for name in xml_names:
                if "contents" not in name.lower() and "section" not in name.lower():
                    continue
                raw = zf.read(name).decode("utf-8", errors="ignore")
                cleaned = re.sub(r"<[^>]+>", " ", raw)
                text_chunks.append(cleaned)
            return "\n".join(text_chunks)
    except Exception:
        return ""


def _extract_text(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".hwpx":
        return _extract_hwpx_text(path)
    return ""


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z가-힣]{2,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def _top_keywords(text: str, top_k: int = 40) -> List[str]:
    counts = Counter(_tokenize(text))
    return [word for word, _ in counts.most_common(top_k)]


def build_material_index(force_refresh: bool = False) -> Dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    source_rows = load_source_materials()

    if INDEX_CACHE.exists() and not force_refresh:
        try:
            with INDEX_CACHE.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("source_count") == len(source_rows):
                return cached
        except Exception:
            pass

    items = []
    for row in source_rows:
        path_str = row.get("path", "")
        text = _extract_text(path_str)
        keywords = _top_keywords(text, top_k=40) if text else []
        items.append(
            {
                "title": row.get("title", ""),
                "path": path_str,
                "subjects": row.get("subjects", []),
                "keyword_count": len(keywords),
                "keywords": keywords,
                "file_exists": os.path.exists(path_str),
                "extract_ok": bool(text),
            }
        )

    payload = {
        "source_count": len(source_rows),
        "items": items,
    }
    with INDEX_CACHE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def recommend_materials(subject: str, interests: List[str], limit: int = 4) -> Dict:
    index = build_material_index(force_refresh=False)
    interest_tokens = set(_tokenize(" ".join(interests)))
    rows = []
    for item in index.get("items", []):
        if subject not in item.get("subjects", []):
            continue
        kw_set = set(item.get("keywords", []))
        overlap = len(interest_tokens & kw_set) if interest_tokens else 0
        rows.append((overlap, item.get("keyword_count", 0), item))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)

    picked = [x[2] for x in rows[:limit]]
    merged_keywords = []
    for item in picked:
        merged_keywords.extend(item.get("keywords", [])[:12])
    merged_keywords = list(dict.fromkeys(merged_keywords))[:20]

    references = [f"{x['title']} ({x['path']})" for x in picked]
    return {
        "references": references,
        "keywords": merged_keywords,
        "picked_count": len(picked),
    }
