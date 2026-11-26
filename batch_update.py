"""batch_update.py — 숏폼레이더 1단계 시장 트렌드 일일 배치 수집·저장 스크립트

GitHub Actions(오전 08:00 KST / 오후 17:00 KST) 또는 로컬에서 실행해
data/trends_snapshot.json, data/trends_snapshot.js, beauty_channels.json 을 갱신합니다.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

from dotenv import load_dotenv

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
load_dotenv(os.path.join(BASE, ".env"))

import agent_core
import pipeline

KST = timezone(timedelta(hours=9))
DATA_DIR = os.path.join(BASE, "data")
SNAPSHOT_JSON = os.path.join(DATA_DIR, "trends_snapshot.json")
SNAPSHOT_JS = os.path.join(DATA_DIR, "trends_snapshot.js")
CHANNELS_POOL_PATH = os.path.join(BASE, "beauty_channels.json")


def _path_label(path_key: str) -> str:
    chain: List[str] = []
    cur = path_key
    while cur and cur in agent_core.KR_EXPLORE_TREE:
        chain.insert(0, agent_core.KR_EXPLORE_TREE[cur]["label"])
        cur = agent_core.KR_EXPLORE_TREE[cur]["parent"]
    return " > ".join(chain) or path_key


def _load_existing_snapshot() -> Dict[str, Any]:
    if os.path.exists(SNAPSHOT_JSON):
        try:
            with open(SNAPSHOT_JSON, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("entries", {})
                data.setdefault("prev_views", {})
                return data
        except Exception:
            pass
    return {"updated_at_kst": "", "entries": {}, "prev_views": {}}


def _update_beauty_channels_pool(entries: Dict[str, Any]):
    """S/A등급 순수 뷰티 영상의 채널을 beauty_channels.json에 자동 누적합니다."""
    pool: Dict[str, Any] = {"_meta": {"description": "K-뷰티 핵심 채널 풀", "updated_at": ""}, "channels": []}
    if os.path.exists(CHANNELS_POOL_PATH):
        try:
            with open(CHANNELS_POOL_PATH, encoding="utf-8") as f:
                pool = json.load(f)
        except Exception:
            pass
    existing_ids: Set[str] = {c.get("channel_id") for c in pool.get("channels", []) if c.get("channel_id")}
    added = 0
    for entry in entries.values():
        pk = entry.get("path_key", "beauty")
        non_beauty_ids = {f.get("video_id") for f in entry.get("facts", []) if f.get("domain") == "기타/뷰티무관"}
        for v in entry.get("videos", []):
            if v.get("video_id") in non_beauty_ids:
                continue
            cid = v.get("channel_id")
            if not cid or cid in existing_ids:
                continue
            if v.get("viral_grade") in ("S", "A") and len(existing_ids) < 120:
                existing_ids.add(cid)
                pool.setdefault("channels", []).append({
                    "channel_id": cid,
                    "title": v.get("channel_title", ""),
                    "handle": v.get("channel_handle", ""),
                    "category": pk,
                    "source": "auto_discovered",
                })
                added += 1
    if added > 0:
        pool.setdefault("_meta", {})["updated_at"] = datetime.now(KST).strftime("%Y-%m-%d")
        with open(CHANNELS_POOL_PATH, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)


CORE_AI_PATHS = {"beauty", "beauty/skincare", "beauty/makeup", "beauty/hairbody"}
_EXHAUSTED_MODELS: Set[str] = set()


def _build_fast_fallback_step1(
    vids: List[Dict[str, Any]],
    path_key: str,
    path_label: str,
    days_val: int,
) -> Dict[str, Any]:
    """AI 호출 없이도 깔끔한 1단계 요약·메타 팩트를 즉시 생성합니다 (0 토큰)."""
    domain = (
        "색조/메이크업" if "makeup" in path_key
        else ("헤어/바디" if "hairbody" in path_key else "기초/스킨케어")
    )
    top_v = vids[0] if vids else {}
    top_views = int(top_v.get("views", 0))
    ad_cnt = sum(1 for v in vids if v.get("has_paid_promotion"))
    org_cnt = len(vids) - ad_cnt
    patterns = [
        f"'{path_label}' 상위 {len(vids)}편 중 최고 조회수는 {top_views:,}회로, 짧은 도입부에서 피부 고민이나 사용 결과를 바로 보여주는 구성이 강세예요.",
        f"현재 수집된 영상은 일반(미표시) {org_cnt}편, 광고 표시 {ad_cnt}편 비중으로 실제 사용감 중심 리뷰가 주로 반응하고 있어요.",
        "아래 영상에서 '이 영상으로 기획하기'를 누르면 AI가 우리 제품 특징에 맞춰 카피와 4단 촬영 콘티를 바로 만들어 드려요.",
    ]
    facts = [
        {
            "video_id": v["video_id"],
            "domain": domain,
            "format_tag": "제품 리뷰형",
            "what_happens": (v.get("title") or "")[:60],
            "product_types": [],
            "hook_quote": (v.get("title") or "")[:40],
            "evidence_quote": (v.get("title") or "")[:40],
            "evidence_ok": True,
            "text_source": v.get("text_source", "meta"),
        }
        for v in vids[:15]
    ]
    return {
        "path_label": path_label,
        "days_range": days_val,
        "report_date": datetime.now(KST).date().isoformat(),
        "videos": vids,
        "facts": facts,
        "market_patterns": patterns,
    }


def _run_ai_with_fallback(
    vids: List[Dict[str, Any]],
    path_key: str,
    path_label: str,
    days_val: int,
    gg_key: str,
) -> Dict[str, Any]:
    # 핵심 4개 카테고리만 Gemini AI 분석 (배치당 4회 × 하루 2회 = 8회/일, 무료 20회 한도 내 안전 유지)
    if path_key not in CORE_AI_PATHS:
        return _build_fast_fallback_step1(vids, path_key, path_label, days_val)

    for model_name in ("gemini-2.5-flash-lite", "gemini-flash-latest"):
        if model_name in _EXHAUSTED_MODELS:
            continue
        try:
            return pipeline.run_step1_explore(
                vids,
                path_label=path_label,
                days_range=days_val,
                api_key=gg_key,
                model=model_name,
            )
        except Exception as e:
            low = str(e).lower()
            print(f"  [AI 경고] {model_name} 실패: {str(e)[:220]}")
            if "per day" in low or "free_tier_requests" in low or "429" in low:
                _EXHAUSTED_MODELS.add(model_name)
    return _build_fast_fallback_step1(vids, path_key, path_label, days_val)


def _filter_beauty_only(entry: Dict[str, Any]) -> Dict[str, Any]:
    """AI 판정 결과 '기타/뷰티무관' 영상을 스냅샷에서 제외합니다."""
    facts = entry.get("facts", [])
    non_beauty_ids = {f.get("video_id") for f in facts if f.get("domain") == "기타/뷰티무관"}
    vids = entry.get("videos", [])
    clean_vids = [v for v in vids if v.get("video_id") not in non_beauty_ids]
    if len(clean_vids) >= 3:
        vids = clean_vids
        facts = [f for f in facts if f.get("video_id") not in non_beauty_ids]
    entry["videos"] = vids[:30]
    entry["facts"] = facts
    return entry


def _derive_daily_1d_entries(snap: Dict[str, Any], path_keys: List[str], now_kst: str):
    """7일·30일 스냅샷에서 최근 48시간 업로드 또는 views_delta 상위 영상을 모아 1일 기준을 자동 생성합니다."""
    entries = snap.get("entries", {})
    for pk in path_keys:
        pool_vids: Dict[str, Dict[str, Any]] = {}
        pool_facts: Dict[str, Dict[str, Any]] = {}
        base_patterns: List[str] = []
        for d in (7, 30):
            e = entries.get(f"{pk}_{d}")
            if not e:
                continue
            if not base_patterns and e.get("market_patterns"):
                base_patterns = e["market_patterns"]
            for f in e.get("facts", []):
                pool_facts[f["video_id"]] = f
            for v in e.get("videos", []):
                pool_vids[v["video_id"]] = v
        if not pool_vids:
            continue
        cands = list(pool_vids.values())
        # 48시간 이내 업로드 or views_delta 보유 영상 우선, 없으면 views_per_day 상위
        cands.sort(
            key=lambda x: (
                1 if float(x.get("days_since_published", 99)) <= 2.2 else 0,
                int(x.get("views_delta", 0) or 0),
                int(x.get("views_per_day", 0)),
                int(x.get("views", 0)),
            ),
            reverse=True,
        )
        top30 = cands[:30]
        top_ids = {v["video_id"] for v in top30}
        entries[f"{pk}_1"] = _strip_heavy_fields({
            "mode": "snapshot",
            "path_key": pk,
            "path_label": _path_label(pk),
            "days_range": 1,
            "report_date": datetime.now(KST).date().isoformat(),
            "updated_at_kst": now_kst,
            "videos": top30,
            "facts": [pool_facts[vid] for vid in top_ids if vid in pool_facts],
            "market_patterns": base_patterns[:3],
        })


def _strip_heavy_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    clean_videos = []
    for v in entry.get("videos", []):
        v2 = dict(v)
        v2.pop("transcript", None)
        if isinstance(v2.get("source_text"), str):
            v2["source_text"] = v2["source_text"][:400]
        clean_videos.append(v2)
    return {
        "mode": "snapshot",
        "path_key": entry.get("path_key", ""),
        "path_label": entry.get("path_label", ""),
        "days_range": entry.get("days_range", 30),
        "report_date": entry.get("report_date", ""),
        "updated_at_kst": entry.get("updated_at_kst", ""),
        "videos": clean_videos,
        "facts": entry.get("facts", []),
        "market_patterns": entry.get("market_patterns", []),
    }


def main():
    parser = argparse.ArgumentParser(description="숏폼레이더 1단계 배치 업데이트")
    parser.add_argument("--days", choices=["1", "7", "30", "both"], default="30")
    parser.add_argument("--paths", default="", help="쉼표로 구분된 경로 키(비우면 전체 16개)")
    parser.add_argument("--skip-ai", action="store_true", help="YouTube 수집만 테스트")
    args = parser.parse_args()

    yt_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    gg_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not yt_key:
        raise SystemExit("YOUTUBE_API_KEY 환경변수가 없습니다.")

    agent_core.YOUTUBE_UNIT_LIMIT = 9800
    tmp_log_dir = tempfile.mkdtemp(prefix="sr_batch_")
    agent_core.USAGE_LOG_PATH = os.path.join(tmp_log_dir, "usage_log.json")

    days_list = [30, 7] if args.days == "both" else [int(args.days)]
    if args.paths.strip():
        path_keys = [p.strip() for p in args.paths.split(",") if p.strip() in agent_core.KR_EXPLORE_TREE]
    else:
        path_keys = list(agent_core.KR_EXPLORE_TREE.keys())

    yt_client = agent_core.build_youtube_client(yt_key)
    snap = _load_existing_snapshot()
    prev_views: Dict[str, int] = snap.get("prev_views", {})
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    ok_count = 0
    for d in days_list:
        fetch_days = 2 if d == 1 else d
        for pk in path_keys:
            label = _path_label(pk)
            print(f"[배치] {pk} ({label}) | {d}일 수집 중...")
            try:
                vids = agent_core.fetch_kr_step1_shorts(
                    yt_client, path_key=pk, days=fetch_days, sort_by="subscriber_ratio", use_cache=False
                )
                for v in vids:
                    vid = v["video_id"]
                    cur_v = int(v.get("views", 0))
                    if vid in prev_views and cur_v > int(prev_views[vid]):
                        v["views_delta"] = cur_v - int(prev_views[vid])
                    prev_views[vid] = cur_v

                if vids and gg_key and not args.skip_ai:
                    s1 = _run_ai_with_fallback(vids[:15], pk, label, d, gg_key)
                    s1["videos"] = vids
                    s1 = _filter_beauty_only(s1)
                    if pk in CORE_AI_PATHS:
                        time.sleep(1.0)
                else:
                    s1 = _build_fast_fallback_step1(vids[:30], pk, label, d)
                s1["path_key"] = pk
                s1["days_range"] = d
                s1["updated_at_kst"] = now_kst
                snap["entries"][f"{pk}_{d}"] = _strip_heavy_fields(s1)
                ok_count += 1
                print(f"  -> 완료 ({len(s1['videos'])}건)")
            except Exception as e:
                print(f"  [실패] {pk} ({d}일): {e}")

    if any(d in (7, 30) for d in days_list):
        _derive_daily_1d_entries(snap, path_keys, now_kst)

    _update_beauty_channels_pool(snap["entries"])
    snap["updated_at_kst"] = now_kst
    snap["prev_views"] = prev_views
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    with open(SNAPSHOT_JS, "w", encoding="utf-8") as f:
        f.write("window.SHORTFORM_RADAR_SNAPSHOT = ")
        json.dump(snap, f, ensure_ascii=False)
        f.write(";\n")
    print(f"스냅샷 저장 완료: {ok_count}개 경로 갱신 ({now_kst})")


if __name__ == "__main__":
    main()
