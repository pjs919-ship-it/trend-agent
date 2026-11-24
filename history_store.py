"""history_store.py — 로컬 스냅샷 시계열 변화 감지 (B2B-10)
직전 실행 스냅샷(cache_store/history.json)과 비교해 신규 등장(is_new) 및 조회수 증가분(views_delta)을 부착합니다.
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HISTORY_PATH = os.path.join(BASE_DIR, "cache_store", "history.json")


def load_history(store_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = store_path or DEFAULT_HISTORY_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("videos"), dict):
            return data
    except Exception:
        return None
    return None


def save_history(
    videos: List[Dict[str, Any]],
    store_path: Optional[str] = None,
    max_entries: int = 200,
) -> str:
    path = store_path or DEFAULT_HISTORY_PATH
    now_iso = datetime.now(timezone.utc).isoformat()
    existing = load_history(store_path=path) or {}
    merged: Dict[str, Any] = dict(existing.get("videos", {})) if isinstance(existing.get("videos"), dict) else {}

    for v in videos:
        vid = v.get("video_id")
        if not vid:
            continue
        merged[vid] = {
            "views": int(v.get("views", 0)),
            "likes": int(v.get("likes", 0)),
            "captured_at": now_iso,
        }

    # 최신 captured_at 순으로 최근 max_entries건(기본 200건)만 유지
    if len(merged) > max_entries:
        sorted_items = sorted(
            merged.items(),
            key=lambda kv: kv[1].get("captured_at", ""),
            reverse=True,
        )[:max_entries]
        merged = dict(sorted_items)

    snapshot: Dict[str, Any] = {
        "last_captured_at": now_iso,
        "videos": merged,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return path


def annotate_with_history(
    videos: List[Dict[str, Any]],
    save: bool = True,
    store_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """직전 스냅샷과 비교해 각 영상 dict에 is_new, views_delta, prev_captured_at, has_prev_snapshot을 부착합니다."""
    prev = load_history(store_path=store_path)
    has_prev = prev is not None and bool(prev.get("videos"))
    prev_videos = prev.get("videos", {}) if has_prev else {}
    prev_last = prev.get("last_captured_at") if has_prev else None

    out: List[Dict[str, Any]] = []
    for v in videos:
        item = dict(v)
        vid = item.get("video_id")
        if not has_prev:
            item["has_prev_snapshot"] = False
            item["is_new"] = False
            item["views_delta"] = None
            item["prev_captured_at"] = None
        elif vid not in prev_videos:
            item["has_prev_snapshot"] = True
            item["is_new"] = True
            item["views_delta"] = None
            item["prev_captured_at"] = prev_last
        else:
            prev_row = prev_videos[vid]
            prev_views = int(prev_row.get("views", 0))
            curr_views = int(item.get("views", 0))
            item["has_prev_snapshot"] = True
            item["is_new"] = False
            item["views_delta"] = max(0, curr_views - prev_views)
            item["prev_captured_at"] = prev_row.get("captured_at") or prev_last
        out.append(item)

    if save and videos:
        save_history(videos, store_path=store_path)
    return out
