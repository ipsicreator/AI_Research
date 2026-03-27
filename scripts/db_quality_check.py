import json
import os
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TOPIC_PATH = BASE_DIR / "data" / "topic_bank.json"
SOURCE_PATH = BASE_DIR / "data" / "source_materials.json"
INDEX_PATH = BASE_DIR / "output" / "material_index.json"
REPORT_PATH = BASE_DIR / "output" / "db_quality_report.json"


def run() -> None:
    with TOPIC_PATH.open("r", encoding="utf-8") as f:
        topic = json.load(f)
    with SOURCE_PATH.open("r", encoding="utf-8") as f:
        source = json.load(f)

    summary = {}
    details = {}

    subjects_topic = set(topic.keys())
    subjects_source = set()
    for row in source:
        subjects_source.update(row.get("subjects", []))
    summary["subjects_topic"] = sorted(subjects_topic)
    summary["subjects_source"] = sorted(subjects_source)
    summary["subject_diff_topic_minus_source"] = sorted(subjects_topic - subjects_source)
    summary["subject_diff_source_minus_topic"] = sorted(subjects_source - subjects_topic)

    required_topic = ["title", "direction", "books", "papers", "conclusion_seed"]
    invalid_topic = []
    for subject, items in topic.items():
        for idx, row in enumerate(items, start=1):
            miss = [k for k in required_topic if k not in row]
            if miss:
                invalid_topic.append((subject, idx, miss))
    summary["topic_total_rows"] = sum(len(v) for v in topic.values())
    summary["topic_invalid_schema_count"] = len(invalid_topic)
    summary["topic_rows_per_subject"] = {k: len(v) for k, v in topic.items()}
    details["invalid_topic"] = invalid_topic

    required_source = ["title", "path", "subjects"]
    invalid_source = []
    missing_files = []
    for idx, row in enumerate(source, start=1):
        miss = [k for k in required_source if k not in row]
        if miss:
            invalid_source.append((idx, miss))
        path = row.get("path", "")
        if not path or not os.path.exists(path):
            missing_files.append((idx, row.get("title", ""), path))
    summary["source_total_rows"] = len(source)
    summary["source_invalid_schema_count"] = len(invalid_source)
    summary["source_missing_files_count"] = len(missing_files)
    details["invalid_source"] = invalid_source
    details["missing_files"] = missing_files

    if INDEX_PATH.exists():
        with INDEX_PATH.open("r", encoding="utf-8") as f:
            index = json.load(f)
        items = index.get("items", [])
        summary["index_exists"] = True
        summary["index_items"] = len(items)
        summary["index_extract_ok_count"] = sum(1 for x in items if x.get("extract_ok"))
        summary["index_file_exists_count"] = sum(1 for x in items if x.get("file_exists"))
        ext_counter = Counter(Path(x.get("path", "")).suffix.lower() for x in items)
        ext_ok_counter = Counter(
            Path(x.get("path", "")).suffix.lower()
            for x in items
            if x.get("extract_ok")
        )
        summary["index_by_ext"] = dict(ext_counter)
        summary["index_ok_by_ext"] = dict(ext_ok_counter)
    else:
        summary["index_exists"] = False

    REPORT_PATH.parent.mkdir(exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": details}, f, ensure_ascii=False, indent=2)

    print(f"Saved: {REPORT_PATH}")
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    run()
