"""batch_update.py — 숏폼레이더 1단계 시장 트렌드 일일 배치 수집·저장 스크립트

GitHub Actions(오전 08:00 KST / 오후 17:00 KST) 또는 로컬에서 실행해
data/trends_snapshot.json, data/trends_snapshot.js, beauty_channels.json 을 갱신합니다.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

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


CORE_AI_PATHS = {"beauty", "beauty/skincare", "beauty/makeup"}
_EXHAUSTED_MODELS: Set[str] = set()
_NON_COSMETIC_NOISE_RE = re.compile(
    r"헤어스타일|#헤어\b|탈모\s*샴푸|블랙샴푸|바디워시|바디미스트|바디스크럽|바디로션|고데기|매직기|파마|염색|가발"
)


def _infer_format_and_reason(v: Dict[str, Any], domain: str) -> Dict[str, Any]:
    """제목·수치 기반 무할루시네이션 상세 분석 보완 생성."""
    title = (v.get("title") or "").strip()
    views = int(v.get("views") or 0)
    sub_ratio = float(v.get("views_per_subscriber") or 0)
    avg_ratio = float(v.get("views_vs_channel_avg") or 0)
    is_ad = bool(v.get("has_paid_promotion"))
    promo_txt = "유료 광고 표기 영상" if is_ad else "광고 표기 없는 오가닉 영상"

    if any(k in title for k in ("비포", "애프터", "전후", "실험", "검증", "성분")):
        fmt = "비포/애프터 실험형"
        hook_mech = "전후 변화·성분 검증 프레임을 앞세워 시청자의 의심을 즉각 해소하려는 구성"
        tip = "사용 전후 대비 컷이나 수치 검증을 첫 2초에 배치해 이탈을 막아보세요."
    elif any(k in title for k in ("올영", "올리브영", "다이소", "추천템", "꿀템", "빵꾸")):
        fmt = "올영 추천 리스트형"
        hook_mech = "실제 구매·재사용 맥락(추천템/완통)과 가성비·접근성 키워드로 클릭 장벽을 낮춘 구성"
        tip = "사용 맥락(재구매·입문템)과 가격/접근성 대비를 첫 문장에 걸어보세요."
    elif any(k in title for k in ("루틴", "응급", "화잘먹", "초간단", "1분", "출근")):
        fmt = "응급처치 루틴형"
        hook_mech = "구체적인 피부·메이크업 고민 상황을 짚어 즉각적인 해결 루틴을 제시하는 구성"
        tip = "시청자가 겪는 특정 시간대·상황 고민을 첫 자막으로 바로 호출하세요."
    elif any(k in title for k in ("믹싱", "섞어", "꿀조합", "조합")):
        fmt = "믹싱 꿀팁형"
        hook_mech = "의외의 제품 조합·활용 팁으로 '나도 따라 해보고 싶다'는 호기심을 자극하는 구성"
        tip = "기존 인기 제품과 함께 쓰는 2단 활용법을 시연해 저장·공유를 유도하세요."
    elif any(k in title for k in ("겟레디", "GRWM", "메이크업", "출근룩")):
        fmt = "겟레디윗미"
        hook_mech = "일상 준비 흐름 속에 제품을 자연스럽게 녹여 광고 저항감을 낮춘 구성"
        tip = "제품 단독 설명보다 실제 사용 순서와 제형 컷을 자연스럽게 끼워 넣으세요."
    else:
        fmt = "제품 리뷰형"
        hook_mech = "제목에 핵심 타겟·소구 포인트를 전진 배치해 관심 시청자의 클릭을 모은 구성"
        tip = "타겟의 가장 큰 불편 1가지를 제목과 1초 컷 자막에 맞춰 통일해 보세요."

    stat_parts = [f"누적 {views:,}회"]
    if sub_ratio >= 1.5:
        stat_parts.append(f"구독자 대비 {sub_ratio:.1f}배")
    if avg_ratio >= 1.5:
        stat_parts.append(f"채널 평소 대비 {avg_ratio:.1f}배")
    stat_str = " · ".join(stat_parts)

    viral_reason = (
        f"{hook_mech}입니다. {promo_txt}으로 {stat_str} 반응을 얻으며 "
        f"타겟 시청자의 저장·탐색 수요를 끌어냈습니다."
    )
    return {
        "video_id": v["video_id"],
        "domain": domain,
        "format_tag": fmt,
        "what_happens": title[:60],
        "viral_reason": viral_reason,
        "apply_point": tip,
        "product_types": [],
        "hook_quote": title[:40],
        "evidence_quote": title[:40],
        "evidence_ok": True,
        "text_source": v.get("text_source", "meta"),
    }


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
    top_title = (top_v.get("title") or "")[:34]
    ad_cnt = sum(1 for v in vids if v.get("has_paid_promotion"))
    org_cnt = len(vids) - ad_cnt
    patterns = [
        f"'{path_label}' 상위 {len(vids)}편 중 최고 조회수는 '{top_title}'({top_views:,}회)로, 구체적 상황·가성비 키워드를 앞세운 훅이 강세예요.",
        f"현재 수집된 영상은 오가닉 {org_cnt}편, 광고 {ad_cnt}편 비중으로 실제 사용감·꿀팁형 리뷰가 주로 반응하고 있어요.",
        "각 영상을 눌러 초반 시선 고정 포인트와 반응 이유를 확인한 뒤, '이 공식으로 우리 상품 기획하기'로 바로 카피·콘티를 뽑아보세요.",
    ]
    facts = [_infer_format_and_reason(v, domain) for v in vids[:30]]
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
    fact_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # 대분류 3개는 Gemini 2.5 Flash(thinking_budget=256), 세부 10개는 Gemini 2.5 Flash-Lite(thinking_budget=0)
    # 이미 분석된 video_id는 캐시 재사용으로 0토큰 처리
    if path_key in CORE_AI_PATHS:
        model_candidates = [("gemini-flash-latest", None), ("gemini-2.5-flash-lite", 0)]
    else:
        model_candidates = [("gemini-2.5-flash-lite", 0), ("gemini-flash-latest", None)]

    for model_name, t_budget in model_candidates:
        if model_name in _EXHAUSTED_MODELS:
            continue
        try:
            res = pipeline.run_step1_explore(
                vids,
                path_label=path_label,
                days_range=days_val,
                api_key=gg_key,
                model=model_name,
                max_videos=30,
                thinking_budget=t_budget,
                cached_facts=fact_cache,
            )
            if fact_cache is not None:
                for f in res.get("facts", []):
                    if (
                        f.get("video_id")
                        and (f.get("viral_reason") or "").strip()
                        and f.get("what_happens") != "(팩트 추출 누락)"
                    ):
                        fact_cache[f["video_id"]] = dict(f)
            return res
        except Exception as e:
            low = str(e).lower()
            print(f"  [AI 경고] {model_name} 실패: {str(e)[:220]}")
            if "per day" in low or "free_tier_requests" in low or "429" in low:
                _EXHAUSTED_MODELS.add(model_name)
    return _build_fast_fallback_step1(vids, path_key, path_label, days_val)


_BEAUTY_SIGNAL_RE = re.compile(
    r"올영|올리브영|뷰티|화장품|메이크업|스킨케어|립|틴트|토너|세럼|크림|선크림|쿠션|파데|블러셔|밤티|클렌징|샴푸|헤어|바디|내돈내산|추천템"
)


def _filter_beauty_only(entry: Dict[str, Any]) -> Dict[str, Any]:
    """AI 판정 '기타/뷰티무관'(실제 뷰티 키워드 없는 순수 비뷰티)과 스팸·해외(비한국어) 영상 및 오염 인사이트를 제외합니다."""
    facts = entry.get("facts", [])
    vids = entry.get("videos", [])
    v_by_id = {v.get("video_id"): v for v in vids}
    non_beauty_ids: Set[str] = set()
    for f in facts:
        if f.get("domain") != "기타/뷰티무관":
            continue
        vid = f.get("video_id")
        v = v_by_id.get(vid, {})
        blob = f"{v.get('title', '')} {v.get('description', '')}"
        if not _BEAUTY_SIGNAL_RE.search(blob):
            non_beauty_ids.add(vid)
    clean_vids = [
        v for v in vids
        if v.get("video_id") not in non_beauty_ids
        and not agent_core.is_spam_video(v)
        and agent_core.is_korean(v)
        and not _NON_COSMETIC_NOISE_RE.search(f"{v.get('title', '')} {v.get('description', '')}")
    ]
    kept_ids = {v.get("video_id") for v in clean_vids[:30]}
    entry["videos"] = clean_vids[:30]
    base_domain = (
        "색조/메이크업" if "makeup" in str(entry.get("path_key", ""))
        else ("헤어/바디" if "hairbody" in str(entry.get("path_key", "")) else "기초/스킨케어")
    )
    f_by_id = {f.get("video_id"): f for f in facts if f.get("video_id") in kept_ids}
    filled_facts = []
    for v in entry["videos"]:
        vid = v.get("video_id")
        f = f_by_id.get(vid)
        if not f or not (f.get("viral_reason") or "").strip() or f.get("what_happens") == "(팩트 추출 누락)":
            fb_f = _infer_format_and_reason(v, (f or {}).get("domain") or base_domain)
            if f and (f.get("hook_quote") or "").strip():
                fb_f["hook_quote"] = f["hook_quote"]
            if f and (f.get("format_tag") or "").strip() and f.get("format_tag") != "기타":
                fb_f["format_tag"] = f["format_tag"]
            f = fb_f
        filled_facts.append(f)
    entry["facts"] = filled_facts

    stale_noise_terms = ("알바생", "알바공감", "알바 공감", "서비스직", "다우니", "자막뉴스", "스케치코미디")
    raw_pats = entry.get("market_patterns") or []
    clean_pats = [
        p for p in raw_pats
        if not any(t in re.sub(r"\s+", "", p) or t in p for t in stale_noise_terms)
    ]
    if len(clean_pats) < len(raw_pats) and clean_vids:
        fb = _build_fast_fallback_step1(
            clean_vids,
            entry.get("path_key", "beauty"),
            entry.get("path_label", "뷰티 전체"),
            int(entry.get("days_range", 30) or 30),
        )
        for p in fb["market_patterns"]:
            if len(clean_pats) >= 3:
                break
            if p not in clean_pats:
                clean_pats.append(p)
    entry["market_patterns"] = clean_pats[:3]
    return entry


def _derive_daily_1d_entries(snap: Dict[str, Any], path_keys: List[str], now_kst: str):
    """직접 수집된 1일(48시간) 데이터를 최우선으로 유지하고, 부족분만 7일 내 신작·급등 영상으로 보충합니다."""
    entries = snap.get("entries", {})
    for pk in path_keys:
        direct_1d = entries.get(f"{pk}_1")
        if direct_1d and len(direct_1d.get("videos") or []) >= 5:
            continue
        pool_vids: Dict[str, Dict[str, Any]] = {}
        pool_facts: Dict[str, Dict[str, Any]] = {}
        base_patterns: List[str] = []
        if direct_1d:
            base_patterns = direct_1d.get("market_patterns") or []
            for f in direct_1d.get("facts", []):
                pool_facts[f["video_id"]] = f
            for v in direct_1d.get("videos", []):
                pool_vids[v["video_id"]] = v
        e7 = entries.get(f"{pk}_7")
        if e7:
            if not base_patterns and e7.get("market_patterns"):
                base_patterns = e7["market_patterns"]
            for f in e7.get("facts", []):
                pool_facts.setdefault(f["video_id"], f)
            for v in e7.get("videos", []):
                pool_vids.setdefault(v["video_id"], v)
        if len(pool_vids) < 5 and entries.get(f"{pk}_30"):
            e30 = entries[f"{pk}_30"]
            if not base_patterns and e30.get("market_patterns"):
                base_patterns = e30["market_patterns"]
            for f in e30.get("facts", []):
                pool_facts.setdefault(f["video_id"], f)
            for v in e30.get("videos", []):
                if float(v.get("days_since_published", 99)) <= 7.5 or int(v.get("views_delta") or 0) > 0:
                    pool_vids.setdefault(v["video_id"], v)
        if not pool_vids:
            continue
        cands = list(pool_vids.values())
        cands.sort(
            key=lambda x: (
                1 if float(x.get("days_since_published", 99)) <= 2.2 else 0,
                1 if float(x.get("days_since_published", 99)) <= 7.5 else 0,
                int(x.get("views_delta", 0) or 0),
                int(x.get("views_per_day", 0)),
                int(x.get("views", 0)),
            ),
            reverse=True,
        )
        top30 = cands[:30]
        base_domain = "색조/메이크업" if "makeup" in pk else "기초/스킨케어"
        derived_facts = [
            pool_facts[v["video_id"]] if v["video_id"] in pool_facts and (pool_facts[v["video_id"]].get("viral_reason") or "").strip()
            else _infer_format_and_reason(v, base_domain)
            for v in top30
        ]
        entries[f"{pk}_1"] = _strip_heavy_fields({
            "mode": "snapshot",
            "path_key": pk,
            "path_label": _path_label(pk),
            "days_range": 1,
            "report_date": datetime.now(KST).date().isoformat(),
            "updated_at_kst": now_kst,
            "videos": top30,
            "facts": derived_facts,
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


def verify_snapshot(snap: Dict[str, Any], clean: bool = False) -> Dict[str, Any]:
    """스냅샷 내 해외/비뷰티 혼입, 카테고리 누락, 활성 증가 여부를 점검하고 필요 시 정화합니다."""
    entries = snap.get("entries", {})
    dirty_spam = 0
    dirty_non_ko = 0
    low_paths: List[str] = []
    active_delta_vids = 0
    total_vids = 0

    for k, entry in list(entries.items()):
        if clean and "hairbody" in k:
            entries.pop(k, None)
            continue
        if clean:
            entry = _filter_beauty_only(entry)
            entries[k] = entry
        vids = entry.get("videos", [])
        total_vids += len(vids)
        if len(vids) < 3:
            low_paths.append(f"{k}({len(vids)}건)")
        for v in vids:
            if agent_core.is_spam_video(v):
                dirty_spam += 1
            if not agent_core.is_korean(v):
                dirty_non_ko += 1
            if (v.get("views_delta") or 0) > 0:
                active_delta_vids += 1

    return {
        "entries": len(entries),
        "total_videos": total_vids,
        "dirty_spam": dirty_spam,
        "dirty_non_korean": dirty_non_ko,
        "active_delta_videos": active_delta_vids,
        "low_count_entries": low_paths,
        "passed": dirty_spam == 0 and dirty_non_ko == 0 and len(entries) > 0,
    }


def format_weekly_audit_md(snap: Dict[str, Any], report: Dict[str, Any]) -> str:
    """@[Quote] 기준: 영역·포맷 분포, 상위 15개 실물 표본, 누락 경로를 한눈에 보는 주간 점검 리포트."""
    from collections import Counter

    entries = snap.get("entries", {})
    dom_cnt: Counter = Counter()
    fmt_cnt: Counter = Counter()
    uniq_vids: Dict[str, Dict[str, Any]] = {}
    fact_by_id: Dict[str, Dict[str, Any]] = {}
    for entry in entries.values():
        for f in entry.get("facts", []):
            dom_cnt[f.get("domain", "미분류")] += 1
            fmt_cnt[f.get("format_tag", "기타")] += 1
            fact_by_id[f.get("video_id", "")] = f
        for v in entry.get("videos", []):
            vid = v.get("video_id")
            if vid and (vid not in uniq_vids or v.get("views", 0) > uniq_vids[vid].get("views", 0)):
                uniq_vids[vid] = v

    top15 = sorted(uniq_vids.values(), key=lambda x: x.get("views", 0), reverse=True)[:15]
    lines = [
        f"## 숏폼레이더 주간 데이터 점검 ({snap.get('updated_at_kst', '-')})",
        f"- 고유 영상: **{len(uniq_vids)}편** | 스팸/해외 혼입: **{report['dirty_spam']}/{report['dirty_non_korean']}건** | 부족 경로: `{', '.join(report['low_count_entries']) or '없음'}`",
        f"- 영역 분포: {', '.join(f'{k}({v})' for k, v in dom_cnt.most_common())}",
        f"- 포맷 분포: {', '.join(f'{k}({v})' for k, v in fmt_cnt.most_common())}",
        "",
        "### 조회수 상위 15개 실물 점검 (가짜·비뷰티·광고 분류 확인)",
        "| # | 조회수 | 영역 | 포맷 | 구분 | 제목 |",
        "|---|---|---|---|---|---|",
    ]
    for idx, v in enumerate(top15, 1):
        f = fact_by_id.get(v["video_id"], {})
        ad_lbl = "광고" if agent_core.detect_paid_promotion(v.get("title", ""), v.get("description", ""), bool(v.get("has_paid_promotion"))) else "오가닉"
        title = (v.get("title") or "").replace("|", " ")[:48]
        lines.append(f"| {idx} | {int(v.get('views', 0)):,} | {f.get('domain', '-')} | {f.get('format_tag', '-')} | {ad_lbl} | {title} |")
    return "\n".join(lines)


def _save_snapshot(snap: Dict[str, Any]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    with open(SNAPSHOT_JS, "w", encoding="utf-8") as f:
        f.write("window.SHORTFORM_RADAR_SNAPSHOT = ")
        json.dump(snap, f, ensure_ascii=False)
        f.write(";\n")


def main():
    parser = argparse.ArgumentParser(description="숏폼레이더 1단계 배치 업데이트")
    parser.add_argument("--days", choices=["1", "7", "30", "both", "all"], default="all")
    parser.add_argument("--paths", default="", help="쉼표로 구분된 경로 키(비우면 전체 13개)")
    parser.add_argument("--skip-ai", action="store_true", help="YouTube 수집만 테스트")
    parser.add_argument("--verify", action="store_true", help="API 호출 없이 저장된 스냅샷 품질 검증")
    parser.add_argument("--clean", action="store_true", help="스냅샷에서 해외/비뷰티 노이즈 즉시 정리 후 저장")
    parser.add_argument("--audit", action="store_true", help="영역·포맷 분포 및 상위 15개 실물 점검표(Markdown) 출력")
    args = parser.parse_args()

    if args.verify or args.clean or args.audit:
        snap = _load_existing_snapshot()
        report = verify_snapshot(snap, clean=args.clean)
        if args.clean:
            _save_snapshot(snap)
        if args.audit:
            print(format_weekly_audit_md(snap, report))
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.verify and not report["passed"]:
            raise SystemExit("스냅샷 품질 검증 실패: 해외 또는 비뷰티 영상이 남아 있습니다.")
        return

    yt_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    gg_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not yt_key:
        raise SystemExit("YOUTUBE_API_KEY 환경변수가 없습니다.")

    agent_core.YOUTUBE_UNIT_LIMIT = 9800
    tmp_log_dir = tempfile.mkdtemp(prefix="sr_batch_")
    agent_core.USAGE_LOG_PATH = os.path.join(tmp_log_dir, "usage_log.json")

    if args.days == "all":
        days_list = [30, 7, 1]
    elif args.days == "both":
        days_list = [30, 7]
    else:
        days_list = [int(args.days)]
    if args.paths.strip():
        path_keys = [p.strip() for p in args.paths.split(",") if p.strip() in agent_core.KR_EXPLORE_TREE]
    else:
        path_keys = list(agent_core.KR_EXPLORE_TREE.keys())

    yt_client = agent_core.build_youtube_client(yt_key)
    snap = _load_existing_snapshot()
    # 제거된 헤어·바디 레거시 엔트리 정리
    for stale_k in [k for k in list(snap.get("entries", {}).keys()) if "hairbody" in k]:
        snap["entries"].pop(stale_k, None)
    # 기존 스냅샷에서 이미 분석 완료된 video_id 전역 캐시 로드 (중복 AI 호출 0원)
    fact_cache: Dict[str, Dict[str, Any]] = {}
    for ent in snap.get("entries", {}).values():
        for f in ent.get("facts", []):
            vid = f.get("video_id")
            if (
                vid
                and (f.get("viral_reason") or "").strip()
                and f.get("what_happens") != "(팩트 추출 누락)"
                and "유료 광고 표기 영상" not in (f.get("viral_reason") or "")
                and "광고 표기 없는 오가닉 영상" not in (f.get("viral_reason") or "")
            ):
                fact_cache[vid] = dict(f)
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
                    s1 = _run_ai_with_fallback(vids[:30], pk, label, d, gg_key, fact_cache=fact_cache)
                    s1["videos"] = vids
                    if pk in CORE_AI_PATHS:
                        time.sleep(0.5)
                else:
                    s1 = _build_fast_fallback_step1(vids[:30], pk, label, d)
                s1 = _filter_beauty_only(s1)
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
    report = verify_snapshot(snap, clean=True)
    _save_snapshot(snap)
    print(f"스냅샷 저장 완료: {ok_count}개 경로 갱신 ({now_kst}) | 검증: {json.dumps(report, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
