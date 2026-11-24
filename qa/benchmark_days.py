"""qa/benchmark_days.py — 7일 / 14일 / 30일 + mostPopular(cat 26, KR) 수집 전략 비교 벤치마크
사용:
  python qa/benchmark_days.py --dry-run    # 네트워크 없이 예상 유닛(904유닛) 및 로직 검증
  python qa/benchmark_days.py              # 실제 YouTube API 호출 후 qa/benchmark_result.json 저장
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"), override=True)

import agent_core

SKINCARE_HINTS = (
    "토너", "세럼", "앰플", "크림", "로션", "패드", "마스크", "시트팩", "수분",
    "진정", "속건조", "보습", "스킨케어", "기초", "히알루론산", "장벽", "트러블", "피부",
)


def is_skincare_related(video: Dict[str, Any]) -> bool:
    blob = f"{video.get('title', '')} {video.get('description', '')}"
    return any(k in blob for k in SKINCARE_HINTS)


def summarize_strategy(name: str, videos: List[Dict[str, Any]], units: int) -> Dict[str, Any]:
    if not videos:
        return {
            "strategy": name,
            "count": 0,
            "median_views": 0,
            "avg_views": 0,
            "avg_views_per_day": 0,
            "korean_ratio_pct": 0.0,
            "skincare_count": 0,
            "estimated_units": units,
        }
    views = [int(v.get("views", 0)) for v in videos]
    vpds = [int(v.get("views_per_day", 0)) for v in videos]
    kor_cnt = sum(1 for v in videos if agent_core.is_korean(v))
    skin_cnt = sum(1 for v in videos if is_skincare_related(v))
    return {
        "strategy": name,
        "count": len(videos),
        "median_views": int(statistics.median(views)),
        "avg_views": int(round(statistics.mean(views))),
        "avg_views_per_day": int(round(statistics.mean(vpds))),
        "korean_ratio_pct": round(kor_cnt / len(videos) * 100, 1),
        "skincare_count": skin_cnt,
        "estimated_units": units,
    }


def fetch_most_popular_beauty_shorts(youtube) -> List[Dict[str, Any]]:
    """videos.list(chart='mostPopular', videoCategoryId='26', regionCode='KR') — 1유닛"""
    agent_core.record_youtube_units(1, action="videos.list.mostPopular", meta={"category": "26", "region": "KR"})
    resp = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        chart="mostPopular",
        videoCategoryId="26",
        regionCode="KR",
        maxResults=25,
    ).execute()
    now_utc = datetime.now(timezone.utc)
    results = []
    for item in resp.get("items", []):
        secs = agent_core.iso8601_to_seconds(item.get("contentDetails", {}).get("duration", ""))
        if secs == 0 or secs > 120:
            continue
        sn = item["snippet"]
        stats = item.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        pub_raw = sn.get("publishedAt", "")
        metrics = agent_core.compute_video_metrics(views, likes, pub_raw, now_utc=now_utc)
        results.append({
            "video_id": item["id"],
            "title": sn.get("title", ""),
            "description": sn.get("description", "")[:300],
            "channel_title": sn.get("channelTitle", ""),
            "views": views,
            "likes": likes,
            **metrics,
            "published_at": pub_raw[:10],
            "thumbnail_url": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "duration_s": secs,
            "is_short60": secs <= 60,
        })
    results.sort(key=lambda r: (r["views_per_day"] * 0.6 + r["views"] * 0.4), reverse=True)
    return results[:10]


def print_table(rows: List[Dict[str, Any]]):
    header = (
        f"{'전략':<18} | {'건수':>4} | {'조회수 중앙값':>11} | {'조회수 평균':>11} | "
        f"{'일평균 평균':>10} | {'한국어%':>7} | {'기초관련':>6} | {'유닛':>5}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['strategy']:<18} | {r['count']:>4} | {r['median_views']:>11,} | "
            f"{r['avg_views']:>11,} | {r['avg_views_per_day']:>10,} | "
            f"{r['korean_ratio_pct']:>6.1f}% | {r['skincare_count']:>6} | {r['estimated_units']:>5}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 예산 및 로직만 검증")
    ap.add_argument("--out", default=os.path.join(ROOT, "qa", "benchmark_result.json"))
    args = ap.parse_args()

    plan = [
        ("search_7d", 301),
        ("search_14d", 301),
        ("search_30d", 301),
        ("mostPopular_cat26", 1),
    ]
    total_est = sum(u for _, u in plan)
    used_now = agent_core.get_used_youtube_units()
    limit = agent_core.YOUTUBE_UNIT_LIMIT

    if args.dry_run:
        print("=== [DRY-RUN] 7/14/30일 + mostPopular 벤치마크 예산 검증 ===")
        print(f"현재 누적 사용 유닛: {used_now} / {limit}")
        print(f"이번 벤치마크 예상 유닛: {total_est} (301 x 3 + 1)")
        print(f"실행 후 예상 누적: {used_now + total_est} / {limit} → {'예산 내 (OK)' if used_now + total_est <= limit else '예산 초과 (BLOCK)'}")
        dry_rows = [summarize_strategy(name, [], units) for name, units in plan]
        print_table(dry_rows)
        if used_now + total_est > limit:
            sys.exit(1)
        print("DRY-RUN PASS!")
        return

    if used_now + total_est > limit:
        raise RuntimeError(
            f"YouTube API 예산 초과 방지 차단: 현재 {used_now} + 예상 {total_est} > 상한 {limit}"
        )

    yt = agent_core.build_youtube_client()
    rows: List[Dict[str, Any]] = []
    raw_samples: Dict[str, List[Dict[str, Any]]] = {}

    for days in (7, 14, 30):
        key = f"search_{days}d"
        before = agent_core.get_used_youtube_units()
        vids = agent_core.fetch_mega_kbeauty_shorts(yt, days=days)
        after = agent_core.get_used_youtube_units()
        rows.append(summarize_strategy(key, vids, after - before))
        raw_samples[key] = vids

    before = agent_core.get_used_youtube_units()
    pop_vids = fetch_most_popular_beauty_shorts(yt)
    after = agent_core.get_used_youtube_units()
    rows.append(summarize_strategy("mostPopular_cat26", pop_vids, after - before))
    raw_samples["mostPopular_cat26"] = pop_vids

    print("\n=== K-Beauty 쇼츠 수집 전략 벤치마크 결과 ===")
    print_table(rows)
    print(f"\n누적 YouTube API 사용 유닛: {agent_core.get_used_youtube_units()} / {limit}")

    payload = {
        "benchmarked_at": datetime.now(timezone.utc).isoformat(),
        "total_used_units": agent_core.get_used_youtube_units(),
        "summary": rows,
        "samples": raw_samples,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"저장 완료 → {args.out}")


if __name__ == "__main__":
    main()
