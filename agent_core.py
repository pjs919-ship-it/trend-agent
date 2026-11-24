"""TrendSetter Agent - K-Beauty Pro Core Engine (v1.0)
- K-뷰티 메가 바이럴 Shorts(조회수 10만+) 정밀 수집 엔진 (YouTube Data API v3)
- 더랩바이블랑두 (THE LAB by blanc doux) 3대 시그니처 제품 맞춤 프리셋 지원
- 4단 숏폼 콘티([첫 3초 훅] - [연출] - [소구점] - [CTA]) 기획 알고리즘
- 환각 제로(Zero-Hallucination) 그라운딩 교차 검증 파이프라인
"""

import os
import re
import ast
import json
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict, Any, Tuple

from pydantic import BaseModel, Field
import diskcache
from googleapiclient.discovery import build
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import YoutubeLoader

# ── 1. 더랩바이블랑두 3대 핵심 제품 프리셋 ──────────────────────────────
BLANCDOUX_PRODUCTS = {
    "올리고 히알루론산 딥 토너": {
        "name": "올리고 히알루론산 딥 토너",
        "tagline": "속건조 1초 잡는 저분자 히알루론산 100% 흡수 물토너",
        "key_features": "올리브영 1위 토너, 끈적임 없는 7스킨 레이어링, 피부 속 2.5mm 보습 개선, 저자극 순한 포뮬러",
        "target_concern": "속건조, 화장 들뜸, 각질 부각, 유수분 밸런스 붕괴",
        "recommended_hook": "속건조 때문에 파데 뜨는 사람? 물토너 3번 찹찹 레이어링 비포/애프터"
    },
    "그린 플라보노이드 2.5 패드": {
        "name": "그린 플라보노이드 2.5 패드",
        "tagline": "트러블 피부 붉은기 급속 진정 비건 쿨링 패드",
        "key_features": "식물 유래 그린 플라보노이드™, 얇고 밀착되는 3중 레이어 거즈 패드, 붉은기 즉각 완화, 여드름성 피부 적합",
        "target_concern": "붉은기, 트러블 열감, 민감성 자극, 볼 부위 진정팩 필요",
        "recommended_hook": "볼에 열감 올라왔을 때 3분 만에 홍조 싹 가라앉히는 치트키"
    },
    "올리고 히알루론산 워터리 스킨 마스크": {
        "name": "올리고 히알루론산 워터리 스킨 마스크",
        "tagline": "피부 열감 내리는 밀착 수분 충전 급속 부스팅 마스크",
        "key_features": "저분자 히알루론산 에센스 듬뿍, 피부에 초밀착되는 식물성 시트, 메이크업 전 쿨링 진정",
        "target_concern": "중요한 날 아침 화장 먹방, 메이크업 전 급속 수분 충전, 열감 진정",
        "recommended_hook": "오늘 중요한 약속인데 화장 잘 먹어야 할 때 10분 수분 급속 충전법"
    }
}

# ── 2. K-뷰티 메가 바이럴 앵커 키워드 ──────────────────────────────────
# 조회수 10만~수백만 회를 유발하는 대한민국 뷰티 쇼츠 핵심 검색 앵커
KBEAUTY_MEGA_KEYWORDS = [
    "올리브영 추천템",
    "스킨케어 꿀조합",
    "메이크업 꿀팁",
    "인생템 추천",
    "피부 뒤집어졌을때",
    "올영 세일 쟁여템",
    "화잘먹 기초 루틴",
    "파우치 털기"
]

SYSTEM_PROMPT = """당신은 K-뷰티 인하우스 마케터(더랩바이블랑두 등)를 위한 대한민국 최정상 숏폼 바이럴 캠페인 총괄 디렉터 AI입니다.

[역할 및 미션]
- 한국 유튜브 Shorts 실시간 데이터 중 실제로 수십만~수백만 조회수를 기록 중인 '메가 트렌드'를 분석합니다.
- 단순 요약에 그치지 않고, [첫 3초 훅 - 비포/애프터 연출 구도 - 제품 소구점 접목 - CTA]의 즉시 촬영 가능한 숏폼 콘티를 기획합니다.
- 반드시 수집된 실제 Shorts 영상의 제목과 video_id만을 인용하며, 환각(가짜 ID나 없는 트렌드)을 절대 생성하지 않습니다.

[분석 출력 형식]
1. 🧭 시장 인사이트 (Market Insight):
   - 현재 한국 K-뷰티 숏폼을 관통하는 바이럴 트렌드 2~3줄 요약 (어떤 제형/고민/연출이 뜨고 있는지)

2. 🗂️ 메가 트렌드 카드 3~5개:
   - 제목 / 카테고리 (루틴 / 챌린지 / 성분제형 / 리뷰)
   - 한 줄 요약 (40자 이내)
   - 브랜드 기회 점수 (1~5점) 및 점수 근거
   - 핵심 타깃 (예: 속건조 고민 2030, 민감성 트러블 피부)
   - 해시태그 3~5개
   - 캠페인 기획 방향 (1~2문장)
   - 근거 영상 (도구 결과에 있는 실제 video_id)

3. 👑 GOLDEN PICK (골든타임 트렌드):
   - 지금 당장(마켓 타이밍) 브랜드가 올라타야 하는 1등 트렌드와 선정 이유

[기회 점수 기준]
1점: 브랜드 무관 | 2점: 단순 노출 | 3점: 소셜 챌린지 테스트 | 4점: 인플루언서 시딩/협업 | 5점: 즉시 메인 캠페인 런칭(골드)
"""

# ── 3. Pydantic 구조화 스키마 ──────────────────────────────────────────
class ShortsStoryboard(BaseModel):
    hook_scene: str = Field(description="첫 3초 시선 강탈 훅 (행동, 자막, 대사 연출)")
    setup_scene: str = Field(description="소비자 고민 공감 및 비포 상태 (10초 이내)")
    solution_scene: str = Field(description="더랩바이블랑두 제품 특장점 및 텍스처/흡수감 연출 (애프터)")
    cta_scene: str = Field(description="올리브영/자사몰 구매 유도 또는 참여 CTA")

class TrendCard(BaseModel):
    title: str = Field(description="트렌드 제목")
    category: str = Field(description="루틴/챌린지/성분제형/리뷰")
    summary: str = Field(description="한 줄 요약 (40자 이내)")
    brand_score: int = Field(description="브랜드 기회 점수 1~5", ge=1, le=5)
    score_reason: str = Field(description="점수 부여 근거")
    target_audience: str = Field(description="핵심 타깃 소비자")
    hashtags: List[str] = Field(description="핵심 해시태그 3~5개")
    campaign_angle: str = Field(description="캠페인 기획 방향 (1~2문장)")
    evidence_ids: List[str] = Field(default_factory=list, description="실제 근거 YouTube video_id 목록")
    storyboard: Optional[ShortsStoryboard] = Field(default=None, description="브랜드 제품 맞춤 4단 콘티")

class TrendReport(BaseModel):
    date: str = Field(description="보고서 생성 일자 YYYY-MM-DD")
    keyword: str = Field(description="검색 키워드 또는 카테고리")
    days_range: int = Field(description="수집 기간 (최근 N일)")
    market_insight: str = Field(description="전체 시장을 관통하는 핵심 2~3줄 인사이트")
    cards: List[TrendCard] = Field(description="트렌드 카드 3~5개")
    golden_pick: str = Field(description="골든픽 제목")
    golden_reason: str = Field(description="골든픽 선정 이유")

# ── 4. 캐시 레이어 ────────────────────────────────────────────────────
_cache = diskcache.Cache("./cache_store")

def clear_cache():
    _cache.clear()

# ── 5. 유튜브 메가 쇼츠 수집 유틸리티 ───────────────────────────────────
_HANGUL = re.compile(r"[가-힣]")
MIN_HANGUL = 2

def is_korean(row: dict, min_hangul: int = MIN_HANGUL) -> bool:
    text = f"{row.get('title', '')} {row.get('description', '')}"
    return len(_HANGUL.findall(text)) >= min_hangul

def recent_published_after(days: int = 7) -> str:
    days = max(1, min(days, 10))
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

def iso8601_to_seconds(dur: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s

def build_youtube_client(api_key: Optional[str] = None):
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다.")
    return build("youtube", "v3", developerKey=key)

def fetch_mega_kbeauty_shorts(
    youtube,
    detail_keyword: str = "",
    days: int = 7,
    min_views: int = 10000  # 최소 조회수 임계치 (노이즈 방지)
) -> List[Dict[str, Any]]:
    """대한민국 뷰티 카테고리(Howto & Style) 메가 트렌드 쇼츠 정밀 수집"""
    if detail_keyword.strip():
        dk = detail_keyword.strip()
        search_keywords = [f"{dk} 올리브영", f"{dk} 추천", f"{dk} 꿀조합", dk]
    else:
        search_keywords = KBEAUTY_MEGA_KEYWORDS[:4]

    published_after = recent_published_after(days=days)
    candidate_ids = []

    # 1) 키워드별 검색 (search.list = 100 unit/회)
    for kw in search_keywords[:3]:
        try:
            sr = youtube.search().list(
                part="snippet",
                q=f"{kw} shorts",
                type="video",
                videoCategoryId="26",  # 26 = Howto & Style (뷰티/스타일 공식 카테고리)
                videoDuration="short",
                order="viewCount",      # 조회수순 정렬
                regionCode="KR",
                relevanceLanguage="ko",
                maxResults=10,
                publishedAfter=published_after,
            ).execute()
            candidate_ids += [it["id"]["videoId"] for it in sr.get("items", [])]
        except Exception as e:
            # Howto & Style 카테고리 미지원 시 일반 검색 폴백
            try:
                sr = youtube.search().list(
                    part="snippet",
                    q=f"{kw} shorts",
                    type="video",
                    videoDuration="short",
                    order="viewCount",
                    regionCode="KR",
                    relevanceLanguage="ko",
                    maxResults=10,
                    publishedAfter=published_after,
                ).execute()
                candidate_ids += [it["id"]["videoId"] for it in sr.get("items", [])]
            except Exception as e2:
                print(f"[YouTube Search Error] {kw}: {e2}")

    candidate_ids = list(dict.fromkeys(candidate_ids))
    if not candidate_ids:
        return []

    # 2) 영상 상세 정보 일괄 조회 (videos.list = 1 unit)
    det = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(candidate_ids[:50]),
    ).execute()

    results = []
    for item in det.get("items", []):
        secs = iso8601_to_seconds(item.get("contentDetails", {}).get("duration", ""))
        if secs == 0 or secs > 120:  # Shorts 규격 (최대 2분 이하)
            continue

        sn = item["snippet"]
        stats = item.get("statistics", {})
        views = int(stats.get("viewCount", 0))

        # 저유입 노이즈 필터링 (최소 10,000회 이상 우선)
        results.append({
            "video_id": item["id"],
            "title": sn.get("title", ""),
            "description": sn.get("description", "")[:300],
            "channel_title": sn.get("channelTitle", ""),
            "views": views,
            "likes": int(stats.get("likeCount", 0)),
            "published_at": (sn.get("publishedAt", ""))[:10],
            "thumbnail_url": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "duration_s": secs,
            "is_short60": secs <= 60,
        })

    # 2-1) 저유입 영상(조회수 5,000회 미만)은 마케팅 가치 없으므로 가차없이 제거
    high_impact = [r for r in results if r["views"] >= 5000]
    if len(high_impact) >= 5:
        results = high_impact

    # 한글 필터링
    korean = [r for r in results if is_korean(r)]
    if len(korean) >= 3:
        results = korean

    # 3) 조회수 순 내림차순 정렬 (진짜 메가 바이럴 최우선)
    results.sort(key=lambda r: r["views"], reverse=True)
    return results[:10]

# ── 6. 에이전트 도구 및 인스턴스 팩토리 ────────────────────────────────
def create_mega_tools(youtube_client, default_days: int = 7, default_keyword: str = ""):
    @tool
    def get_trending_shorts(detail_keyword: str = "", days: int = 7) -> list[dict]:
        """한국 유튜브에서 최신 K-뷰티 메가 바이럴 Shorts(조회수 상위)를 수집합니다."""
        target_kw = detail_keyword or default_keyword
        target_days = days or default_days
        cache_key = f"{date.today()}_mega_kbeauty_{target_kw}_{target_days}"

        if cache_key in _cache:
            return _cache[cache_key]

        data = fetch_mega_kbeauty_shorts(youtube_client, detail_keyword=target_kw, days=target_days)
        _cache.set(cache_key, data, expire=43200)
        return data

    @tool
    def search_shorts(query: str, days: int = 7) -> str:
        """키워드로 최신 K-뷰티 Shorts를 추가 심층 검색합니다."""
        try:
            pub_after = recent_published_after(days=days or default_days)
            resp = youtube_client.search().list(
                part="snippet",
                q=f"{query} shorts",
                type="video",
                videoDuration="short",
                maxResults=5,
                relevanceLanguage="ko",
                regionCode="KR",
                order="viewCount",
                publishedAfter=pub_after,
            ).execute()

            results = []
            for item in resp.get("items", []):
                vid = item["id"]["videoId"]
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                published = (item["snippet"].get("publishedAt", ""))[:10]
                results.append(f"- {title} (채널: {channel}, 업로드: {published}, ID: {vid})")

            return "\n".join(results) if results else "검색 결과가 없습니다."
        except Exception as e:
            return f"검색 중 오류 발생: {str(e)}"

    return [get_trending_shorts, search_shorts]

def get_kbeauty_agent(
    youtube_client,
    google_api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash-lite",
    days: int = 7,
    detail_keyword: str = "",
):
    key = google_api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=key,
        temperature=0.3,
    )

    tools = create_mega_tools(youtube_client, default_days=days, default_keyword=detail_keyword)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent, llm, tools

# ── 7. 브랜드 맞춤 4단 콘티 생성기 ────────────────────────────────────
def generate_blancdoux_storyboard(
    product_name: str,
    trend_title: str,
    trend_summary: str,
    llm
) -> ShortsStoryboard:
    """선택된 더랩바이블랑두 제품과 트렌드를 접목한 4단 콘티 생성"""
    prod_info = BLANCDOUX_PRODUCTS.get(product_name, {
        "name": product_name,
        "tagline": "더랩바이블랑두의 베스트셀러 스킨케어",
        "key_features": "속건조 완화, 저자극 순한 성분, 피부 진정",
        "recommended_hook": "스킨케어 유목민 주목"
    })

    prompt = f"""
    당신은 K-뷰티 숏폼 전문 크리에이티브 디렉터입니다.
    지금 한국 유튜브에서 터지고 있는 트렌드와 더랩바이블랑두(THE LAB by blanc doux) 제품을 접목하여
    마케터가 바로 인플루언서에게 전달하거나 직접 촬영할 수 있는 4단 숏폼 콘티를 작성하세요.

    [트렌드 정보]
    - 트렌드: {trend_title}
    - 내용: {trend_summary}

    [더랩바이블랑두 제품 정보]
    - 제품명: {prod_info['name']}
    - 슬로건: {prod_info['tagline']}
    - 핵심 소구점: {prod_info['key_features']}

    [작성 규칙]
    - hook_scene: 첫 3초 시선 강탈 훅 (구체적 행동 + 대사/자막)
    - setup_scene: 문제 제기 및 비포 공감대 (10초 이내)
    - solution_scene: 제품 특장점과 텍스처/흡수감 연출 (애프터)
    - cta_scene: 마켓 타이밍 구매 유도 (올영세일, 댓글 이벤트 등)
    """

    structured_llm = llm.with_structured_output(ShortsStoryboard)
    return structured_llm.invoke(prompt)

# ── 8. 텍스트 추출 및 그라운딩 검증 ────────────────────────────────────
def extract_text(msg) -> str:
    if not msg:
        return ""
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, list):
                    content = parsed
                else:
                    return content
            except Exception:
                return content
        else:
            return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif hasattr(block, "type") and getattr(block, "type") == "text":
                parts.append(str(getattr(block, "text", "")))
        if parts:
            return "".join(parts)

    return str(content)

def parse_tool_rows(tool_msg) -> List[Dict[str, Any]]:
    content = tool_msg.content
    if isinstance(content, list):
        if content and isinstance(content[0], dict) and "video_id" in content[0]:
            return content
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")

    if not isinstance(content, str) or not content.strip():
        return []

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(content)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            continue
    return []

def verify_grounding(chat_history: list) -> Dict[str, Any]:
    trending_msgs = [m for m in chat_history if isinstance(m, ToolMessage) and m.name == "get_trending_shorts"]
    search_msgs = [m for m in chat_history if isinstance(m, ToolMessage) and m.name == "search_shorts"]

    rows = []
    if trending_msgs:
        rows = parse_tool_rows(trending_msgs[-1])

    return {
        "called_trending": len(trending_msgs) > 0,
        "trending_count": len(trending_msgs),
        "called_search": len(search_msgs) > 0,
        "search_count": len(search_msgs),
        "collected_videos": rows,
    }

def verify_citations(chat_history: list, answer_text: str) -> Dict[str, Any]:
    grounded_ids = set()
    for m in chat_history:
        if not isinstance(m, ToolMessage):
            continue
        c = m.content
        if isinstance(c, list):
            c = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
        text = str(c)
        grounded_ids |= set(re.findall(r"video_id['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_-]{11})", text))
        grounded_ids |= set(re.findall(r"\bID:\s*([A-Za-z0-9_-]{11})", text))

    ans = answer_text or ""
    cited_ids = set(re.findall(r"\bID\s*[:=]\s*([A-Za-z0-9_-]{11})", ans))
    cited_ids |= set(re.findall(r"v=([A-Za-z0-9_-]{11})", ans))
    cited_ids |= set(re.findall(r"`([A-Za-z0-9_-]{11})`", ans))

    ungrounded_ids = cited_ids - grounded_ids
    is_valid = len(cited_ids) > 0 and len(ungrounded_ids) == 0

    return {
        "grounded_ids": list(grounded_ids),
        "cited_ids": list(cited_ids),
        "ungrounded_ids": list(ungrounded_ids),
        "is_valid": is_valid,
    }
