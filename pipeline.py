"""pipeline.py — 마케터 업무 프로세스 기반 4단계 파이프라인 (v2)

Step1 팩트 추출  : 브랜드 정보 없이, 제목·자막만으로 '영상에서 실제로 일어나는 일'을 추출
Step2 브랜드 판정: 팩트 vs 제품(확인된 문구만) → Go / Pivot / Drop (규칙 + LLM)
Step3 브리프     : Go 판정에만 4단 콘티 (확인된 제품 문구만 사용)
Step4 감사       : 코드로 검증 (인용문이 실제 자막에 있는지, 점수-판정 일관성, 금지 문구)
"""
import html as _html
import json
import os
import re
import time
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional

import diskcache
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

import history_store

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


def upsert_product_from_text(
    name: str,
    raw_claims_text: str,
    fit_territory_csv: str = "",
    non_fit_territory_csv: str = "",
    source_url: str = "",
    save_to_file: bool = True,
    products_path: Optional[str] = None,
) -> Dict[str, Any]:
    """공식 상세페이지 원문 문구를 파싱해 products.json에 등록/승격합니다.
    화장품법 금지어 또는 미확인 금지 문구가 포함된 줄은 verified_claims에 절대 넣지 않고 rejected_claims로 격리합니다.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("제품명을 입력해야 합니다.")

    raw_lines: List[str] = []
    for line in (raw_claims_text or "").splitlines():
        cleaned = re.sub(r"^\s*[-•*·]\s*", "", line).strip()
        if cleaned:
            raw_lines.append(cleaned)
    if not raw_lines:
        raise ValueError("최소 1개 이상의 공식 확인 문구를 입력해야 합니다.")

    fit_list = [x.strip() for x in (fit_territory_csv or "").split(",") if x.strip()]
    non_fit_list = [x.strip() for x in (non_fit_territory_csv or "").split(",") if x.strip()]

    path = products_path or os.path.join(BASE, "products.json")
    full_doc: Dict[str, Any] = {"_meta": {}, "products": {}}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            full_doc = json.load(f)

    existing = full_doc.get("products", {}).get(clean_name, {})
    existing_banned = [
        _clean_banned_for_creator(x)
        for x in existing.get("unverified_removed_from_v1", [])
        if _clean_banned_for_creator(x)
    ]

    # 화장품법 제13조 금지어 및 미확인 금지 문구 검사 → 적발된 줄은 verified_claims에서 완전 격리
    accepted_claims: List[str] = []
    rejected_claims: List[str] = []
    warnings: List[str] = []
    for c in raw_lines:
        nc = _norm(c)
        hit_terms: List[str] = []
        for term in COSMETIC_LAW_BANNED_TERMS:
            nt = _norm(term)
            if nt and nt in nc:
                hit_terms.append(term)
        for bad in existing_banned:
            nb = _norm(bad)
            if nb and nb in nc:
                hit_terms.append(bad)
        if hit_terms:
            rejected_claims.append(c)
            warnings.append(
                f"금지 표현 격리({', '.join(dict.fromkeys(hit_terms))}): \"{c[:50]}\""
            )
        else:
            accepted_claims.append(c)

    if not accepted_claims:
        raise ValueError("화장품법 금지 표현이 포함되어 저장할 수 없습니다.")

    warnings = list(dict.fromkeys(warnings))
    # 격리된 문구가 1건 이상 있으면 confidence를 high로 승격하지 않고 medium 유지
    confidence = "medium" if rejected_claims else "high"
    entry: Dict[str, Any] = {
        "confidence": confidence,
        "verified_claims": accepted_claims,
        "unverified_removed_from_v1": existing.get("unverified_removed_from_v1", []),
        "fit_territory": fit_list or existing.get("fit_territory", ["기초 스킨케어"]),
        "non_fit_territory": non_fit_list or existing.get("non_fit_territory", ["색조 메이크업", "헤어/바디"]),
        "source_url": (source_url or "").strip(),
        "updated_at": date.today().isoformat(),
    }

    if save_to_file:
        full_doc.setdefault("products", {})[clean_name] = entry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(full_doc, f, ensure_ascii=False, indent=2)

    return {
        "product_name": clean_name,
        "entry": entry,
        "warnings": warnings,
        "rejected_claims": rejected_claims,
        "saved": save_to_file,
    }


_CAPTION_NOISE_RE = re.compile(r"\[[^\]]{1,15}\]|>>")


def _norm(s: str) -> str:
    cleaned = _CAPTION_NOISE_RE.sub(" ", s or "")
    return re.sub(r"[\s\W_]+", "", cleaned).lower()


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


def _ensure_video_metrics(v: Dict[str, Any]) -> Dict[str, Any]:
    """캐시 등 외부 입력에 views_per_day/like_rate가 누락된 경우 published_at 기반으로 보완합니다."""
    v = dict(v)
    views = int(v.get("views", 0))
    likes = int(v.get("likes", 0))
    if "days_since_published" not in v or "views_per_day" not in v:
        pub_raw = v.get("published_at", "")
        now_utc = datetime.now(timezone.utc)
        try:
            pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            elapsed_hours = max(0.0, (now_utc - pub_dt).total_seconds() / 3600.0)
            days_since = round(max(0.25, elapsed_hours / 24.0), 2)
        except Exception:
            days_since = 1.0
        v["days_since_published"] = days_since
        v["views_per_day"] = int(round(views / days_since))
    if "like_rate" not in v:
        v["like_rate"] = round(likes / max(1, views) * 100, 2)
    return v


def enrich_with_transcripts(videos: List[Dict[str, Any]], sleep_s: float = 0.4) -> List[Dict[str, Any]]:
    out = []
    for v in videos:
        v = _ensure_video_metrics(v)
        tr = get_transcript(v["video_id"])
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
    hook_quote: str = Field(description="초반 훅 문장을 제목/자막 원문 그대로 복사(수정·창작 금지). 없으면 빈 문자열")
    evidence_quote: str = Field(description="분석의 근거가 되는 제목/자막 원문 그대로 복사(수정·창작 금지)")
    domain: str = Field(description="기초/스킨케어 | 색조/메이크업 | 헤어/바디 | 기타/뷰티무관 중 하나")
    format_tag: str = Field(description="영상 포맷 태그: 비포/애프터 실험형 | 올영 추천 리스트형 | 응급처치 루틴형 | 믹싱 꿀팁형 | 겟레디윗미 | 제품 리뷰형 | 기타 중 하나")
    what_happens: str = Field(description="영상에서 실제로 일어나는 일 한 문장(60자 이내). 제공된 제목·자막에 있는 내용만")
    viral_reason: str = Field(
        default="",
        description="왜 반응이 나왔는지 2~3문장(110~180자): [① 건드린 시청자 고민/심리] + [② 권위·가성비·반전·시즌 키워드 등 후킹/유지 장치] + [③ 제공된 조회수·구독자 대비·평소 대비 수치 근거]. 제공된 텍스트·수치에 없는 사실·성분·효능 추측 절대 금지",
    )
    apply_point: str = Field(
        default="",
        description="마케터가 자사 제품에 바로 적용할 수 있는 숏폼 기획·카피 포인트 1문장(70자 이내)",
    )
    product_types: List[str] = Field(description="영상에 실제 등장하는 제품군. 없으면 빈 리스트")


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
    copy_ideas: List[str] = Field(default_factory=list, description="바로 쓸 마케팅 카피 3종")


class BriefSheet(BaseModel):
    briefs: List[Storyboard]


# ───────────────────────── LLM 호출 ─────────────────────────
def make_llm(
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash-lite",
    temperature: float = 0.2,
    thinking_budget: Optional[int] = None,
):
    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY가 없습니다.")
    kwargs: Dict[str, Any] = {"model": model, "google_api_key": key, "temperature": temperature}
    if thinking_budget is not None and "2.5" in str(model):
        kwargs["thinking_budget"] = int(thinking_budget)
    return ChatGoogleGenerativeAI(**kwargs)


def _invoke(llm, schema, prompt: str, retries: int = 3):
    structured = llm.with_structured_output(schema)
    last = None
    for i in range(retries):
        try:
            return structured.invoke(prompt)
        except Exception as e:
            last = e
            msg = str(e)
            low = msg.lower()
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                # 일일 무료 한도 소진(RPD)이나 선불 크레딧 소진은 기다려도 안 풀리므로 즉시 중단
                if (
                    "prepayment" in low
                    or "per day" in low
                    or "free_tier_requests" in low
                    or "limit: 0" in low
                ):
                    raise
                time.sleep(5 * (i + 1))
                continue
            raise
    raise last


# ───────────────────────── Step 1. 팩트 추출 (브랜드 정보 없음) ─────────────────────────
def extract_facts(llm, videos: List[Dict[str, Any]]) -> FactSheet:
    blocks = []
    for v in videos:
        promo = "광고" if v.get("has_paid_promotion") else "오가닉"
        sub_cnt = int(v.get("subscriber_count") or 0)
        sub_ratio = float(v.get("views_per_subscriber") or 0)
        avg_ratio = float(v.get("views_vs_channel_avg") or 0)
        blocks.append(
            f"[video_id={v['video_id']}] 제목: {v.get('title','')} | 채널: {v.get('channel_title','')} (구독자 {sub_cnt:,}명) | "
            f"조회수: {v.get('views',0):,} | 일평균: {v.get('views_per_day', 0):,} | "
            f"평소 대비: {avg_ratio:.1f}배 | 구독자 대비: {sub_ratio:.1f}배 | 유형: {promo} | 텍스트출처: {v['text_source']}\n"
            f"텍스트: {v['source_text'][:550]}"
        )
    prompt = (
        "당신은 올리브영 출신 10년차 K-뷰티 숏폼 마케팅 전략가입니다. 아래 한국 유튜브 쇼츠 각각에 대해 "
        "제공된 제목·자막·수치만으로 '초반 시선 고정 포인트'와 '왜 반응이 나왔는지'를 날카롭게 분석하고, "
        "고조회수·급상승 영상들의 공통점을 종합해 메인 인사이트 요약을 도출하세요.\n"
        "규칙 (할루시네이션 절대 방지):\n"
        "- [Quote-First 원칙] 반드시 hook_quote와 evidence_quote를 위 텍스트에서 원문 그대로 먼저 복사한 뒤(고쳐 쓰기·창작 금지), 그 근거 범위 안에서만 what_happens·viral_reason·apply_point를 작성하세요.\n"
        "- 제공된 텍스트·수치에 없는 성분, 효능, 임상 결과, 브랜드 배경 스토리는 절대 추측·창작하지 마세요. 자막이 없는(meta) 영상은 제목·설명과 실제 수치(구독자 대비·평소 대비·오가닉/광고)에서 확인되는 사실만 근거로 분석하세요.\n"
        "- 뷰티와 무관한 영상(알바썰·뉴스·음식·게임 등)만 domain을 '기타/뷰티무관'으로 분류하세요.\n"
        "- domain 구분: 토너·세럼·크림·패드·마스크·세안 등 피부 관리=기초/스킨케어, "
        "쿠션·파운데이션·블러셔·틴트·립·섀도 등=색조/메이크업, 샴푸·바디=헤어/바디. "
        "올리브영·다이소 추천템 종합 영상처럼 여러 뷰티 카테고리가 섞인 경우는 가장 비중이 큰 뷰티 영역(기초/스킨케어, 색조/메이크업, 헤어/바디) 중 하나로 분류하세요.\n"
        f"- format_tag는 반드시 다음 중 하나를 선택하세요: {' | '.join(FORMAT_TAGS)}\n"
        "- [viral_reason 작성 규칙] '자신의 인생템을 소개한다' 같은 뻔한 줄거리 요약 금지! 반드시 2~3문장(110~180자) 안에 "
        "① 건드린 시청자 고민/결핍 + ② 권위(청담샵·원장)·초저가 대비(다이소 5천원)·반전·시즌 검색어(올영 블프/내돈내산) 등 클릭/시청 유지 장치 + ③ 실제 수치 근거(조회수·구독자 대비 N배·평소 대비 N배)를 구체적으로 쓰세요.\n"
        "- [apply_point 작성 규칙] 마케터가 자사 제품에 바로 적용할 수 있는 포맷·후킹 공식 1문장(70자 이내)을 쓰세요.\n"
        "- [market_patterns 작성 절대 규칙] 메인 화면 상단 인사이트 요약 영역에 그대로 노출됩니다. 단순 단어·명사구 나열 금지! "
        "고조회수·급상승 영상들의 공통점을 종합해 [① 공통 연출/포맷/키워드] + [② 시청자 심리·시즌 맥락] + [③ 실제 상위 영상 제목·수치 근거] 3요소를 담은 "
        "완성된 1~2문장(50~115자) 3개로 작성하세요. "
        "단, 조회수 1만 미만 또는 좋아요율 1% 미만인 영상군을 '폭발적 인기'로 과장하지 말고 '초기 반응/저유입 참고 수준'으로 정직하게 쓰세요.\n"
        "- [K-뷰티 사실 기준] 올영세일은 연 4회(3·6·9·12월 분기 1회 약 7일간)이며, 올영데이 일정은 매월 변동되므로 특정 날짜를 임의로 단정하지 마세요. 한국 숏폼 유행어: "
        "'밤티'=못생기고 촌스럽거나 구린 비주얼(부정 표현, 절대 '밤에 좋은'으로 오역 금지), "
        "'느좋'=느낌 좋다, '추구미'=추구하는 이미지, '톤그로'=피부톤과 안 어울림, '화잘먹'=화장이 잘 먹는 피부.\n"
        "- 입력된 모든 video_id에 대해 하나도 누락 없이 반환하세요.\n\n" + "\n\n".join(blocks)
    )
    return _invoke(llm, FactSheet, prompt)


def audit_facts(facts: List[Fact], videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {v["video_id"]: v for v in videos}
    seen_ids = set()
    out = []
    for f in facts:
        v = by_id.get(f.video_id)
        if v is None or f.video_id in seen_ids:
            continue  # 존재하지 않는 ID나 중복은 버림
        seen_ids.add(f.video_id)
        flags = []
        src = _norm(v["source_text"])
        ev_norm = _norm(f.evidence_quote)
        hk_norm = _norm(f.hook_quote)
        ev_ok = len(ev_norm) >= 4 and ev_norm in src
        hk_ok = len(hk_norm) >= 4 and hk_norm in src
        if not ev_ok:
            flags.append("evidence_quote가 원문에 없음(또는 너무 짧음) → 근거 불충분")
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
    # LLM이 누락한 영상도 보고서 총합 정합성을 위해 명시적으로 포함
    for v in videos:
        vid = v["video_id"]
        if vid not in seen_ids:
            out.append({
                "video_id": vid,
                "domain": "기타/뷰티무관",
                "format_tag": "기타",
                "what_happens": "(팩트 추출 누락)",
                "viral_reason": "",
                "apply_point": "",
                "product_types": [],
                "hook_quote": "",
                "evidence_quote": "",
                "evidence_ok": False,
                "text_source": v.get("text_source", "meta"),
                "flags": ["LLM 팩트 추출 누락 → 근거 불충분"],
            })
    return out


# ───────────────────────── Step 2. 브랜드 판정 ─────────────────────────
def _decision_from_score(score: int) -> str:
    return "Go" if score >= 4 else "Pivot" if score == 3 else "Drop"


# non_fit_territory 항목별 한국어 뷰티 실무 키워드 확장 매핑
NON_FIT_KEYWORD_MAP: Dict[str, List[str]] = {
    "색조": ["색조", "립틴트", "틴트", "블러셔", "립스틱", "립글로스", "섀도", "아이라이너", "속눈썹", "쉐딩", "컨실러", "퍼스널컬러"],
    "블러셔": ["블러셔", "틴트", "믹싱"],
    "틴트": ["틴트", "립틴트", "립스틱"],
    "헤어": ["헤어", "샴푸", "트리트먼트", "두피", "탈모"],
    "바디": ["바디워시", "바디로션", "바디미스트", "바디스크럽"],
    "각질": ["각질 제거", "각질제거", "필링", "스크럽", "필링젤", "aha", "bha", "pha", "아하", "바하", "파하", "피지 녹이", "블랙헤드 제거"],
    "미백": ["미백", "기미", "잡티", "화이트닝", "톤업"],
    "모공": ["모공", "블랙헤드", "화이트헤드", "피지 녹이", "블랙헤드 제거", "클렌징오일", "클렌징밤"],
    "피지": ["피지", "블랙헤드", "모공"],
}


def _find_non_fit_hits(fact: Dict[str, Any], non_fit_territory: List[str]) -> List[str]:
    """팩트의 행동/등장제품군이 products.json의 non_fit_territory와 명백히 충돌하는지 검사합니다."""
    blob = _norm(f"{fact.get('what_happens', '')} {' '.join(fact.get('product_types', []))}")
    if not blob:
        return []
    hits: List[str] = []
    for terr in non_fit_territory:
        terr_norm = _norm(terr)
        # 1) territory 원문 토큰 직접 체크
        if len(terr_norm) >= 2 and terr_norm in blob:
            hits.append(terr)
            continue
        # 2) 확장 키워드 체크
        for key, kws in NON_FIT_KEYWORD_MAP.items():
            if key in terr:
                for kw in kws:
                    if _norm(kw) in blob:
                        hits.append(f"{terr}({kw})")
                        break
    return list(dict.fromkeys(hits))


def _is_valid_linked_claim(linked_claim: str, verified_claims: List[str]) -> bool:
    """linked_claim이 2글자 부분일치 우회 없이 개별 verified_claim과 실질적으로 일치하는지 검증합니다."""
    norm_lc = _norm(linked_claim)
    if len(norm_lc) < 8:
        return False
    lc_tokens = {t for t in re.findall(r"[가-힣a-zA-Z0-9]{2,}", linked_claim or "")}
    for claim in verified_claims:
        norm_c = _norm(claim)
        if not norm_c:
            continue
        # 개별 확인 문구 내부에 8자 이상 정확히 포함되거나 반대로 포함하는 경우
        if norm_lc in norm_c or norm_c in norm_lc:
            return True
        # 핵심 토큰 겹침 비율 50% 이상 (최소 3개 토큰 이상 일치)
        c_tokens = {t for t in re.findall(r"[가-힣a-zA-Z0-9]{2,}", claim)}
        overlap = lc_tokens & c_tokens
        if len(overlap) >= 3 and (len(overlap) / max(1, len(lc_tokens))) >= 0.5:
            return True
    return False


def _expected_domain_from_category(product_category: str) -> str:
    """제품 카테고리(예: '기초 > 토너·패드', '색조 > 립·틴트')에서 기대 영역을 자동 매핑합니다."""
    cat = product_category or ""
    if any(k in cat for k in ("색조", "메이크업", "립", "틴트", "블러셔", "쿠션", "파데", "아이")):
        return "색조/메이크업"
    if any(k in cat for k in ("헤어", "바디")):
        return "헤어/바디"
    return DOMAIN_BASE


def apply_judgement_rules(
    raw_judgements: List[Judgement],
    facts: List[Dict[str, Any]],
    product: Dict[str, Any],
    expected_domain: str = DOMAIN_BASE,
) -> List[Dict[str, Any]]:
    """Step 2 LLM 판정에 결정론적 B2B 가드레일(영역·non_fit·linked_claim·자막유무·누락방지)을 적용합니다."""
    verified_claims = product.get("verified_claims", [])
    non_fit_territory = product.get("non_fit_territory", [])
    j_by_id = {j.video_id: j for j in raw_judgements}

    out: List[Dict[str, Any]] = []
    for f in facts:
        vid = f["video_id"]
        # 근거 검증 실패 영상도 증발시키지 않고 명시적으로 Drop 처리해 총합 100% 일치
        if not f.get("evidence_ok"):
            out.append({
                "video_id": vid,
                "decision": "Drop",
                "score": 1,
                "reason": "[자동 제외] 근거 인용 검증 실패로 제외",
                "linked_claim": "",
                "flags": ["근거 인용 검증 실패로 자동 Drop"],
            })
            continue

        j = j_by_id.get(vid)
        if j is None:
            out.append({
                "video_id": vid,
                "decision": "Drop",
                "score": 1,
                "reason": "[자동 제외] 판정 누락으로 제외",
                "linked_claim": "",
                "flags": ["LLM 판정 누락으로 자동 Drop"],
            })
            continue

        flags: List[str] = []
        score = max(1, min(5, int(j.score)))
        reason = j.reason

        # 규칙 1: 영역 불일치는 무조건 Drop (기초/색조/헤어바디 양방향 지원)
        if f["domain"] != expected_domain:
            if score > 2:
                flags.append(f"규칙 적용: 영역이 '{f['domain']}'이라 제품 영역({expected_domain})과 달라 Drop 처리 (LLM 점수 {score})")
            score = min(score, 1)
            reason = f"[규칙] 영상 영역이 '{f['domain']}'로 제품 영역({expected_domain})과 다름. " + reason

        # 규칙 2: 기초/스킨케어 내부라도 non_fit_territory 충돌 시 강제 Drop
        non_fit_hits = _find_non_fit_hits(f, non_fit_territory)
        if non_fit_hits and score > 2:
            flags.append(f"규칙 적용: 부적합 영역({', '.join(non_fit_hits)}) 충돌로 Drop 처리 (LLM 점수 {score})")
            score = min(score, 2)
            reason = f"[규칙] 부적합 영역({', '.join(non_fit_hits)}) 충돌. " + reason

        # 규칙 3: 연결 문구가 개별 verified_claim과 실질적으로 일치(8자 이상)하지 않으면 Go 불가
        linked_ok = _is_valid_linked_claim(j.linked_claim, verified_claims)
        if score >= 4 and not linked_ok:
            flags.append("확인된 제품 문구와 실질적 연결 근거 없음(8자 미만 또는 미일치) → Go를 Pivot으로 강등")
            score = 3

        # 규칙 4: 자막 없는 영상(text_source="meta")은 최대 Pivot(3점)으로 제한 (Go/촬영 가이드 직행 금지)
        if f.get("text_source") != "caption":
            if score >= 4:
                flags.append("자막 미확인(직접 시청 검증 필요) → Go를 Pivot으로 강등")
                score = 3
            else:
                flags.append("자막 미확인(직접 시청 검증 필요)")

        decision = _decision_from_score(score)
        if decision != j.decision:
            flags.append(f"LLM 판정 '{j.decision}'과 점수 기준 판정 '{decision}' 불일치 → 점수 기준으로 통일")
        out.append({
            "video_id": vid,
            "decision": decision,
            "score": score,
            "reason": reason,
            "linked_claim": j.linked_claim if linked_ok else "",
            "flags": flags,
        })
    return out


def judge_fit(
    llm,
    facts: List[Dict[str, Any]],
    product_name: str,
    products: Dict[str, Any],
    expected_domain: str = DOMAIN_BASE,
) -> List[Dict[str, Any]]:
    p = products[product_name]
    usable = [f for f in facts if f.get("evidence_ok")]
    if not usable:
        return apply_judgement_rules([], facts, p, expected_domain=expected_domain)
    fact_lines = "\n".join(
        f"- [video_id={f['video_id']}] 영역={f['domain']} | 포맷={f.get('format_tag', '기타')} | "
        f"텍스트출처={f.get('text_source', 'meta')} | 내용={f['what_happens']} | 등장제품군={', '.join(f['product_types']) or '-'}"
        for f in usable
    )
    prompt = (
        f"당신은 '{product_name}' ({expected_domain}) 담당 인하우스 마케터입니다. 아래 시장 팩트 각각이 이 제품 캠페인에 쓸 만한지 냉정하게 판정하세요.\n\n"
        f"[제품 확인된 문구 — 이것만 근거로 사용]\n" + "\n".join(f"- {c}" for c in p["verified_claims"]) + "\n"
        f"[적합 영역 (fit_territory)] {', '.join(p['fit_territory'])}\n"
        f"[부적합 영역 (non_fit_territory)] {', '.join(p['non_fit_territory'])}\n\n"
        "판정 기준:\n"
        "- Go(4~5): 자막(caption)으로 확인된 영상의 행동·포맷이 제품의 적합 영역 및 확인된 문구와 직접 연결되어 그대로 캠페인 훅으로 쓸 수 있음\n"
        "- Pivot(3): 일부만 연결되거나 자막이 없는(meta) 영상으로 마케터 직접 시청 후 서브 테스트 수준\n"
        "- Drop(1~2): 부적합 영역(non_fit_territory)에 해당하거나 영역이 다르거나 억지로 엮어야 함. 억지 연결은 소비자에게 조롱당함\n"
        "- 대부분을 Go로 주면 기준이 느슨한 것입니다. 확인된 문구로 연결 근거를 못 대면 Go를 주지 마세요.\n"
        "- linked_claim은 위 확인된 문구 중 하나를 8자 이상 원문 그대로 복사하세요. 위에 없는 제품 특징을 만들어내지 마세요.\n\n"
        "[시장 팩트]\n" + fact_lines
    )
    js = _invoke(llm, JudgementSheet, prompt).judgements
    return apply_judgement_rules(js, facts, p, expected_domain=expected_domain)


# ───────────────────────── Step 2-2. 제품 3종 교차 매칭 매트릭스 (Multi-Product Triage) ─────────────────────────
FIT_KEYWORD_MAP: Dict[str, List[str]] = {
    "속건조": ["속건조", "건조", "당김", "푸석", "히알루론산", "보습"],
    "수분 보충": ["수분", "히알루론산", "보습", "쫀광", "물광", "촉촉"],
    "토너 팩": ["토너", "물토너", "토너팩", "화장솜", "성분표", "ppm"],
    "기초 레이어링": ["기초", "루틴", "레이어링", "화잘먹", "세럼", "스킨케어"],
    "트러블 진정": ["트러블", "진정", "여드름", "예민", "뒤집어", "붉은", "홍조"],
    "자극 후 진정": ["자극", "진정", "민감", "패드", "진정팩", "토너패드"],
    "열감/쿨링": ["열감", "쿨링", "시원", "진정", "홍조"],
    "메이크업 전 진정 루틴": ["메이크업전", "화잘먹", "패드", "진정", "5분팩"],
    "속당김": ["속당김", "속건조", "당김", "건조", "수분", "히알루론산"],
    "메이크업 전 수분 루틴": ["메이크업전", "화잘먹", "수분", "촉촉", "마스크"],
    "1일 1팩": ["1일1팩", "마스크", "시트팩", "팩"],
    "시트팩 루틴": ["시트", "마스크", "마스크팩", "시트팩", "팩"],
}

PRODUCT_FORM_BONUS: Dict[str, List[str]] = {
    "올리고 히알루론산 딥 토너": ["토너", "물토너", "토너팩", "성분표", "ppm", "히알루론산"],
    "그린 플라보노이드 2.5 패드": ["패드", "토너패드", "진정패드", "트러블", "진정", "쿨링", "열감"],
    "올리고 히알루론산 워터리 스킨 마스크": ["마스크", "시트팩", "마스크팩", "1일1팩", "시트"],
}


def _deterministic_judgements_for_product(
    facts: List[Dict[str, Any]],
    product_name: str,
    product: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """오프라인/저비용 교차 매칭용 결정론적 스코어링 (apply_judgement_rules와 100% 동일 가드레일 적용)."""
    fit_territory = product.get("fit_territory", [])
    claims = product.get("verified_claims", [])
    form_kws = PRODUCT_FORM_BONUS.get(product_name, [])
    raw_js: List[Judgement] = []

    for f in facts:
        vid = f["video_id"]
        if not f.get("evidence_ok"):
            continue
        blob = _norm(
            f"{f.get('what_happens', '')} {' '.join(f.get('product_types', []))} "
            f"{f.get('hook_quote', '')} {f.get('evidence_quote', '')}"
        )
        if f.get("domain") != DOMAIN_BASE:
            raw_js.append(Judgement(
                video_id=vid, decision="Drop", score=1,
                reason=f"영상 영역({f.get('domain')}) 불일치로 제외", linked_claim="",
            ))
            continue

        # '토너패드'가 물토너로 오인되지 않도록 패드 복합어를 분리한 텍스트로 물토너 키워드 검사
        blob_check = blob.replace("토너패드", "패드") if product_name == "올리고 히알루론산 딥 토너" else blob

        matched_terrs: List[str] = []
        matched_kws = set()
        for terr in fit_territory:
            t_hit = False
            if _norm(terr) and _norm(terr) in blob_check:
                t_hit = True
                matched_kws.add(terr)
            for key, kws in FIT_KEYWORD_MAP.items():
                if key in terr:
                    for kw in kws:
                        if _norm(kw) in blob_check:
                            t_hit = True
                            matched_kws.add(kw)
            if t_hit:
                matched_terrs.append(terr)

        form_hits = [kw for kw in form_kws if _norm(kw) in blob_check]
        total_signal = len(matched_kws) + len(form_hits)

        if len(form_hits) >= 2 or (len(form_hits) >= 1 and len(matched_terrs) >= 2) or total_signal >= 4:
            score = 5
            reason = f"적합 영역({', '.join(matched_terrs[:2]) or product_name}) 및 핵심 키워드({', '.join(list(matched_kws)[:3])})와 강하게 일치"
            lc = claims[0] if claims else ""
        elif len(matched_terrs) >= 1 and total_signal >= 2:
            score = 4
            reason = f"적합 영역({', '.join(matched_terrs[:2])})과 직접 연결 가능"
            lc = claims[0] if claims else ""
        elif len(matched_terrs) >= 1 or len(form_hits) >= 1:
            score = 3
            reason = f"일부 키워드({', '.join(list(matched_kws | set(form_hits))[:2])})만 연결되어 서브 테스트(Pivot) 수준"
            lc = claims[0] if claims else ""
        else:
            score = 2
            reason = f"'{product_name}' 적합 영역과 직접적 연결 근거 부족"
            lc = ""

        # QA #1: 시트/마스크 제형 제품(워터리 스킨 마스크)은 제형 키워드(마스크/시트팩/1일1팩 등)가 전혀 없으면 최대 Pivot(3점)으로 캡핑
        if "마스크" in product_name and len(form_hits) == 0 and score >= 4:
            score = 3
            reason = f"시트/마스크 제형 언급 없어 일반 수분 키워드만으로 Go 불가 → Pivot(3점) 제한. " + reason

        # 가장 잘 맞는 verified_claim 선택
        if score >= 4 and claims:
            best_c = claims[0]
            best_overlap = -1
            for c in claims:
                nc = _norm(c)
                ov = sum(1 for kw in (matched_kws | set(form_hits)) if _norm(kw) in nc)
                if ov > best_overlap:
                    best_overlap = ov
                    best_c = c
            lc = best_c

        raw_js.append(Judgement(
            video_id=vid, decision=_decision_from_score(score), score=score,
            reason=reason, linked_claim=lc,
        ))

    return apply_judgement_rules(raw_js, facts, product)


def build_multi_product_matrix(
    videos: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    products: Optional[Dict[str, Any]] = None,
    primary_product: Optional[str] = None,
    primary_judgements: Optional[List[Dict[str, Any]]] = None,
    llm=None,
) -> Dict[str, Any]:
    """한 번의 클리핑(추가 YouTube 쿼터 0)으로 products.json 전체 제품 교차 매칭 매트릭스를 생성합니다."""
    products = products or load_products()
    prod_names = list(products.keys())
    v_by_id = {v["video_id"]: _ensure_video_metrics(v) for v in videos}

    per_product: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for pname in prod_names:
        if pname == primary_product and primary_judgements is not None:
            js = primary_judgements
        elif llm is not None:
            js = judge_fit(llm, facts, pname, products)
        else:
            js = _deterministic_judgements_for_product(facts, pname, products[pname])
        per_product[pname] = {j["video_id"]: j for j in js}

    def _count_form_hits(fact: Dict[str, Any], pname: str) -> int:
        blob = _norm(
            f"{fact.get('what_happens', '')} {' '.join(fact.get('product_types', []))} "
            f"{fact.get('hook_quote', '')} {fact.get('evidence_quote', '')}"
        )
        blob_check = blob.replace("토너패드", "패드") if pname == "올리고 히알루론산 딥 토너" else blob
        return sum(1 for kw in PRODUCT_FORM_BONUS.get(pname, []) if _norm(kw) in blob_check)

    rows: List[Dict[str, Any]] = []
    for f in facts:
        vid = f["video_id"]
        v = v_by_id.get(vid, {})
        cells: Dict[str, Dict[str, Any]] = {}
        best_product: Optional[str] = None
        best_rank = (-1, -1)  # (score, form_hits)
        best_score = 0
        for pname in prod_names:
            j = per_product[pname].get(vid, {"decision": "Drop", "score": 1, "reason": "판정 없음"})
            f_hits = _count_form_hits(f, pname)
            cells[pname] = {
                "decision": j["decision"],
                "score": int(j["score"]),
                "reason": j["reason"],
                "form_hits": f_hits,
            }
            if j["decision"] == "Go":
                sc = int(j["score"])
                rank_tuple = (sc, f_hits)
                if rank_tuple > best_rank:
                    best_rank = rank_tuple
                    best_score = sc
                    best_product = pname
        rows.append({
            "video_id": vid,
            "title": v.get("title", vid),
            "views": int(v.get("views", 0)),
            "views_per_day": int(v.get("views_per_day", 0)),
            "text_source": f.get("text_source", v.get("text_source", "meta")),
            "domain": f.get("domain", "기타/뷰티무관"),
            "cells": cells,
            "best_product": best_product,
            "best_score": best_score,
        })

    product_summary: Dict[str, Dict[str, int]] = {}
    for pname in prod_names:
        js_vals = list(per_product[pname].values())
        go_js = [j for j in js_vals if j["decision"] == "Go"]
        product_summary[pname] = {
            "go": len(go_js),
            "pivot": sum(1 for j in js_vals if j["decision"] == "Pivot"),
            "drop": sum(1 for j in js_vals if j["decision"] == "Drop"),
            "total_go_score": sum(int(j["score"]) for j in go_js),
            "total_go_views_per_day": sum(int(v_by_id.get(j["video_id"], {}).get("views_per_day", 0)) for j in go_js),
        }

    ranked = sorted(
        prod_names,
        key=lambda pn: (
            product_summary[pn]["go"],
            product_summary[pn]["total_go_score"],
            product_summary[pn]["total_go_views_per_day"],
        ),
        reverse=True,
    )
    top_p = ranked[0] if ranked else None
    if top_p and product_summary[top_p]["go"] > 0:
        s = product_summary[top_p]
        recommended_product = top_p
        recommendation_reason = f"{top_p} (Go {s['go']}건·합계 {s['total_go_score']}점 · Pivot {s['pivot']}건 · Drop {s['drop']}건)"
    else:
        recommended_product = None
        recommendation_reason = "오늘은 억지 집행 금지 — 전원 보류/테스트 권장 (전 제품 Go 0건)"

    return {
        "products": prod_names,
        "rows": rows,
        "product_summary": product_summary,
        "recommended_product": recommended_product,
        "recommendation_reason": recommendation_reason,
    }


# ───────────────────────── Step 3. 브리프 (Go만) ─────────────────────────
NUM_TOKEN = re.compile(r"\d[\d,\.]*\s*(?:%|ppm|mm|ml|배속|배|스킨|겹|중|위|등|시간|초|분|일|만\s*개?|억|개)")
# 촬영/편집 연출 타임코드 화이트리스트 (효능 과장 '3초 만에', '1초 컷' 등은 제외)
DIRECTION_TIME_RE = re.compile(
    r"(?:첫|초반)\s*\d+\s*초(?!\s*만에)"
    r"|\b\d+\s*초\s*(?:훅|이내|후|오프닝|클립|분량|연출|촬영)"
    r"|\b(?:[3-9]|\d{2,})\s*초\s*컷"
)
COSMETIC_LAW_BANNED_TERMS = [
    "1위", "1등", "최고", "즉각", "완벽", "100%", "기적",
    "치료", "재생", "염증 완화", "염증완화", "피부과 치료",
    "완벽 차단", "붉은기 즉각", "즉각 진정", "즉각 완화",
    "여드름 완치", "완치", "아토피", "피부염", "피부과 시술", "시술",
    "모공 축소", "주름 개선", "미백 효과", "미백",
    "품절 대란", "베스트셀러", "랭킹",
]
# 의약품 오인 핵심 금지어: verified_claims 포함 여부와 무관하게 무조건 위반 적발 (우회 원천 차단)
ABSOLUTE_MEDICAL_BANNED_TERMS = [
    "완치", "여드름 완치", "아토피", "피부염", "치료", "피부과 치료",
    "염증 완화", "염증완화", "피부과 시술", "기적",
]


def _token_in_claims(tok: str, claims_text: str) -> bool:
    """수치 토큰이 확인된 제품 문구(범위 표기 양끝 포함)에 존재하는지 검사합니다."""
    norm_tok = _norm(tok)
    norm_claims = _norm(claims_text)
    if norm_tok in norm_claims:
        return True
    # 범위 표기 지원 (예: claims에 '15~20분'이 있을 때 '15분'과 '20분' 모두 허용)
    m = re.match(r"(\d[\d,\.]*)\s*(분|시간|ml|ppm|%)", tok.strip())
    if m:
        num, unit = m.group(1), m.group(2)
        if re.search(rf"{re.escape(num)}\s*~\s*\d[\d,\.]*\s*{re.escape(unit)}", claims_text):
            return True
        if re.search(rf"\d[\d,\.]*\s*~\s*{re.escape(num)}\s*{re.escape(unit)}", claims_text):
            return True
    return False


def _brief_violations(b: Storyboard, product: Dict[str, Any]) -> List[str]:
    # 시청자 노출 스크립트 4개 필드 + 마케팅 카피 3종(copy_ideas) 검사 (creator_note는 금지 안내 문맥이므로 제외)
    text = " ".join([b.hook, b.before, b.product_moment, b.cta, *(b.copy_ideas or [])])
    norm_text = _norm(text)
    claims = " ".join(product["verified_claims"])
    norm_claims = _norm(claims)
    v: List[str] = []

    for bad in product.get("unverified_removed_from_v1", []):
        if _norm(bad) and _norm(bad) in norm_text:
            v.append(f"확인되지 않은 문구 사용: {bad}")

    for med in ABSOLUTE_MEDICAL_BANNED_TERMS:
        nm = _norm(med)
        if nm and nm in norm_text:
            v.append(f"의약품 오인 절대 금지 표현: {med}")

    for term in COSMETIC_LAW_BANNED_TERMS:
        nt = _norm(term)
        if nt and nt in norm_text and nt not in norm_claims:
            v.append(f"화장품법 과대광고/금지 표현 의심: {term}")

    # 연출 타임코드('첫 3초', '3초 훅', '5초 컷', '10초 이내' 등)를 제외한 텍스트에서만 효능 수치 검사
    num_scan_text = DIRECTION_TIME_RE.sub(" ", text)
    for tok in NUM_TOKEN.findall(num_scan_text):
        if not _token_in_claims(tok, claims):
            v.append(f"출처 없는 수치 표현: {tok.strip()}")

    return list(dict.fromkeys(v))


def write_briefs(llm, go_items: List[Dict[str, Any]], facts: Dict[str, Dict[str, Any]],
                 product_name: str, products: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not go_items:
        return []
    p = products[product_name]
    go_ids = {g["video_id"] for g in go_items}
    lines = "\n".join(
        f"- [video_id={g['video_id']}] 포맷={facts[g['video_id']].get('format_tag', '기타')} | "
        f"트렌드={facts[g['video_id']]['what_happens']} | 훅원문={facts[g['video_id']]['hook_quote'] or '-'} | "
        f"근거원문={facts[g['video_id']].get('evidence_quote') or '-'} | 연결문구={g['linked_claim']}"
        for g in go_items if g["video_id"] in facts
    )

    def build(feedback: str = "") -> str:
        return (
            f"'{product_name}' 인하우스 마케터가 인플루언서에게 그대로 전달할 숏폼 브리프를 작성하세요.\n"
            f"[사용 가능한 제품 문구 — 이 범위 밖의 효능·수치·순위·시간·배수·임상 표현 금지]\n"
            + "\n".join(f"- {c}" for c in p["verified_claims"]) + "\n"
            f"[금지 문구] {', '.join(p.get('unverified_removed_from_v1', []))}\n"
            "규칙:\n"
            "- 각 트렌드의 바이럴 포맷 구조를 살려 구체적인 화면 구도·소품·자막/대사를 작성하세요(추상적 문구 금지).\n"
            "- copy_ideas에는 썸네일/자막에 바로 쓸 수 있는 짧은 마케팅 카피 3종을 작성하세요.\n"
            "- hook/before/product_moment/cta/copy_ideas에는 '1위/1등/3초 만에/24시간/10배/즉각/완벽/치료/재생/완치/아토피' 같은 과대광고 표현을 절대 쓰지 마세요.\n"
            "- creator_note에는 인플루언서가 피해야 할 금지 표현 주의사항을 명확히 적으세요.\n"
            + (f"[이전 시도 위반 — 반드시 수정]\n{feedback}\n" if feedback else "")
            + "\n[Go 판정 트렌드]\n" + lines
        )

    briefs = _invoke(llm, BriefSheet, build()).briefs
    out = []
    pending = {b.video_id: b for b in briefs if b.video_id in go_ids}
    viol = {vid: _brief_violations(b, p) for vid, b in pending.items()}
    if any(viol.values()):
        fb = "\n".join(f"- {vid}: {', '.join(vs)}" for vid, vs in viol.items() if vs)
        retry = {b.video_id: b for b in _invoke(llm, BriefSheet, build(fb)).briefs if b.video_id in go_ids}
        for vid in list(pending):
            if viol[vid] and vid in retry:
                pending[vid] = retry[vid]
                viol[vid] = _brief_violations(retry[vid], p)
    for vid, b in pending.items():
        if vid not in go_ids:
            continue
        out.append({**b.model_dump(), "violations": viol.get(vid, []), "needs_review": bool(viol.get(vid))})
    return out


# ───────────────────────── Step 3-2. 즉시 복사 가능한 2종 마크다운 ─────────────────────────
_INTERNAL_SOURCE_PAREN_RE = re.compile(
    r"\s*\([^)]*(?:요약|blancdoux|kurly|glowpick|costco|hwahae|gsshop|koreadepart|미확인)[^)]*\)",
    re.IGNORECASE,
)
_INTERNAL_BANNED_PAREN_RE = re.compile(
    r"\s*\([^)]*(?:정정|단정|미확인|요약)[^)]*\)",
    re.IGNORECASE,
)


def _clean_claim_for_creator(claim: str) -> str:
    """대외 발송용 크리에이터 가이드에서 미확인 임상 문구와 내부 출처 괄호 주석·제3자 어투를 제거합니다."""
    if not claim or "시험 조건은 미확인" in claim:
        return ""
    c = _INTERNAL_SOURCE_PAREN_RE.sub("", claim).strip()
    c = re.sub(r"케어를\s*내세움$", "케어", c)
    c = re.sub(r"를\s*내세움$", "", c)
    c = re.sub(r"(?:으)?로\s*소개$", "", c)
    return c.strip()


def _clean_banned_for_creator(item: str) -> str:
    """금지 표현 목록에서 내부 수정 이력 괄호((대나무 유래로 정정), (단정 표현) 등)를 제거합니다."""
    return _INTERNAL_BANNED_PAREN_RE.sub("", item or "").strip()


def format_copyable_outputs(result: Dict[str, Any]) -> Dict[str, str]:
    """팀장/슬랙 보고용 1페이지 요약 + 인플루언서/대행사 전달용 촬영 가이드 생성."""
    product_name = result.get("product", "")
    videos = [_ensure_video_metrics(v) for v in result.get("videos", [])]
    facts = result.get("facts", [])
    judgements = result.get("judgements", [])
    briefs = result.get("briefs", [])
    stats = result.get("stats", {})
    market_patterns = result.get("market_patterns", [])
    report_date = result.get("report_date") or date.today().isoformat()
    days_range = result.get("days_range")
    period_label = f"최근 {days_range}일" if days_range else "최근 수집 배치"

    v_by_id = {v["video_id"]: v for v in videos}
    f_by_id = {f["video_id"]: f for f in facts}
    b_by_id = {b["video_id"]: b for b in briefs}

    products = load_products()
    prod_info = products.get(product_name, {})
    banned_list = [
        cleaned for cleaned in (_clean_banned_for_creator(x) for x in prod_info.get("unverified_removed_from_v1", []))
        if cleaned
    ]
    verified_claims = prod_info.get("verified_claims", [])
    confidence = result.get("product_confidence") or prod_info.get("confidence", "unknown")

    total_v = stats.get("videos", len(videos))
    caption_v = stats.get("transcript_caption", sum(1 for v in videos if v.get("text_source") == "caption"))
    caption_pct = round(caption_v / max(1, total_v) * 100, 1)

    go_items = sorted(
        [j for j in judgements if j["decision"] == "Go"],
        key=lambda j: (-j["score"], -v_by_id.get(j["video_id"], {}).get("views_per_day", 0)),
    )
    pivot_items = [j for j in judgements if j["decision"] == "Pivot"]
    drop_items = [j for j in judgements if j["decision"] == "Drop"]

    conf_banner = (
        f"> ⚠️ **[제품 정보 확인 필요]** 현재 제품 문구는 요약 기반(신뢰도: {confidence})입니다. "
        "최종 광고·시딩 집행 전 공식 상세페이지 원문 및 임상 시험 조건을 반드시 확인하세요."
        if confidence != "high"
        else ""
    )

    # 1) 팀장/슬랙 보고용 1페이지 요약 (internal_report_md)
    has_prev = stats.get("has_prev_snapshot", any(v.get("has_prev_snapshot") for v in videos))
    new_cnt = stats.get("new_videos_count", sum(1 for v in videos if v.get("is_new")))
    delta_summary = f" | 신규 🆕 {new_cnt}건" if has_prev else ""

    rep: List[str] = [
        f"# [주간 K-뷰티 쇼츠 트렌드 보고] {product_name}",
        f"- **보고 기준일**: {report_date} | **수집 기간**: {period_label}{delta_summary}",
        f"- **수집 현황**: 총 {total_v}건 (자막 확보 {caption_v}건 / {caption_pct}%) | "
        f"**판정 합계 ({len(go_items) + len(pivot_items) + len(drop_items)}건)**: "
        f"Go {len(go_items)}건 · Pivot {len(pivot_items)}건 · Drop {len(drop_items)}건",
    ]
    if conf_banner:
        rep.extend(["", conf_banner])
    rep.extend(["", "## 1. 이번 주 시장 바이럴 패턴"])
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
            vpd = v.get("views_per_day", 0)
            like_rate = v.get("like_rate", 0.0)
            pub_date = (v.get("published_at") or "-")[:10]
            quote = f.get("hook_quote") or f.get("evidence_quote") or "-"
            is_caption = f.get("text_source") == "caption"
            src_tag = "자막 확보(caption)" if is_caption else "⚠️ 자막 미확인(meta — 직접 시청 필수)"
            new_tag = " 🆕 NEW" if v.get("is_new") else ""
            v_delta = v.get("views_delta")
            delta_tag = f" (+{v_delta:,}회 ↑)" if isinstance(v_delta, int) and v_delta > 0 else ""

            rep.append(f"### Go #{idx}.{new_tag} {v.get('title', vid)} (`{vid}`)")
            if b and b.get("needs_review"):
                rep.append(f"> 🚨 **[발송 보류 — 검수 필요]**: {'; '.join(b.get('violations', []))}")
            rep.extend([
                f"- **레퍼런스**: https://youtube.com/shorts/{vid} | 채널: {v.get('channel_title', '-')} | 업로드일: {pub_date}",
                f"- **지표**: 조회수 {views:,}회{delta_tag} | 일평균 {vpd:,}회/일 | 좋아요율 {like_rate:.2f}% | 포맷: `{f.get('format_tag', '기타')}`",
                f"- **Go 근거 ({j['score']}점)**: {j['reason']}",
                f"- **연결 제품 문구**: {j.get('linked_claim') or '-'}",
                f"- **원문 인용 ({src_tag})**: \"{quote}\"",
            ])
            if b:
                rep.append(f"- **핵심 훅/제품 침투**: {b['hook']} → {b['product_moment']}")
                if b.get("copy_ideas"):
                    rep.append(f"- **추천 카피 3종**: " + " / ".join(f"\"{c}\"" for c in b["copy_ideas"][:3]))
            rep.append("")
    else:
        rep.append("- 이번 수집 배치에서 Go 판정 컨셉이 없습니다.")
        rep.append("")

    if pivot_items:
        rep.append(f"## 3. Pivot 검토 컨셉 ({len(pivot_items)}건 — 서브 테스트/직접 시청 검토)")
        for j in pivot_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            pub_date = (v.get("published_at") or "-")[:10]
            src_note = "자막 확보" if f.get("text_source") == "caption" else "⚠️ 자막 미확인(직접 시청 필요)"
            rep.append(
                f"- **{v.get('title', vid)[:45]}** (https://youtube.com/shorts/{vid} | {pub_date} | "
                f"{v.get('views', 0):,}회 · 일평균 {v.get('views_per_day', 0):,}회 | `{f.get('format_tag', '기타')}` | {src_note}): {j['reason']}"
            )
        rep.append("")

    rep.append(f"## 4. Drop 제외 요약 ({len(drop_items)}건)")
    if drop_items:
        for j in drop_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            rep.append(
                f"- [{f.get('domain', '-')}] {v.get('title', vid)[:45]} (`{vid}`, {v.get('views', 0):,}회): {j['reason']}"
            )
    else:
        rep.append("- Drop 제외 항목 없음")

    matrix = result.get("multi_product_matrix")
    if matrix and matrix.get("product_summary"):
        rep.extend(["", "### 🔀 제품 3종 교차 매칭 요약"])
        for pname in matrix.get("products", []):
            ps = matrix["product_summary"].get(pname, {})
            rep.append(
                f"- **{pname}**: Go {ps.get('go', 0)}건(합계 {ps.get('total_go_score', 0)}점) · "
                f"Pivot {ps.get('pivot', 0)}건 · Drop {ps.get('drop', 0)}건"
            )
        rec_p = matrix.get("recommended_product")
        rec_reason = matrix.get("recommendation_reason", "")
        if rec_p:
            rep.append(f"- **🏆 오늘의 추천 주력 제품**: {rec_reason}")
        else:
            rep.append(f"- **⚠️ 오늘의 추천 주력 제품**: {rec_reason}")

    internal_report_md = "\n".join(rep).strip()

    # 2) 인플루언서/대행사 전달용 촬영 가이드 (2단 분리: 마케터 내부 확인 블록 + 순수 DM 본문)
    internal_notes: List[str] = ["<!-- 마케터 내부 확인용 (발송 시 제외) -->"]
    if confidence != "high":
        internal_notes.append(
            f"- ⚠️ **[제품 정보 확인 필요]** 현재 제품 문구는 요약 기반(신뢰도: {confidence})입니다. "
            "최종 광고·시딩 집행 전 공식 상세페이지 원문 및 임상 시험 조건을 반드시 확인하세요."
        )
    flagged_briefs = [b for b in briefs if b.get("needs_review")]
    if flagged_briefs:
        for b in flagged_briefs:
            internal_notes.append(
                f"- 🚨 **[발송 보류 — 검수 필요 (`{b['video_id']}`)]**: {'; '.join(b.get('violations', []))}"
            )
    else:
        internal_notes.append("- ✅ **브리프 자동 검수**: 위반 사항 없음")
    for idx, b in enumerate(briefs, 1):
        vid = b["video_id"]
        f = f_by_id.get(vid, {})
        src_note = "자막 확인 완료(caption)" if f.get("text_source") == "caption" else "⚠️ 자막 미확인(meta — 발송 전 영상 직접 시청 필수)"
        internal_notes.append(f"- **컨셉 #{idx} (`{vid}`) 출처 상태**: {src_note}")

    clean_guide: List[str] = [
        f"# [크리에이터 촬영 가이드] {product_name}",
        f"- **배포 기준일**: {report_date} | **권장 규격**: 세로형 9:16 숏폼 (20~45초) | **필수 표기**: `#광고` 또는 `#협찬`",
        "> 아래 가이드는 최근 실제 바이럴 쇼츠 포맷과 공식 확인된 제품 정보만을 기반으로 작성되었습니다.",
        "",
    ]

    if briefs:
        for idx, b in enumerate(briefs, 1):
            vid = b["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            pub_date = (v.get("published_at") or "-")[:10]
            clean_guide.extend([
                f"## 컨셉 #{idx}. [{f.get('format_tag', '기타')}] {v.get('title', vid)}",
                f"- **참고 레퍼런스**: https://youtube.com/shorts/{vid} (업로드 {pub_date} | 조회수 {v.get('views', 0):,}회 · 일평균 {v.get('views_per_day', 0):,}회)",
                f"- **첫 3초 훅**: {b['hook']}",
                f"- **비포 상황**: {b['before']}",
                f"- **제품 침투 시점**: {b['product_moment']}",
                f"- **CTA**: {b['cta']}",
                f"- **촬영 주의사항**: {b['creator_note']}",
            ])
            if b.get("copy_ideas"):
                clean_guide.append(f"- **추천 카피 3종**: " + " / ".join(f"\"{c}\"" for c in b["copy_ideas"][:3]))
            if banned_list:
                clean_guide.append(f"- **절대 사용 금지 문구 (과대광고/미확인 표현 방지)**: {', '.join(banned_list)}")
            clean_guide.append("")
    else:
        clean_guide.append("- 이번 수집 배치에서 Go 판정 컨셉이 없어 촬영 가이드가 생성되지 않았습니다.")
        if banned_list:
            clean_guide.append(f"- **참고 금지 표현**: {', '.join(banned_list)}")

    if verified_claims:
        clean_guide.append("### [참고] 공식 확인된 제품 소구 포인트")
        for c in verified_claims:
            cleaned = _clean_claim_for_creator(c)
            if cleaned:
                clean_guide.append(f"- {cleaned}")

    creator_dm_clean_md = "\n".join(clean_guide).strip()
    creator_guide_md = (
        "\n".join(internal_notes).strip()
        + "\n\n--- [아래부터 복사해서 인플루언서에게 전달] ---\n\n"
        + creator_dm_clean_md
    )
    return {
        "internal_report_md": internal_report_md,
        "creator_guide_md": creator_guide_md,
        "creator_dm_clean_md": creator_dm_clean_md,
    }


# ───────────────────────── Step 3-3. 팀장/임원 결재용 1페이지 독립 HTML 보고서 (B2B-12) ─────────────────────────
def export_shareable_html_report(result: Dict[str, Any]) -> str:
    """API 키·서버 없이 브라우저에서 바로 열고 PDF 인쇄/이메일 첨부 가능한 1페이지 독립 HTML5 보고서를 생성합니다."""
    def _e(val: Any) -> str:
        return _html.escape(str(val if val is not None else ""), quote=True)

    product_name = result.get("product", "")
    report_date = result.get("report_date") or date.today().isoformat()
    days_range = result.get("days_range")
    period_label = f"최근 {days_range}일" if days_range else "최근 수집 배치"
    videos = [_ensure_video_metrics(v) for v in result.get("videos", [])]
    facts = result.get("facts", [])
    judgements = result.get("judgements", [])
    briefs = result.get("briefs", [])
    market_patterns = result.get("market_patterns", [])
    products = load_products()
    prod_info = products.get(product_name, {})
    confidence = result.get("product_confidence") or prod_info.get("confidence", "unknown")
    banned_list = [
        x for x in (_clean_banned_for_creator(b) for b in prod_info.get("unverified_removed_from_v1", [])) if x
    ]
    banned_str = ", ".join(banned_list)

    v_by_id = {v["video_id"]: v for v in videos}
    f_by_id = {f["video_id"]: f for f in facts}
    b_by_id = {b["video_id"]: b for b in briefs}

    total_v = len(videos)
    cap_v = sum(1 for v in videos if v.get("text_source") == "caption")
    cap_pct = round(cap_v / max(1, total_v) * 100, 1)
    avg_views = int(round(sum(v.get("views", 0) for v in videos) / max(1, total_v)))
    avg_lr = round(sum(v.get("like_rate", 0.0) for v in videos) / max(1, total_v), 2)
    max_vpd = max((v.get("views_per_day", 0) for v in videos), default=0)

    go_items = sorted(
        [j for j in judgements if j["decision"] == "Go"],
        key=lambda j: (-j["score"], -v_by_id.get(j["video_id"], {}).get("views_per_day", 0)),
    )
    pivot_items = [j for j in judgements if j["decision"] == "Pivot"]
    drop_items = [j for j in judgements if j["decision"] == "Drop"]

    banners: List[str] = []
    if confidence != "high":
        banners.append(
            f'<div class="banner warn">⚠️ <b>[제품 정보 확인 필요]</b> 현재 제품 문구는 요약 기반(신뢰도: {_e(confidence)})입니다. '
            "최종 광고·시딩 집행 전 공식 상세페이지 원문 및 임상 시험 조건을 반드시 확인하세요.</div>"
        )
    if any(v.get("low_views_fallback") for v in videos):
        banners.append(
            '<div class="banner info">ℹ️ <b>저유입 기준 완화 포함:</b> 최소 조회수 기준을 넘는 영상이 부족해 일부 저유입 영상이 포함되었습니다.</div>'
        )

    pat_html = "".join(
        f'<div class="pat-row"><span class="pat-num">{i}</span><div>{_e(p)}</div></div>'
        for i, p in enumerate(market_patterns, 1)
    ) or '<div class="pat-row">추출된 공통 시장 패턴이 없습니다.</div>'

    matrix = result.get("multi_product_matrix")
    mat_banner = ""
    if matrix:
        rec_p = matrix.get("recommended_product")
        rec_reason = matrix.get("recommendation_reason", "")
        if rec_p:
            mat_banner = f'<div class="banner go">🏆 <b>3종 교차 매칭 추천 주력 제품:</b> {_e(rec_reason)}</div>'
        else:
            mat_banner = f'<div class="banner warn">⚠️ <b>3종 교차 매칭 결과:</b> {_e(rec_reason)}</div>'

    def _dots(score: int, decision: str) -> str:
        s = max(1, min(5, int(score)))
        col = "#BF8A12" if (decision == "Go" and s == 5) else ("#0F766E" if decision == "Go" else ("#B45309" if decision == "Pivot" else "#4B5563"))
        return f'<span class="dots" style="color:{col};">{"●"*s}{"○"*(5-s)} {s}점</span>'

    go_cards: List[str] = []
    if not go_items:
        go_cards.append('<div class="empty">이번 수집 배치에서는 억지 연결 없이 바로 집행할 Go 컨셉이 없습니다.</div>')
    else:
        for idx, j in enumerate(go_items):
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            b = b_by_id.get(vid)
            is_top = idx == 0
            thumb = v.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            cap_badge = (
                '<span class="pill go">✅ 자막 검증 완료</span>'
                if f.get("text_source") == "caption"
                else '<span class="pill warn">⚠️ 자막 미확인 (직접 시청 필요)</span>'
            )
            rev_html = ""
            if b and b.get("needs_review"):
                rev_html = f'<div class="banner danger">🚨 <b>발송 보류 — 검수 필요:</b> {_e("; ".join(b.get("violations", [])))}</div>'
            clean_lc = _clean_claim_for_creator(j.get("linked_claim") or "") or (j.get("linked_claim") or "-")
            quote = f.get("hook_quote") or f.get("evidence_quote") or "-"
            new_b = ' <span class="pill go">🆕 NEW</span>' if v.get("is_new") else ""
            d_val = v.get("views_delta")
            delta_b = f' <span class="pill go">+{int(d_val):,}회 ↑</span>' if isinstance(d_val, int) and d_val > 0 else ""

            sb_html = ""
            if b:
                copies = b.get("copy_ideas") or []
                copy_html = (
                    '<div class="quote" style="background:#F6F2FF;border-left-color:#6C2BD9;">'
                    '<div class="quote-lbl" style="color:#4C1D95;">✍️ 바로 쓸 마케팅 카피 3종</div>'
                    + "".join(f'<div class="quote-txt">• {_e(c)}</div>' for c in copies[:3])
                    + "</div>"
                    if copies
                    else ""
                )
                sb_html = f"""
                {copy_html}
                <div class="sb-grid">
                  <div class="sb-cell"><div class="sb-lbl">⚡ 1. 첫 3초 훅</div><div>{_e(b['hook'])}</div></div>
                  <div class="sb-cell"><div class="sb-lbl">👀 2. 비포 공감 상황</div><div>{_e(b['before'])}</div></div>
                  <div class="sb-cell"><div class="sb-lbl">💧 3. 제품 침투 시점</div><div>{_e(b['product_moment'])}</div></div>
                  <div class="sb-cell"><div class="sb-lbl">🛒 4. 구매/참여 CTA</div><div>{_e(b['cta'])}</div></div>
                </div>
                <div class="note-strip">
                  <b>📝 크리에이터 주의사항:</b> {_e(b['creator_note'])}
                  {f'<br><b>🚫 절대 금지 표현:</b> {_e(banned_str)}' if banned_str else ''}
                </div>
                """

            go_cards.append(f"""
            <div class="card {'gold' if is_top else ''}">
              <div class="card-top">
                <div class="badges">
                  {'<span class="pill gold-p">👑 TOP GO PICK</span>' if is_top else ''}
                  <span class="pill go">🎯 Go</span>
                  <span class="pill purple">{_e(f.get('format_tag', '기타'))}</span>
                  {cap_badge}
                </div>
                {_dots(j['score'], 'Go')}
              </div>
              {rev_html}
              <div class="card-title">{_e(f.get('what_happens') or v.get('title', vid))}</div>
              <div class="reason"><b>📌 Go 근거:</b> {_e(j['reason'])}</div>
              <div class="claim">🔗 {_e(clean_lc)}</div>
              <div class="quote">
                <div class="quote-lbl">💬 실제 영상 원문 인용 ({'자막 확보' if f.get('text_source')=='caption' else '제목/설명'})</div>
                <div class="quote-txt">"{_e(quote)}"</div>
              </div>
              <div class="evid">
                <img src="{_e(thumb)}" alt="thumb" class="thumb"/>
                <div class="evid-body">
                  <div class="evid-title">{_e(v.get('title', vid))}</div>
                  <div class="evid-meta">
                    📺 {_e(v.get('channel_title', '-'))} · 👀 {v.get('views', 0):,}회{new_b}{delta_b} ·
                    <span class="pill hot">🔥 {v.get('views_per_day', 0):,}회/일</span> ·
                    ❤️ {v.get('like_rate', 0.0):.2f}% · 📅 {_e((v.get('published_at') or '-')[:10])}
                  </div>
                </div>
                <a class="evid-btn" href="https://youtube.com/shorts/{_e(vid)}" target="_blank" rel="noopener">쇼츠 보기 ↗</a>
              </div>
              {sb_html}
            </div>
            """)

    triage_rows: List[str] = []
    for j in pivot_items + drop_items:
        vid = j["video_id"]
        v = v_by_id.get(vid, {})
        f = f_by_id.get(vid, {})
        dec = j["decision"]
        cls = "warn" if dec == "Pivot" else "drop"
        triage_rows.append(
            f"<tr>"
            f"<td><span class='pill {cls}'>{_e(dec)} {int(j['score'])}점</span></td>"
            f"<td><span class='pill drop'>{_e(f.get('domain', '-'))}</span></td>"
            f"<td><a href='https://youtube.com/shorts/{_e(vid)}' target='_blank' rel='noopener'>{_e(v.get('title', vid)[:50])} ↗</a></td>"
            f"<td class='tnum'>{v.get('views', 0):,}회</td>"
            f"<td>{_e(j['reason'])}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>[결재 보고서] {_e(product_name)} — K-Beauty TrendSetter Pro ({_e(report_date)})</title>
<style>
  :root {{
    --purple:#6C2BD9; --purple-dark:#4C1D95; --purple-soft:#F3EEFD;
    --gold:#BF8A12; --gold-soft:#FFFDF5; --ink:#1C1730; --ink2:#374151;
    --muted:#6B7280; --bg:#FAF9FE; --surface:#FFFFFF; --line:#ECE9F5;
    --go:#0F766E; --go-soft:#E6F6F4; --warn:#B45309; --warn-soft:#FEF3C7;
    --drop:#4B5563; --drop-soft:#F3F4F6; --danger:#B91C1C; --danger-soft:#FEF2F2;
    --hot:#C2410C; --hot-soft:#FFF7ED;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Pretendard","Malgun Gothic",sans-serif; line-height:1.5; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:24px 20px 48px; }}
  .tnum {{ font-variant-numeric:tabular-nums; }}
  .header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid var(--purple); padding-bottom:12px; margin-bottom:14px; flex-wrap:wrap; gap:8px; }}
  .header h1 {{ margin:0; font-size:1.55rem; font-weight:800; color:var(--ink); }}
  .header .meta {{ font-size:0.86rem; color:var(--muted); }}
  .banner {{ padding:10px 14px; border-radius:10px; font-size:0.84rem; font-weight:600; margin-bottom:12px; }}
  .banner.warn {{ background:var(--warn-soft); color:var(--warn); border-left:4px solid var(--warn); }}
  .banner.danger {{ background:var(--danger-soft); color:var(--danger); border-left:4px solid var(--danger); }}
  .banner.go {{ background:var(--go-soft); color:var(--go); border-left:4px solid var(--go); }}
  .banner.info {{ background:var(--drop-soft); color:var(--drop); border-left:4px solid var(--drop); }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }}
  .kpi {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }}
  .kpi-lbl {{ font-size:0.75rem; font-weight:700; color:var(--muted); }}
  .kpi-val {{ font-size:1.35rem; font-weight:800; color:var(--ink); margin:4px 0; font-variant-numeric:tabular-nums; }}
  .kpi-sub {{ font-size:0.75rem; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .insight {{ background:linear-gradient(135deg,#F6F2FF 0%,#FFF 100%); border:1px solid #E0D8F5; border-left:5px solid var(--purple); border-radius:12px; padding:14px 18px; margin-bottom:14px; }}
  .insight h2 {{ margin:0 0 10px; font-size:1rem; color:var(--purple-dark); }}
  .pat-row {{ display:flex; gap:8px; align-items:flex-start; font-size:0.88rem; color:var(--ink2); margin-bottom:6px; }}
  .pat-num {{ min-width:20px; height:20px; border-radius:999px; background:var(--purple); color:#FFF; font-size:0.72rem; font-weight:800; display:inline-flex; align-items:center; justify-content:center; margin-top:2px; }}
  .sec-title {{ font-size:1.08rem; font-weight:800; margin:18px 0 10px; color:var(--ink); }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin-bottom:14px; break-inside:avoid; }}
  .card.gold {{ border:2px solid var(--gold); background:var(--gold-soft); }}
  .card-top {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:8px; }}
  .badges {{ display:flex; gap:6px; flex-wrap:wrap; align-items:center; }}
  .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:0.74rem; font-weight:700; }}
  .pill.go {{ background:var(--go-soft); color:var(--go); }}
  .pill.warn {{ background:var(--warn-soft); color:var(--warn); }}
  .pill.drop {{ background:var(--drop-soft); color:var(--drop); }}
  .pill.purple {{ background:var(--purple-soft); color:var(--purple); }}
  .pill.gold-p {{ background:#FEF3C7; color:#92400E; border:1px solid #F59E0B; }}
  .pill.hot {{ background:var(--hot-soft); color:var(--hot); }}
  .dots {{ font-size:0.85rem; font-weight:800; letter-spacing:1px; }}
  .card-title {{ font-size:1.05rem; font-weight:800; margin:4px 0 6px; }}
  .reason {{ font-size:0.88rem; color:var(--ink2); margin-bottom:6px; }}
  .claim {{ display:inline-block; background:var(--go-soft); color:var(--go); border-radius:6px; padding:3px 9px; font-size:0.8rem; font-weight:700; margin-bottom:10px; }}
  .quote {{ background:#F4FBF9; border-left:3px solid var(--go); border-radius:6px; padding:8px 12px; margin-bottom:10px; }}
  .quote-lbl {{ font-size:0.74rem; font-weight:700; color:var(--go); margin-bottom:3px; }}
  .quote-txt {{ font-size:0.88rem; font-weight:600; color:var(--ink); }}
  .evid {{ display:flex; align-items:center; gap:10px; background:#FBF9FF; border:1px solid var(--line); border-radius:10px; padding:8px 10px; margin-bottom:12px; }}
  .thumb {{ width:88px; height:50px; border-radius:5px; object-fit:cover; flex-shrink:0; }}
  .evid-body {{ flex:1; min-width:0; }}
  .evid-title {{ font-size:0.85rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .evid-meta {{ font-size:0.76rem; color:var(--muted); margin-top:3px; font-variant-numeric:tabular-nums; }}
  .evid-btn {{ padding:5px 10px; border-radius:6px; border:1px solid #D8D3E8; font-size:0.75rem; font-weight:700; color:var(--purple-dark); text-decoration:none; white-space:nowrap; background:#FFF; }}
  .sb-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin-bottom:8px; }}
  .sb-cell {{ background:#FFF; border:1px solid var(--line); border-radius:8px; padding:9px 11px; font-size:0.84rem; color:var(--ink2); }}
  .sb-lbl {{ font-size:0.74rem; font-weight:800; color:var(--purple-dark); margin-bottom:3px; }}
  .note-strip {{ background:#FFF8F8; border:1px solid #FECACA; border-radius:8px; padding:7px 10px; font-size:0.78rem; color:var(--ink2); }}
  .empty {{ border:1px dashed #D8D3E8; border-radius:12px; padding:18px; text-align:center; color:var(--muted); background:#FFF; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.8rem; background:#FFF; border:1px solid var(--line); }}
  th {{ background:#FBF9FF; color:var(--muted); text-align:left; padding:7px 8px; border-bottom:1px solid var(--line); }}
  td {{ padding:7px 8px; border-bottom:1px solid var(--line); color:var(--ink2); vertical-align:top; }}
  td a {{ color:var(--purple-dark); text-decoration:none; font-weight:600; }}
  .footer {{ margin-top:20px; font-size:0.75rem; color:var(--muted); text-align:right; }}
  @media (max-width:768px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} .sb-grid {{ grid-template-columns:1fr; }} }}
  @media print {{
    body {{ background:#FFF; }}
    .wrap {{ max-width:100%; padding:0; }}
    .card, .insight, .kpi {{ break-inside:avoid; box-shadow:none; }}
    .evid-btn {{ border:1px solid #999; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div>
      <h1>💄 K-Beauty TrendSetter Pro — 주간 트렌드 결재 보고서</h1>
      <div class="meta">대상 제품: <b>{_e(product_name)}</b> · 보고 기준일: {_e(report_date)} · {_e(period_label)}</div>
    </div>
    <span class="pill purple">B2B Executive Report</span>
  </div>
  {''.join(banners)}
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-lbl">🎬 클리핑 쇼츠</div><div class="kpi-val">{total_v}건</div><div class="kpi-sub">자막 확보 {cap_v}건 ({cap_pct}%)</div></div>
    <div class="kpi"><div class="kpi-lbl">👀 평균 조회수</div><div class="kpi-val">{avg_views:,}회</div><div class="kpi-sub">평균 좋아요율 {avg_lr:.2f}%</div></div>
    <div class="kpi"><div class="kpi-lbl">🔥 최고 상승속도</div><div class="kpi-val">{max_vpd:,}회/일</div><div class="kpi-sub">{_e(period_label)} 급상승 1위</div></div>
    <div class="kpi"><div class="kpi-lbl">📊 판정 분포</div><div class="kpi-val">Go {len(go_items)} · Pivot {len(pivot_items)} · Drop {len(drop_items)}</div><div class="kpi-sub">총 {len(go_items)+len(pivot_items)+len(drop_items)}건 정합</div></div>
  </div>
  <div class="insight">
    <h2>🧭 이번 주 K-뷰티 시장 관통 패턴 (브랜드 편향 0%)</h2>
    {pat_html}
  </div>
  {mat_banner}
  <div class="sec-title">🎯 Go 판정 캠페인 컨셉 ({len(go_items)}건)</div>
  {''.join(go_cards)}
  <div class="sec-title">📋 Pivot &amp; Drop 탈락 사유 요약 ({len(pivot_items)+len(drop_items)}건)</div>
  <div style="overflow-x:auto;">
    <table>
      <thead><tr><th>판정</th><th>도메인</th><th>영상 제목 (쇼츠 링크)</th><th>조회수</th><th>판정/탈락 사유</th></tr></thead>
      <tbody>{''.join(triage_rows) or '<tr><td colspan="5">해당 항목 없음</td></tr>'}</tbody>
    </table>
  </div>
  <div class="footer">Generated by K-Beauty TrendSetter Pro (B2B v2) · 인쇄(Ctrl+P) 시 PDF로 바로 저장 가능합니다.</div>
</div>
</body>
</html>"""


# ───────────────────────── 전체 실행 ─────────────────────────
def run_pipeline(videos: List[Dict[str, Any]], product_name: str, llm=None,
                 api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite",
                 max_videos: int = 10, max_briefs: int = 3,
                 days_range: Optional[int] = None,
                 include_matrix: bool = True,
                 matrix_use_llm: bool = False,
                 use_history: bool = True,
                 history_path: Optional[str] = None) -> Dict[str, Any]:
    products = load_products()
    llm = llm or make_llm(api_key, model)
    vids = enrich_with_transcripts(videos[:max_videos])
    if use_history:
        vids = history_store.annotate_with_history(vids, save=True, store_path=history_path)

    fact_sheet = extract_facts(llm, vids)
    raw_facts = fact_sheet.facts
    market_patterns = [p.strip() for p in (fact_sheet.market_patterns or []) if p and p.strip()][:3]
    facts = audit_facts(raw_facts, vids)
    judgements = judge_fit(llm, facts, product_name, products)

    fact_by_id = {f["video_id"]: f for f in facts}
    go = sorted([j for j in judgements if j["decision"] == "Go"],
                key=lambda j: (-j["score"], -next((v["views_per_day"] for v in vids if v["video_id"] == j["video_id"]), 0)))[:max_briefs]
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
        "has_prev_snapshot": any(v.get("has_prev_snapshot") for v in vids),
        "new_videos_count": sum(1 for v in vids if v.get("is_new")),
    }
    matrix = (
        build_multi_product_matrix(
            vids, facts, products=products,
            primary_product=product_name, primary_judgements=judgements,
            llm=(llm if matrix_use_llm else None),
        )
        if include_matrix
        else None
    )
    result: Dict[str, Any] = {
        "product": product_name,
        "report_date": date.today().isoformat(),
        "days_range": days_range,
        "videos": vids,
        "facts": facts,
        "market_patterns": market_patterns,
        "judgements": judgements,
        "briefs": briefs,
        "multi_product_matrix": matrix,
        "stats": stats,
        "product_confidence": products[product_name].get("confidence", "unknown"),
    }
    copyables = format_copyable_outputs(result)
    result.update(copyables)
    return result


# ───────────────────────── 2단계 분리 실행 (Step 1 순수 탐색 → Step 2 제품 매칭) ─────────────────────────
def _summarize_recommended_formats(facts: List[Dict[str, Any]], videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 1에서 브랜드 편향 없이 바이럴 성과가 높은 포맷 상위 3종을 집계합니다."""
    v_by_id = {v["video_id"]: _ensure_video_metrics(v) for v in videos}
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts:
        if not f.get("evidence_ok"):
            continue
        tag = f.get("format_tag") or "기타"
        v = v_by_id.get(f["video_id"], {})
        buckets.setdefault(tag, []).append(v)

    summary: List[Dict[str, Any]] = []
    for tag, vs in buckets.items():
        avg_vpd = int(round(sum(x.get("views_per_day", 0) for x in vs) / max(1, len(vs))))
        top_v = max(vs, key=lambda x: x.get("views_per_day", 0))
        summary.append({
            "format_tag": tag,
            "count": len(vs),
            "avg_views_per_day": avg_vpd,
            "example_video_id": top_v.get("video_id", ""),
            "example_title": top_v.get("title", ""),
        })
    summary.sort(key=lambda r: (r["count"], r["avg_views_per_day"]), reverse=True)
    return summary[:3]


class MarketPatternsOnly(BaseModel):
    market_patterns: List[str] = Field(
        default_factory=list,
        description="상위 쇼츠의 공통점을 종합한 실무 인사이트 3개 문장",
    )


def extract_market_patterns_only(llm, videos: List[Dict[str, Any]], cached_facts: Dict[str, Dict[str, Any]]) -> List[str]:
    """모든 영상이 캐시된 경우 상위 15편 요약본만으로 메인 인사이트 3줄을 경량 생성합니다."""
    lines = []
    for v in videos[:15]:
        vid = v["video_id"]
        f = cached_facts.get(vid, {})
        lines.append(
            f"- 제목: {v.get('title','')} | 조회수: {v.get('views',0):,} | 구독자대비: {float(v.get('views_per_subscriber') or 0):.1f}배 | "
            f"포맷: {f.get('format_tag','-')} | 이유: {(f.get('viral_reason') or f.get('what_happens') or '')[:100]}"
        )
    prompt = (
        "당신은 올리브영 출신 10년차 K-뷰티 숏폼 마케팅 전략가입니다. 아래 상위 쇼츠들의 공통점을 종합해 메인 인사이트 요약 3문장을 작성하세요.\n"
        "- [① 공통 연출/포맷/키워드] + [② 시청자 심리·시즌 맥락] + [③ 실제 상위 영상 제목·수치 근거] 3요소를 담은 완성된 1~2문장(50~115자) 3개 작성.\n"
        "- 제공된 내용 외 사실·효능 추측 금지. 올영세일은 연 4회(3·6·9·12월).\n\n" + "\n".join(lines)
    )
    res = _invoke(llm, MarketPatternsOnly, prompt)
    return [p.strip() for p in (res.market_patterns or []) if p and p.strip()][:3]


def run_step1_explore(
    videos: List[Dict[str, Any]],
    path_label: str,
    days_range: int = 30,
    llm=None,
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash-lite",
    max_videos: int = 30,
    use_history: bool = True,
    history_path: Optional[str] = None,
    thinking_budget: Optional[int] = None,
    cached_facts: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """[Step 1] 브랜드 정보 완전 배제 — 한국(KR) 쇼츠 팩트·포맷·시장 패턴·추천 포맷만 객관 추출합니다."""
    llm = llm or make_llm(api_key, model, thinking_budget=thinking_budget)
    vids = enrich_with_transcripts(videos[:max_videos])
    if use_history:
        vids = history_store.annotate_with_history(vids, save=True, store_path=history_path)

    cache = cached_facts or {}
    uncached_vids = [v for v in vids if v["video_id"] not in cache]

    # 신규 영상만 15편 단위 청크 분할 AI 분석 (이미 분석된 video_id는 0토큰 캐시 재사용)
    raw_facts: List[Fact] = []
    market_patterns: List[str] = []
    if uncached_vids:
        chunk_size = 15
        for idx in range(0, len(uncached_vids), chunk_size):
            chunk = uncached_vids[idx:idx + chunk_size]
            fact_sheet = extract_facts(llm, chunk)
            raw_facts.extend(fact_sheet.facts or [])
            if idx == 0 and len(uncached_vids) >= min(5, len(vids)):
                market_patterns = [p.strip() for p in (fact_sheet.market_patterns or []) if p and p.strip()][:3]

    audited_new = audit_facts(raw_facts, uncached_vids) if uncached_vids else []
    new_by_id = {f["video_id"]: f for f in audited_new}

    facts: List[Dict[str, Any]] = []
    for v in vids:
        vid = v["video_id"]
        if vid in new_by_id:
            facts.append(new_by_id[vid])
        elif vid in cache:
            facts.append(dict(cache[vid]))

    if not market_patterns and vids:
        facts_map = {f["video_id"]: f for f in facts}
        market_patterns = extract_market_patterns_only(llm, vids, facts_map)

    recommended_formats = _summarize_recommended_formats(facts, vids)

    stats = {
        "videos": len(vids),
        "transcript_caption": sum(1 for v in vids if v["text_source"] == "caption"),
        "facts": len(facts),
        "evidence_verified": sum(1 for f in facts if f["evidence_ok"]),
        "has_prev_snapshot": any(v.get("has_prev_snapshot") for v in vids),
        "new_videos_count": sum(1 for v in vids if v.get("is_new")),
    }
    return {
        "path_label": path_label,
        "days_range": days_range,
        "report_date": date.today().isoformat(),
        "videos": vids,
        "facts": facts,
        "market_patterns": market_patterns,
        "recommended_formats": recommended_formats,
        "stats": stats,
    }


def _build_temp_product_spec(
    product_category: str,
    product_name: str,
    brand_keywords: str,
    expected_domain: str,
) -> Dict[str, Any]:
    """자유 입력 신제품용 임시 스펙 구성 (화장품법 금지어 자동 격리 + 반대 영역 non_fit 자동 설정)."""
    raw_tokens = [x.strip() for x in re.split(r"[\n,]+", brand_keywords or "") if x.strip()]
    safe_claims: List[str] = []
    for tok in raw_tokens:
        nt = _norm(tok)
        if any(_norm(m) in nt for m in ABSOLUTE_MEDICAL_BANNED_TERMS):
            continue
        if any(_norm(t) in nt for t in COSMETIC_LAW_BANNED_TERMS):
            continue
        safe_claims.append(tok)
    if not safe_claims:
        safe_claims = [f"{product_name} ({product_category}) 데일리 뷰티 제품"]

    if expected_domain == "색조/메이크업":
        non_fit = ["기초/스킨케어", "헤어/바디"]
    elif expected_domain == "헤어/바디":
        non_fit = ["기초/스킨케어", "색조/메이크업"]
    else:
        non_fit = ["색조 메이크업", "블러셔/틴트 믹싱", "헤어/바디"]

    return {
        "confidence": "custom",
        "verified_claims": safe_claims,
        "unverified_removed_from_v1": [],
        "fit_territory": [product_category] + safe_claims[:3],
        "non_fit_territory": non_fit,
    }


def run_step2_match(
    step1_result: Dict[str, Any],
    product_category: str,
    product_name: str,
    brand_keywords: str = "",
    llm=None,
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash-lite",
    max_briefs: int = 3,
) -> Dict[str, Any]:
    """[Step 2] 추가 YouTube 쿼터 0 — Step 1 결과에 자사 제품을 매칭해 Go/Pivot/Drop + 카피 3종 + 4단 콘티 생성."""
    products_ctx = dict(load_products())
    expected_domain = _expected_domain_from_category(product_category)
    clean_name = (product_name or "").strip() or "자사 신제품"

    if clean_name not in products_ctx:
        products_ctx[clean_name] = _build_temp_product_spec(
            product_category, clean_name, brand_keywords, expected_domain
        )

    llm = llm or make_llm(api_key, model)
    vids = [_ensure_video_metrics(v) for v in step1_result.get("videos", [])]
    facts = step1_result.get("facts", [])
    market_patterns = step1_result.get("market_patterns", [])

    judgements = judge_fit(llm, facts, clean_name, products_ctx, expected_domain=expected_domain)
    fact_by_id = {f["video_id"]: f for f in facts}
    go = sorted(
        [j for j in judgements if j["decision"] == "Go"],
        key=lambda j: (-j["score"], -next((v["views_per_day"] for v in vids if v["video_id"] == j["video_id"]), 0)),
    )[:max_briefs]
    briefs = write_briefs(llm, go, fact_by_id, clean_name, products_ctx)

    stats = {
        **step1_result.get("stats", {}),
        "videos": len(vids),
        "go": sum(1 for j in judgements if j["decision"] == "Go"),
        "pivot": sum(1 for j in judgements if j["decision"] == "Pivot"),
        "drop": sum(1 for j in judgements if j["decision"] == "Drop"),
        "briefs": len(briefs),
        "briefs_need_review": sum(1 for b in briefs if b["needs_review"]),
    }

    result: Dict[str, Any] = {
        "product": clean_name,
        "product_category": product_category,
        "expected_domain": expected_domain,
        "path_label": step1_result.get("path_label", ""),
        "report_date": step1_result.get("report_date") or date.today().isoformat(),
        "days_range": step1_result.get("days_range"),
        "videos": vids,
        "facts": facts,
        "market_patterns": market_patterns,
        "recommended_formats": step1_result.get("recommended_formats", []),
        "judgements": judgements,
        "briefs": briefs,
        "stats": stats,
        "product_confidence": products_ctx[clean_name].get("confidence", "custom"),
    }
    result.update(format_copyable_outputs(result))
    result["shareable_html_report"] = export_shareable_html_report(result)
    return result
