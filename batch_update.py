"""batch_update.py — 숏폼레이더 1단계 시장 트렌드 일일 배치 수집·저장 스크립트

GitHub Actions(오전 08:00 KST / 오후 17:00 KST) 또는 로컬에서 실행해
data/trends_snapshot.json 및 data/trends_snapshot.js 를 갱신합니다.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

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


def _run_ai_with_fallback(
    vids: List[Dict[str, Any]],
    path_label: str,
    days_val: int,
    gg_key: str,
) -> Dict[str, Any]:
    for model_name in ("gemini-2.5-flash-lite", "gemini-flash-latest"):
        try:
            return pipeline.run_step1_explore(
                vids,
                path_label=path_label,
                days_range=days_val,
                api_key=gg_key,
                model=model_name,
            )
        except Exception as e:
            print(f"  [AI 경고] {model_name} 실패: {e}")
            time.sleep(2)
    # AI가 일시 한도에 걸려도 수집된 영상 수치·등급은 살려서 반환
    return {
        "path_label": path_label,
        "days_range": days_val,
        "report_date": datetime.now(KST).date().isoformat(),
        "videos": vids,
        "facts": [],
        "market_patterns": [
            "영상별 조회수·하루 평균·구독자 대비 확산력 수치를 먼저 확인해 보세요. (AI 요약은 다음 배치에서 자동 보완됩니다.)"
        ],
    }


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
    parser.add_argument("--days", choices=["30", "7", "both"], default="30")
    parser.add_argument("--paths", default="", help="쉼표로 구분된 경로 키(비우면 전체 16개)")
    parser.add_argument("--skip-ai", action="store_true", help="YouTube 수집만 테스트")
    args = parser.parse_args()

    yt_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    gg_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not yt_key:
        raise SystemExit("YOUTUBE_API_KEY 환경변수가 없습니다.")

    # 배치 실행 시에는 일일 배치 한도(9,800유닛)까지 허용하고 임시 로그 사용
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
        for pk in path_keys:
            label = _path_label(pk)
            print(f"[배치] {pk} ({label}) | {d}일 수집 중...")
            try:
                vids = agent_core.fetch_kr_step1_shorts(
                    yt_client, path_key=pk, days=d, sort_by="subscriber_ratio", use_cache=False
                )
                for v in vids:
                    vid = v["video_id"]
                    cur_v = int(v.get("views", 0))
                    if vid in prev_views and cur_v > int(prev_views[vid]):
                        v["views_delta"] = cur_v - int(prev_views[vid])
                    prev_views[vid] = cur_v

                if vids and gg_key and not args.skip_ai:
                    s1 = _run_ai_with_fallback(vids, label, d, gg_key)
                    time.sleep(1.5)
                else:
                    s1 = {
                        "path_label": label,
                        "days_range": d,
                        "report_date": datetime.now(KST).date().isoformat(),
                        "videos": vids,
                        "facts": [],
                        "market_patterns": [],
                    }
                s1["path_key"] = pk
                s1["updated_at_kst"] = now_kst
                snap["entries"][f"{pk}_{d}"] = _strip_heavy_fields(s1)
                ok_count += 1
                print(f"  -> 완료 ({len(vids)}건)")
            except Exception as e:
                print(f"  [실패] {pk} ({d}일): {e}")

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
