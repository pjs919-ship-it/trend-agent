"""pipeline.py — 마케터 업무 프로세스 기반 4단계 파이프라인 (v2)

Step1 팩트 추출  : 브랜드 정보 없이, 제목·자막만으로 '영상에서 실제로 일어나는 일'을 추출
Step2 브랜드 판정: 팩트 vs 제품(확인된 문구만) → Go / Pivot / Drop (규칙 + LLM)
Step3 브리프     : Go 판정에만 4단 콘티 (확인된 제품 문구만 사용)
Step4 감사       : 코드로 검증 (인용문이 실제 자막에 있는지, 점수-판정 일관성, 금지 문구)
"""
import json
import os
import re
import time
from typing import List, Dict, Any, Optional

import diskcache
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

BASE = os.path.dirname(os.path.abspath(__file__))
_cache = diskcache.Cache(os.path.join(BASE, "cache_store"))

DOMAIN_BASE = "기초/스킨케어"
DOMAINS = [DOMAIN_BASE, "색조/메이크업", "헤어/바디", "기타/뷰티무관"]
FORMAT_TAGS = [
    "비포/애프터 실험형",
    "올영 추천 리스트형",
    "응급처치 루틴형",
    "믹싱 꿀팁형",
    "겟레디윗미",
    "제품 리뷰형",
    "기타",
]


# ───────────────────────── 제품 정보 (products.json 단일 출처) ─────────────────────────
def load_products() -> Dict[str, Any]:
    with open(os.path.join(BASE, "products.json"), encoding="utf-8") as f:
        return json.load(f)["products"]


def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "").lower()


# ───────────────────────── 자막 수집 ─────────────────────────
def get_transcript(vid: str) -> Dict[str, Any]:
    key = f"tr2_{vid}"
    if key in _cache:
        return _cache[key]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        snippets = list(YouTubeTranscriptApi().fetch(vid, languages=["ko", "en"]))
        segs = [{"t": round(s.start, 1), "text": s.text.strip()} for s in snippets if s.text.strip()]
        res = {"source": "caption", "segments": segs, "text": " ".join(x["text"] for x in segs)}
        ttl = 7 * 86400
    except Exception as e:
        res = {"source": "none", "segments": [], "text": "", "error": type(e).__name__}
        ttl = 6 * 3600  # 일시적 실패일 수 있으므로 짧게
    _cache.set(key, res, expire=ttl)
    return res


def enrich_with_transcripts(videos: List[Dict[str, Any]], sleep_s: float = 0.4) -> List[Dict[str, Any]]:
    out = []
    for v in videos:
        tr = get_transcript(v["video_id"])
        v = dict(v)
        if tr["text"]:
            v["source_text"] = f"{v.get('title','')} {tr['text']}"
            v["text_source"] = "caption"
        else:
            v["source_text"] = f"{v.get('title','')} {v.get('description','')}"
            v["text_source"] = "meta"  # 자막 없음: 제목+설명으로 대체 (신뢰도 낮음)
        v["transcript"] = tr
        out.append(v)
        time.sleep(sleep_s)
    return out


# ───────────────────────── 스키마 ─────────────────────────
class Fact(BaseModel):
    video_id: str
    domain: str = Field(description="기초/스킨케어 | 색조/메이크업 | 헤어/바디 | 기타/뷰티무관 중 하나")
    format_tag: str = Field(description="영상 포맷 태그: 비포/애프터 실험형 | 올영 추천 리스트형 | 응급처치 루틴형 | 믹싱 꿀팁형 | 겟레디윗미 | 제품 리뷰형 | 기타 중 하나")
    what_happens: str = Field(description="영상에서 실제로 일어나는 일 한 문장(60자 이내). 제공된 제목·자막에 있는 내용만")
    product_types: List[str] = Field(description="영상에 실제 등장하는 제품군. 없으면 빈 리스트")
    hook_quote: str = Field(description="초반 훅 문장을 제목/자막 원문 그대로 복사(수정 금지). 없으면 빈 문자열")
    evidence_quote: str = Field(description="what_happens를 뒷받침하는 제목/자막 원문 그대로 복사(수정 금지)")


class FactSheet(BaseModel):
    facts: List[Fact]
    market_patterns: List[str] = Field(
        default_factory=list,
        description="전체 영상에서 반복되는 이번 주 K-뷰티 시장 바이럴 패턴 2~3개 문장 (제공된 영상 내용에 근거한 패턴만)",
    )


class Judgement(BaseModel):
    video_id: str
    decision: str = Field(description="Go | Pivot | Drop")
    score: int = Field(description="1~5. Go=4~5, Pivot=3, Drop=1~2")
    reason: str = Field(description="판정 근거 1~2문장. 제품 확인 문구와 어떻게 연결/충돌하는지 명시")
    linked_claim: str = Field(description="연결한 제품 '확인된 문구'를 원문 그대로 복사. 연결 없으면 빈 문자열")


class JudgementSheet(BaseModel):
    judgements: List[Judgement]


class Storyboard(BaseModel):
    video_id: str
    hook: str = Field(description="첫 3초: 화면/행동/자막")
    before: str = Field(description="비포 공감 상황")
    product_moment: str = Field(description="제품이 등장하는 순간. 확인된 문구 범위 안에서만")
    cta: str = Field(description="구매/참여 유도")
    creator_note: str = Field(description="인플루언서 전달 주의사항(쓰면 안 되는 표현 포함)")


class BriefSheet(BaseModel):
    briefs: List[Storyboard]


# ───────────────────────── LLM 호출 ─────────────────────────
def make_llm(api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite", temperature: float = 0.2):
    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY가 없습니다.")
    return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=temperature)


def _invoke(llm, schema, prompt: str, retries: int = 3):
    structured = llm.with_structured_output(schema)
    last = None
    for i in range(retries):
        try:
            return structured.invoke(prompt)
        except Exception as e:
            last = e
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                if "prepayment" in msg.lower():
                    raise
                time.sleep(15 * (i + 1))
                continue
            raise
    raise last


# ───────────────────────── Step 1. 팩트 추출 (브랜드 정보 없음) ─────────────────────────
def extract_facts(llm, videos: List[Dict[str, Any]]) -> FactSheet:
    blocks = []
    for v in videos:
        blocks.append(
            f"[video_id={v['video_id']}] 제목: {v.get('title','')} | 채널: {v.get('channel_title','')} | "
            f"조회수: {v.get('views',0):,} | 일평균: {v.get('views_per_day', 0):,} | 텍스트출처: {v['text_source']}\n"
            f"텍스트: {v['source_text'][:900]}"
        )
    prompt = (
        "당신은 브랜드를 모르는 뷰티 시장 리서처입니다. 아래 한국 유튜브 쇼츠 각각에 대해, "
        "제공된 제목·자막에 실제로 있는 내용만으로 '영상에서 일어나는 일'을 정리하고, "
        "전체 영상에서 반복되는 시장 패턴을 요약하세요.\n"
        "규칙:\n"
        "- 제공된 텍스트에 없는 내용은 추측하지 마세요. 불분명하면 domain을 '기타/뷰티무관'으로.\n"
        "- hook_quote, evidence_quote는 위 텍스트에서 원문 그대로 복사하세요(고쳐 쓰기 금지).\n"
        "- domain 구분: 토너·세럼·크림·패드·마스크·세안 등 피부 관리=기초/스킨케어, "
        "쿠션·파운데이션·블러셔·틴트·립·섀도 등=색조/메이크업.\n"
        f"- format_tag는 반드시 다음 중 하나를 선택하세요: {' | '.join(FORMAT_TAGS)}\n"
        "- market_patterns는 위 영상 전체에서 반복되는 포맷·고민·소비자 반응 패턴을 2~3개 문장으로 정리하세요(제공된 영상에 없는 트렌드 추측 금지).\n"
        "- 입력된 모든 video_id에 대해 하나씩 반환하세요.\n\n" + "\n\n".join(blocks)
    )
    return _invoke(llm, FactSheet, prompt)


def audit_facts(facts: List[Fact], videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {v["video_id"]: v for v in videos}
    out = []
    for f in facts:
        v = by_id.get(f.video_id)
        flags = []
        if v is None:
            continue  # 존재하지 않는 ID는 버림
        src = _norm(v["source_text"])
        ev_ok = bool(f.evidence_quote) and _norm(f.evidence_quote) in src
        hk_ok = bool(f.hook_quote) and _norm(f.hook_quote) in src
        if not ev_ok:
            flags.append("evidence_quote가 원문에 없음 → 근거 불충분")
        if f.hook_quote and not hk_ok:
            flags.append("hook_quote가 원문에 없음 → 삭제")
        domain = f.domain if f.domain in DOMAINS else "기타/뷰티무관"
        format_tag = f.format_tag if f.format_tag in FORMAT_TAGS else "기타"
        out.append({
            **f.model_dump(),
            "domain": domain,
            "format_tag": format_tag,
            "hook_quote": f.hook_quote if hk_ok else "",
            "evidence_ok": ev_ok,
            "text_source": v["text_source"],
            "flags": flags,
        })
    return out


# ───────────────────────── Step 2. 브랜드 판정 ─────────────────────────
def _decision_from_score(score: int) -> str:
    return "Go" if score >= 4 else "Pivot" if score == 3 else "Drop"


def judge_fit(llm, facts: List[Dict[str, Any]], product_name: str, products: Dict[str, Any]) -> List[Dict[str, Any]]:
    p = products[product_name]
    usable = [f for f in facts if f["evidence_ok"]]
    if not usable:
        return []
    fact_lines = "\n".join(
        f"- [video_id={f['video_id']}] 영역={f['domain']} | 포맷={f.get('format_tag', '기타')} | "
        f"내용={f['what_happens']} | 등장제품군={', '.join(f['product_types']) or '-'}"
        for f in usable
    )
    prompt = (
        f"당신은 '{product_name}' 담당 인하우스 마케터입니다. 아래 시장 팩트 각각이 이 제품 캠페인에 쓸 만한지 냉정하게 판정하세요.\n\n"
        f"[제품 확인된 문구 — 이것만 근거로 사용]\n" + "\n".join(f"- {c}" for c in p["verified_claims"]) + "\n"
        f"[적합 영역 (fit_territory)] {', '.join(p['fit_territory'])}\n"
        f"[부적합 영역 (non_fit_territory)] {', '.join(p['non_fit_territory'])}\n\n"
        "판정 기준:\n"
        "- Go(4~5): 영상의 행동·포맷이 제품의 적합 영역 및 확인된 문구와 직접 연결되어 그대로 캠페인 훅으로 쓸 수 있음\n"
        "- Pivot(3): 일부만 연결되어 서브 테스트 수준\n"
        "- Drop(1~2): 부적합 영역(non_fit_territory)에 해당하거나 영역이 다르거나 억지로 엮어야 함. 억지 연결은 소비자에게 조롱당함\n"
        "- 대부분을 Go로 주면 기준이 느슨한 것입니다. 확인된 문구로 연결 근거를 못 대면 Go를 주지 마세요.\n"
        "- linked_claim은 위 확인된 문구를 원문 그대로 복사하세요. 위에 없는 제품 특징을 만들어내지 마세요.\n"
        "- 예시(참고): '립틴트 바르는 법' 또는 '블러셔 믹싱' 영상 + 수분 토너 → Drop(부적합 영역, 연결 문구 없음).\n\n"
        "[시장 팩트]\n" + fact_lines
    )
    js = _invoke(llm, JudgementSheet, prompt).judgements
    claims_blob = _norm(" ".join(p["verified_claims"]))
    fact_by_id = {f["video_id"]: f for f in usable}
    out = []
    for j in js:
        f = fact_by_id.get(j.video_id)
        if f is None:
            continue
        flags = []
        score = max(1, min(5, int(j.score)))
        reason = j.reason
        # 규칙 1: 영역 불일치는 무조건 Drop (설명 가능한 하드 규칙)
        if f["domain"] != DOMAIN_BASE:
            if score > 2:
                flags.append(f"규칙 적용: 영역이 '{f['domain']}'이라 제품 영역과 달라 Drop 처리 (LLM 점수 {score})")
            score = min(score, 1)
            reason = f"[규칙] 영상 영역이 '{f['domain']}'로 제품 영역({DOMAIN_BASE})과 다름. " + reason
        # 규칙 2: 연결 문구가 확인된 문구에 없으면 Go 불가
        linked_ok = bool(j.linked_claim) and _norm(j.linked_claim) in claims_blob
        if score >= 4 and not linked_ok:
            flags.append("확인된 제품 문구와 연결 근거 없음 → Go를 Pivot으로 강등")
            score = 3
        decision = _decision_from_score(score)
        if decision != j.decision:
            flags.append(f"LLM 판정 '{j.decision}'과 점수 기준 판정 '{decision}' 불일치 → 점수 기준으로 통일")
        out.append({
            "video_id": j.video_id, "decision": decision, "score": score, "reason": reason,
            "linked_claim": j.linked_claim if linked_ok else "", "flags": flags,
        })
    return out


# ───────────────────────── Step 3. 브리프 (Go만) ─────────────────────────
NUM_TOKEN = re.compile(r"\d[\d,\.]*\s*(?:%|ppm|mm|ml|배속|스킨|겹|중)")


def _brief_violations(b: Storyboard, product: Dict[str, Any]) -> List[str]:
    text = " ".join([b.hook, b.before, b.product_moment, b.cta, b.creator_note])
    claims = " ".join(product["verified_claims"])
    v = []
    for bad in product.get("unverified_removed_from_v1", []):
        if _norm(bad) and _norm(bad) in _norm(text):
            v.append(f"확인되지 않은 문구 사용: {bad}")
    for tok in NUM_TOKEN.findall(text):
        if _norm(tok) not in _norm(claims):
            v.append(f"출처 없는 수치 표현: {tok}")
    return v


def write_briefs(llm, go_items: List[Dict[str, Any]], facts: Dict[str, Dict[str, Any]],
                 product_name: str, products: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not go_items:
        return []
    p = products[product_name]
    lines = "\n".join(
        f"- [video_id={g['video_id']}] 트렌드={facts[g['video_id']]['what_happens']} | 훅원문={facts[g['video_id']]['hook_quote'] or '-'} | 연결문구={g['linked_claim']}"
        for g in go_items
    )

    def build(feedback: str = "") -> str:
        return (
            f"'{product_name}' 인하우스 마케터가 인플루언서에게 그대로 전달할 숏폼 브리프를 작성하세요.\n"
            f"[사용 가능한 제품 문구 — 이 범위 밖의 효능·수치·순위·임상 표현 금지]\n"
            + "\n".join(f"- {c}" for c in p["verified_claims"]) + "\n"
            f"[금지 문구] {', '.join(p.get('unverified_removed_from_v1', []))}\n"
            "각 트렌드의 바이럴 방식을 따르되 제품과 자연스럽게 연결되는 부분만 쓰세요.\n"
            + (f"[이전 시도 위반 — 반드시 수정]\n{feedback}\n" if feedback else "")
            + "\n[Go 판정 트렌드]\n" + lines
        )

    briefs = _invoke(llm, BriefSheet, build()).briefs
    out = []
    pending = {b.video_id: b for b in briefs}
    viol = {vid: _brief_violations(b, p) for vid, b in pending.items()}
    if any(viol.values()):
        fb = "\n".join(f"- {vid}: {', '.join(vs)}" for vid, vs in viol.items() if vs)
        retry = {b.video_id: b for b in _invoke(llm, BriefSheet, build(fb)).briefs}
        for vid in list(pending):
            if viol[vid] and vid in retry:
                pending[vid] = retry[vid]
                viol[vid] = _brief_violations(retry[vid], p)
    for vid, b in pending.items():
        if vid not in facts:
            continue
        out.append({**b.model_dump(), "violations": viol.get(vid, []), "needs_review": bool(viol.get(vid))})
    return out


# ───────────────────────── Step 3-2. 즉시 복사 가능한 2종 마크다운 ─────────────────────────
def format_copyable_outputs(result: Dict[str, Any]) -> Dict[str, str]:
    """팀장/슬랙 보고용 1페이지 요약 + 인플루언서/대행사 전달용 촬영 가이드 생성."""
    product_name = result.get("product", "")
    videos = result.get("videos", [])
    facts = result.get("facts", [])
    judgements = result.get("judgements", [])
    briefs = result.get("briefs", [])
    stats = result.get("stats", {})
    market_patterns = result.get("market_patterns", [])

    v_by_id = {v["video_id"]: v for v in videos}
    f_by_id = {f["video_id"]: f for f in facts}
    b_by_id = {b["video_id"]: b for b in briefs}

    products = load_products()
    prod_info = products.get(product_name, {})
    banned_list = prod_info.get("unverified_removed_from_v1", [])

    total_v = stats.get("videos", len(videos))
    caption_v = stats.get("transcript_caption", sum(1 for v in videos if v.get("text_source") == "caption"))
    caption_pct = round(caption_v / max(1, total_v) * 100, 1)

    go_items = sorted(
        [j for j in judgements if j["decision"] == "Go"],
        key=lambda j: (-j["score"], -v_by_id.get(j["video_id"], {}).get("views", 0)),
    )
    pivot_items = [j for j in judgements if j["decision"] == "Pivot"]
    drop_items = [j for j in judgements if j["decision"] == "Drop"]

    # 1) 팀장/슬랙 보고용 1페이지 요약 (internal_report_md)
    rep: List[str] = [
        f"# [주간 K-뷰티 쇼츠 트렌드 보고] {product_name}",
        f"- **수집 현황**: 총 {total_v}건 (자막 확보 {caption_v}건 / {caption_pct}%) | "
        f"**판정**: Go {len(go_items)}건 · Pivot {len(pivot_items)}건 · Drop {len(drop_items)}건",
        "",
        "## 1. 이번 주 시장 바이럴 패턴",
    ]
    if market_patterns:
        for idx, pat in enumerate(market_patterns, 1):
            rep.append(f"{idx}. {pat}")
    else:
        rep.append("- 추출된 공통 시장 패턴 없음")

    rep.append("")
    rep.append("## 2. Go 추천 캠페인 컨셉")
    if go_items:
        for idx, j in enumerate(go_items, 1):
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            b = b_by_id.get(vid)
            views = v.get("views", 0)
            vpd = v.get("views_per_day", views)
            like_rate = v.get("like_rate", 0.0)
            quote = f.get("hook_quote") or f.get("evidence_quote") or "-"
            src_tag = "자막 원문" if f.get("text_source") == "caption" else "제목/설명"

            rep.extend([
                f"### Go #{idx}. {v.get('title', vid)} (`{vid}`)",
                f"- **레퍼런스**: https://youtube.com/shorts/{vid} | 채널: {v.get('channel_title', '-')}",
                f"- **지표**: 조회수 {views:,}회 | 일평균 {vpd:,}회/일 | 좋아요율 {like_rate:.2f}% | 포맷: `{f.get('format_tag', '기타')}`",
                f"- **Go 근거 ({j['score']}점)**: {j['reason']}",
                f"- **연결 제품 문구**: {j.get('linked_claim') or '-'}",
                f"- **원문 인용 ({src_tag})**: \"{quote}\"",
            ])
            if b:
                rep.append(f"- **핵심 훅/제품 침투**: {b['hook']} → {b['product_moment']}")
            rep.append("")
    else:
        rep.append("- 이번 수집 배치에서 Go 판정 컨셉이 없습니다.")
        rep.append("")

    if pivot_items:
        rep.append("## 3. Pivot 검토 컨셉 (서브 테스트)")
        for j in pivot_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            rep.append(
                f"- **{v.get('title', vid)[:45]}** (`{vid}`, {v.get('views', 0):,}회, `{f.get('format_tag', '기타')}`): {j['reason']}"
            )
        rep.append("")

    rep.append(f"## 4. Drop 제외 요약 ({len(drop_items)}건)")
    if drop_items:
        for j in drop_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            rep.append(
                f"- [{f.get('domain', '-')}] {v.get('title', vid)[:45]} (`{vid}`): {j['reason']}"
            )
    else:
        rep.append("- Drop 제외 항목 없음")

    internal_report_md = "\n".join(rep).strip()

    # 2) 인플루언서/대행사 전달용 촬영 가이드 (creator_guide_md)
    guide: List[str] = [
        f"# [크리에이터 촬영 가이드] {product_name}",
        "> 아래 가이드는 실제 바이럴 쇼츠 포맷과 확인된 제품 정보(`products.json`)만을 기반으로 작성되었습니다.",
        "",
    ]
    if briefs:
        for idx, b in enumerate(briefs, 1):
            vid = b["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            guide.extend([
                f"## 컨셉 #{idx}. [{f.get('format_tag', '기타')}] {v.get('title', vid)}",
                f"- **참고 레퍼런스**: https://youtube.com/shorts/{vid} (조회수 {v.get('views', 0):,}회 / 일평균 {v.get('views_per_day', 0):,}회)",
                f"- **첫 3초 훅**: {b['hook']}",
                f"- **비포 상황**: {b['before']}",
                f"- **제품 침투 시점**: {b['product_moment']}",
                f"- **CTA**: {b['cta']}",
                f"- **주의사항 및 금지 표현**: {b['creator_note']}",
            ])
            if banned_list:
                guide.append(f"- **절대 사용 금지 문구 (미확인/과대광고 방지)**: {', '.join(banned_list)}")
            if b.get("needs_review"):
                guide.append(f"- **[검수 필요 경고]**: {'; '.join(b.get('violations', []))}")
            guide.append("")
    else:
        guide.append("- 이번 수집 배치에서 Go 판정 컨셉이 없어 촬영 가이드가 생성되지 않았습니다.")
        if banned_list:
            guide.append(f"- **참고 금지 표현**: {', '.join(banned_list)}")

    creator_guide_md = "\n".join(guide).strip()
    return {
        "internal_report_md": internal_report_md,
        "creator_guide_md": creator_guide_md,
    }


# ───────────────────────── 전체 실행 ─────────────────────────
def run_pipeline(videos: List[Dict[str, Any]], product_name: str, llm=None,
                 api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite",
                 max_videos: int = 10, max_briefs: int = 3) -> Dict[str, Any]:
    products = load_products()
    llm = llm or make_llm(api_key, model)
    vids = enrich_with_transcripts(videos[:max_videos])

    fact_sheet = extract_facts(llm, vids)
    raw_facts = fact_sheet.facts
    market_patterns = [p.strip() for p in (fact_sheet.market_patterns or []) if p and p.strip()][:3]
    facts = audit_facts(raw_facts, vids)
    judgements = judge_fit(llm, facts, product_name, products)

    fact_by_id = {f["video_id"]: f for f in facts}
    go = sorted([j for j in judgements if j["decision"] == "Go"],
                key=lambda j: (-j["score"], -next((v["views"] for v in vids if v["video_id"] == j["video_id"]), 0)))[:max_briefs]
    briefs = write_briefs(llm, go, fact_by_id, product_name, products)

    stats = {
        "videos": len(vids),
        "transcript_caption": sum(1 for v in vids if v["text_source"] == "caption"),
        "facts": len(facts),
        "evidence_verified": sum(1 for f in facts if f["evidence_ok"]),
        "go": sum(1 for j in judgements if j["decision"] == "Go"),
        "pivot": sum(1 for j in judgements if j["decision"] == "Pivot"),
        "drop": sum(1 for j in judgements if j["decision"] == "Drop"),
        "briefs": len(briefs),
        "briefs_need_review": sum(1 for b in briefs if b["needs_review"]),
    }
    result: Dict[str, Any] = {
        "product": product_name, "videos": vids, "facts": facts,
        "market_patterns": market_patterns,
        "judgements": judgements, "briefs": briefs, "stats": stats,
        "product_confidence": products[product_name].get("confidence", "unknown"),
    }
    copyables = format_copyable_outputs(result)
    result.update(copyables)
    return result
