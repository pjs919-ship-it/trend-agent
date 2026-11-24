"""qa/run_once.py — 수집(캐시) + 파이프라인 1회 실행 + 사람이 읽는 요약 출력
사용: python qa/run_once.py --days 30 --product "올리고 히알루론산 딥 토너"
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"), override=True)

import agent_core
import pipeline

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=30)
ap.add_argument("--product", default="올리고 히알루론산 딥 토너")
ap.add_argument("--model", default="gemini-2.5-flash-lite")
ap.add_argument("--out", default="run_latest.json")
args = ap.parse_args()

qa_dir = os.path.join(ROOT, "qa")
os.makedirs(qa_dir, exist_ok=True)
sample_path = os.path.join(qa_dir, f"sample_{args.days}d.json")

if os.path.exists(sample_path):
    with open(sample_path, encoding="utf-8") as f:
        videos = json.load(f)
    print(f"[캐시된 수집 결과 사용] {sample_path} ({len(videos)}건) — YouTube 쿼터 0 (누적 {agent_core.get_used_youtube_units()}유닛)")
else:
    before_units = agent_core.get_used_youtube_units()
    yt = agent_core.build_youtube_client()
    videos = agent_core.fetch_mega_kbeauty_shorts(yt, days=args.days)
    after_units = agent_core.get_used_youtube_units()
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    print(f"[신규 수집] {len(videos)}건 저장 → {sample_path} (이번 {after_units - before_units}유닛 / 누적 {after_units}유닛)")

res = pipeline.run_pipeline(videos, args.product, model=args.model)
out_path = os.path.join(qa_dir, args.out)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("\n=== 통계 ===")
print(json.dumps(res["stats"], ensure_ascii=False))
print(f"YouTube 누적 유닛: {agent_core.get_used_youtube_units()} / {agent_core.YOUTUBE_UNIT_LIMIT}")

print("\n=== 이번 주 시장 패턴 ===")
for idx, pat in enumerate(res.get("market_patterns", []), 1):
    print(f"  {idx}. {pat}")

fact = {f["video_id"]: f for f in res["facts"]}
jd = {j["video_id"]: j for j in res["judgements"]}
print("\n=== 영상별 결과 ===")
for v in res["videos"]:
    f = fact.get(v["video_id"])
    j = jd.get(v["video_id"])
    vpd = v.get("views_per_day", 0)
    lr = v.get("like_rate", 0.0)
    print(f"\n[{v['views']:>9,}회 | 일평균 {vpd:>7,} | 좋아요 {lr:>5.2f}% | {v['text_source']}] {v['title'][:45]}  ({v['video_id']})")
    if not f:
        print("  (팩트 없음)")
        continue
    print(f"  팩트: [{f['domain']} | {f.get('format_tag', '기타')}] {f['what_happens']}  | 근거검증={'OK' if f['evidence_ok'] else 'FAIL'}")
    if j:
        print(f"  판정: {j['decision']} {j['score']}점 — {j['reason']}")
        for fl in j["flags"]:
            print(f"    · flag: {fl}")
    else:
        print("  판정: (근거 불충분으로 판정 제외)")
print("\n=== 브리프 ===")
for b in res["briefs"]:
    print(f"\n[{b['video_id']}] needs_review={b['needs_review']} {b['violations']}")
    print(f"  훅: {b['hook']}\n  비포: {b['before']}\n  제품: {b['product_moment']}\n  CTA: {b['cta']}\n  메모: {b['creator_note']}")

print("\n=== 2종 복사 산출물 길이 ===")
print(f"  internal_report_md: {len(res.get('internal_report_md', ''))} chars")
print(f"  creator_guide_md:   {len(res.get('creator_guide_md', ''))} chars")
