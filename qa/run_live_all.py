"""qa/run_live_all.py — 1클릭 라이브 E2E 런처 (B2B-11)
사용:
  python qa/run_live_all.py --dry-run    # 네트워크 없이 예산·로직·요약 오프라인 검증
  python qa/run_live_all.py              # 7/14/30일+mostPopular 실측 + 최적 기간 재사용 E2E + LIVE_E2E_SUMMARY.md 생성
  python qa/run_live_all.py --skip-benchmark  # 기존 qa/benchmark_result.json 재사용 (YouTube 쿼터 0)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "qa"))
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"), override=True)

import agent_core
import benchmark_days
import pipeline


def pick_best_period(summary_rows: List[Dict[str, Any]], samples: Dict[str, List[Dict[str, Any]]]) -> Tuple[str, int, List[Dict[str, Any]]]:
    """기초/스킨케어 관련 영상 수와 조회수 중앙값을 종합해 가장 균형 잡힌 기간을 선택합니다 (기본 30일 폴백)."""
    candidates = []
    for row in summary_rows:
        key = row.get("strategy", "")
        if not key.startswith("search_"):
            continue
        vids = samples.get(key, [])
        if not vids:
            continue
        days_num = int(key.replace("search_", "").replace("d", ""))
        score = (row.get("skincare_count", 0) * 1000) + min(row.get("median_views", 0) / 1000.0, 500.0)
        candidates.append((score, days_num, key, vids))
    if not candidates:
        return "search_30d", 30, samples.get("search_30d", [])
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _, best_days, best_key, best_vids = candidates[0]
    return best_key, best_days, best_vids


def format_live_summary_md(
    bench_rows: List[Dict[str, Any]],
    selected_strategy: str,
    selected_days: int,
    res: Dict[str, Any],
    used_units: int,
) -> str:
    stats = res.get("stats", {})
    total_v = stats.get("videos", len(res.get("videos", [])))
    cap_v = stats.get("transcript_caption", 0)
    cap_pct = round(cap_v / max(1, total_v) * 100, 1)
    mat = res.get("multi_product_matrix") or {}

    lines = [
        f"# 🚀 K-Beauty TrendSetter Pro — 라이브 E2E 실측 요약",
        f"- **생성 시각 (UTC)**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- **대상 제품**: {res.get('product')} | **선정 수집 전략**: `{selected_strategy}` (최근 {selected_days}일)",
        f"- **누적 YouTube API 사용 유닛**: `{used_units:,} / {agent_core.YOUTUBE_UNIT_LIMIT:,}`",
        "",
        "## 1. 수집 기간 벤치마크 비교표 (7일 / 14일 / 30일 / mostPopular)",
        "| 전략 | 건수 | 조회수 중앙값 | 조회수 평균 | 일평균 평균 | 한국어% | 기초관련 | 유닛 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in bench_rows:
        lines.append(
            f"| `{r['strategy']}` | {r['count']} | {r['median_views']:,} | {r['avg_views']:,} | "
            f"{r['avg_views_per_day']:,} | {r['korean_ratio_pct']:.1f}% | {r['skincare_count']} | {r['estimated_units']} |"
        )

    lines.extend([
        "",
        "## 2. E2E 파이프라인 실행 통계",
        f"- **분석 영상**: {total_v}건 (자막 확보 {cap_v}건 / **{cap_pct}%**)",
        f"- **판정 분포**: 🎯 Go **{stats.get('go', 0)}건** · ⚠️ Pivot **{stats.get('pivot', 0)}건** · ❌ Drop **{stats.get('drop', 0)}건**",
        f"- **브리프 생성**: {stats.get('briefs', 0)}건 (검수 필요: {stats.get('briefs_need_review', 0)}건)",
        f"- **3종 교차 매칭 추천 주력 제품**: **{mat.get('recommendation_reason', '-')}**",
        "",
        "---",
        "## 3. 팀장/슬랙 보고용 1페이지 요약 (`internal_report_md`)",
        res.get("internal_report_md", "(없음)"),
        "",
        "---",
        "## 4. 인플루언서 DM 발송 본문 (`creator_dm_clean_md`)",
        res.get("creator_dm_clean_md", "(없음)"),
    ])
    return "\n".join(lines).strip()


def run_dry_run(product_name: str):
    used_now = agent_core.get_used_youtube_units()
    limit = agent_core.YOUTUBE_UNIT_LIMIT
    est_units = 904  # 301 * 3 + 1 (Step B는 Step A 결과 재사용 → 추가 0유닛)
    print("=== [DRY-RUN] 1클릭 라이브 E2E 런처 오프라인 검증 ===")
    print(f"1) 예산 확인: 현재 {used_now} + 벤치마크 예상 {est_units} = {used_now + est_units} / {limit} → "
          f"{'예산 내 (OK)' if used_now + est_units <= limit else '예산 초과 (BLOCK)'}")
    if used_now + est_units > limit:
        sys.exit(1)

    golden_path = os.path.join(ROOT, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        gs_items = json.load(f)["items"]

    products = pipeline.load_products()
    prod = products[product_name]
    skin_items = [it for it in gs_items if it["expected_domain"] == "기초/스킨케어"]
    color_items = [it for it in gs_items if it["expected_domain"] != "기초/스킨케어"][:6]
    selected = skin_items + color_items
    videos = [pipeline._ensure_video_metrics(it) for it in selected]
    raw_facts = [pipeline.Fact(video_id=it["video_id"], **it["sample_fact"]) for it in selected]
    facts = pipeline.audit_facts(raw_facts, videos)
    judgements = pipeline._deterministic_judgements_for_product(facts, product_name, prod)
    mat = pipeline.build_multi_product_matrix(
        videos, facts, products=products, primary_product=product_name, primary_judgements=judgements
    )

    stats = {
        "videos": len(videos),
        "transcript_caption": sum(1 for v in videos if v.get("text_source") == "caption"),
        "go": sum(1 for j in judgements if j["decision"] == "Go"),
        "pivot": sum(1 for j in judgements if j["decision"] == "Pivot"),
        "drop": sum(1 for j in judgements if j["decision"] == "Drop"),
        "briefs": 0,
        "briefs_need_review": 0,
    }
    res = {
        "product": product_name,
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "days_range": 30,
        "videos": videos,
        "facts": facts,
        "market_patterns": ["[DRY-RUN] 골든셋 오프라인 검증 패턴"],
        "judgements": judgements,
        "briefs": [],
        "multi_product_matrix": mat,
        "stats": stats,
        "product_confidence": prod.get("confidence", "medium"),
    }
    res.update(pipeline.format_copyable_outputs(res))

    dry_bench = [
        benchmark_days.summarize_strategy("search_7d", [], 301),
        benchmark_days.summarize_strategy("search_14d", [], 301),
        benchmark_days.summarize_strategy("search_30d", videos, 301),
        benchmark_days.summarize_strategy("mostPopular_cat26", [], 1),
    ]
    best_key, best_days, _ = pick_best_period(dry_bench, {"search_30d": videos})
    summary_md = format_live_summary_md(dry_bench, best_key, best_days, res, used_now)

    print(f"2) Step A 최적 기간 선정 테스트: {best_key} (최근 {best_days}일)")
    print(f"3) Step B 결정론적 리허설: Go {stats['go']} / Pivot {stats['pivot']} / Drop {stats['drop']} | 추천: {mat['recommendation_reason']}")
    print(f"4) Step C 요약 마크다운 생성 길이: {len(summary_md)} chars (DRY-RUN이므로 qa/LIVE_E2E_SUMMARY.md 미덮어쓰기)")
    print("DRY-RUN PASS!")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="올리고 히알루론산 딥 토너")
    ap.add_argument("--model", default="gemini-2.5-flash-lite")
    ap.add_argument("--dry-run", action="store_true", help="네트워크 없이 예산·로직·요약 검증")
    ap.add_argument("--skip-benchmark", action="store_true", help="기존 qa/benchmark_result.json 재사용 (YouTube 쿼터 0)")
    args = ap.parse_args()

    if args.dry_run:
        run_dry_run(args.product)
        return

    qa_dir = os.path.join(ROOT, "qa")
    os.makedirs(qa_dir, exist_ok=True)
    bench_path = os.path.join(qa_dir, "benchmark_result.json")
    latest_path = os.path.join(qa_dir, "run_latest.json")
    summary_path = os.path.join(qa_dir, "LIVE_E2E_SUMMARY.md")

    used_now = agent_core.get_used_youtube_units()
    limit = agent_core.YOUTUBE_UNIT_LIMIT
    print(f"[1/4] YouTube API 예산 확인: 현재 {used_now} / {limit} 유닛")

    if args.skip_benchmark and os.path.exists(bench_path):
        print(f"[2/4] 기존 벤치마크 결과 재사용: {bench_path} (추가 YouTube 쿼터 0)")
        with open(bench_path, encoding="utf-8") as f:
            bench_data = json.load(f)
        bench_rows = bench_data.get("summary", [])
        raw_samples = bench_data.get("samples", {})
    else:
        if used_now + 904 > limit:
            raise RuntimeError(f"YouTube API 예산 초과 차단: 현재 {used_now} + 예상 904 > 상한 {limit}")
        print("[2/4] 7/14/30일 + mostPopular(cat 26) 실측 벤치마크 실행 중 (예상 904유닛)...")
        yt = agent_core.build_youtube_client()
        bench_rows = []
        raw_samples = {}
        for days in (7, 14, 30):
            key = f"search_{days}d"
            before = agent_core.get_used_youtube_units()
            vids = agent_core.fetch_mega_kbeauty_shorts(yt, days=days)
            after = agent_core.get_used_youtube_units()
            bench_rows.append(benchmark_days.summarize_strategy(key, vids, after - before))
            raw_samples[key] = vids

        before = agent_core.get_used_youtube_units()
        pop_vids = benchmark_days.fetch_most_popular_beauty_shorts(yt)
        after = agent_core.get_used_youtube_units()
        bench_rows.append(benchmark_days.summarize_strategy("mostPopular_cat26", pop_vids, after - before))
        raw_samples["mostPopular_cat26"] = pop_vids

        with open(bench_path, "w", encoding="utf-8") as f:
            json.dump({
                "benchmarked_at": datetime.now(timezone.utc).isoformat(),
                "total_used_units": agent_core.get_used_youtube_units(),
                "summary": bench_rows,
                "samples": raw_samples,
            }, f, ensure_ascii=False, indent=2)
        benchmark_days.print_table(bench_rows)

    best_key, best_days, selected_vids = pick_best_period(bench_rows, raw_samples)
    print(f"\n[3/4] 최적 기간 '{best_key}' ({len(selected_vids)}건) 재사용 → 4단계 파이프라인 + 3종 교차 매칭 실행 (추가 YouTube 쿼터 0)")
    res = pipeline.run_pipeline(
        selected_vids, args.product, model=args.model, days_range=best_days,
        include_matrix=True, matrix_use_llm=False, use_history=True,
    )
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"      저장 완료 → {latest_path}")

    used_after = agent_core.get_used_youtube_units()
    summary_md = format_live_summary_md(bench_rows, best_key, best_days, res, used_after)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)
    print(f"[4/4] 라이브 E2E 요약 리포트 생성 완료 → {summary_path}")
    print(f"      누적 YouTube API 사용량: {used_after:,} / {limit:,} 유닛")


if __name__ == "__main__":
    main()
