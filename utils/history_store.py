import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_FILE = OUTPUT_DIR / "history_log.jsonl"


def save_history_event(event: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    serializable = _make_json_safe(event)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(serializable, ensure_ascii=False) + "\n")


def get_recent_history(days: int = 7) -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    rows: List[Dict[str, Any]] = []
    with HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                created_at = datetime.fromisoformat(payload["created_at"])
                if created_at >= cutoff:
                    rows.append(payload)
            except Exception:
                continue
    return rows


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return value
