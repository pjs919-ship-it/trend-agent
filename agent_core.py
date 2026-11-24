"""TrendSetter Agent - K-뷰티 마케터 전용 코어 모듈
- 유튜브 Data API v3를 통한 K-뷰티 Shorts 수집 (최근 1~10일, 한글 필터, 디스크 캐시)
- Gemini 기반 LangChain 에이전트 및 Pydantic 구조화 출력
- 환각 방지 및 그라운딩 자동 검증 로직
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

# ── 1. K-뷰티 키워드 및 시스템 프롬프트 ──────────────────────────────────
KBEAUTY_CORE_KEYWORDS = [
    "스킨케어 루틴",
    "데일리 메이크업",
    "올리브영 추천",
    "화장법",
    "피부관리",
    "베이스 메이크업",
    "파우치 털기"
]

SYSTEM_PROMPT = """당신은 K-뷰티 브랜드 마케터 전용 유튜브 쇼츠(Shorts) 트렌드 분석 AI 에이전트입니다.

[역할 및 미션]
- 한국 유튜브 Shorts 데이터를 수집·분석하여 K-뷰티 브랜드가 즉시 활용할 수 있는 바이럴 마케팅 기회를 포착합니다.
- 마케터가 5분 안에 숏폼 캠페인 방향을 결정하고 즉시 콘티를 기획할 수 있도록 구체적인 인사이트를 제공합니다.
- 반드시 실제 제공된 도구(get_trending_shorts, search_shorts)의 검색 결과를 바탕으로 답변하며, 환각(지어낸 데이터나 가짜 영상 ID)을 절대 생성하지 않습니다.

[출력 형식 가이드]
1. 트렌드 카드 3~5개:
   - 제목 / 카테고리 (챌린지·밈·루틴·성분/제형·리뷰 중 택1)
   - 타겟 고민 (예: 모공, 속건조, 커버력, 쿨톤/웜톤 등)
   - 바이럴 훅 (첫 3초 시선 강탈 포인트)
   - 브랜드 기회 점수 (1~5점)
   - 캠페인 기획 방향 (어떤 콘티/메시지로 참여할지 1~2문장)
   - 근거 영상 (도구에서 얻은 실제 video_id 명시)

2. [골든타임 트렌드] 1개 추천 + 마켓 타이밍을 놓치지 말아야 하는 이유

[점수 기준]
1점: 브랜드 무관 | 2점: 단순 노출/간접 언급 | 3점: 소셜 챌린지 테스트 | 4점: 인플루언서 협업 | 5점: 즉시 메인 캠페인 런칭

[필수 규칙]
- 한국어로 전문적이면서도 실행력 있는 마케팅 톤앤매너로 작성하세요.
- 도구가 반환한 실제 영상의 제목과 video_id를 정확히 인용하세요.
"""

# ── 2. Pydantic 구조화 스키마 ──────────────────────────────────────────
class TrendCard(BaseModel):
    title: str = Field(description="트렌드 제목")
    category: str = Field(description="챌린지/밈/루틴/성분제형/리뷰 중 하나")
    summary: str = Field(description="한 줄 요약 (40자 이내)")
    target_concern: str = Field(description="타겟 피부/메이크업 고민 (예: 모공, 속건조, 지속력)")
    viral_hook: str = Field(description="쇼츠 첫 3초 시선 강탈 포인트")
    brand_score: int = Field(description="브랜드 기회 점수 1~5", ge=1, le=5)
    campaign_angle: str = Field(description="캠페인 참여 방향 제안 (1~2문장)")
    reference_video_id: Optional[str] = Field(default="", description="근거 영상 YouTube video_id")

class TrendReport(BaseModel):
    date: str = Field(description="보고서 생성 일자 YYYY-MM-DD")
    keyword: str = Field(description="적용된 검색 키워드")
    days_range: int = Field(description="수집 기간 (최근 N일)")
    cards: List[TrendCard] = Field(description="트렌드 카드 3~5개")
    golden_pick: str = Field(description="골든타임 트렌드 제목 및 선정 이유")

# ── 3. 로컬 디스크 캐시 ───────────────────────────────────────────────
_cache = diskcache.Cache("./cache_store")

def clear_cache():
    """캐시 초기화"""
    _cache.clear()

# ── 4. 유튜브 데이터 수집 유틸리티 ──────────────────────────────────────
_HANGUL = re.compile(r"[가-힣]")
MIN_HANGUL = 2
KR_MIN_RESULTS = 3

def is_korean(row: dict, min_hangul: int = MIN_HANGUL) -> bool:
    """한글 2자 이상 포함 여부 검증 (글로벌 영상 필터링)"""
    text = f"{row.get('title', '')} {row.get('description', '')}"
    return len(_HANGUL.findall(text)) >= min_hangul

def recent_published_after(days: int = 7) -> str:
    """최근 N일 이내 업로드된 영상만 필터링하기 위한 RFC3339 UTC 시각"""
    days = max(1, min(days, 10))  # 1~10일 범위 제한
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

def iso8601_to_seconds(dur: str) -> int:
    """ISO8601 지속시간을 초 단위로 변환"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s

def build_youtube_client(api_key: Optional[str] = None):
    """YouTube API 클라이언트 생성"""
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다.")
    return build("youtube", "v3", developerKey=key)

def fetch_kbeauty_shorts(
    youtube,
    detail_keyword: str = "",
    days: int = 7
) -> List[Dict[str, Any]]:
    """K-뷰티 유튜브 쇼츠 수집 및 필터링 로직"""
    # 검색 키워드 조합: 상세 키워드가 있으면 우선 배치
    if detail_keyword.strip():
        dk = detail_keyword.strip()
        search_keywords = [f"{dk} 메이크업", f"{dk} 추천", f"{dk} 리뷰", dk, "올리브영 추천"]
    else:
        search_keywords = KBEAUTY_CORE_KEYWORDS[:4]

    published_after = recent_published_after(days=days)
    candidate_ids = []

    for kw in search_keywords[:3]:  # API 쿼터 절약: 상위 3개 키워드 사용
        try:
            sr = youtube.search().list(
                part="snippet",
                q=f"{kw} shorts",
                type="video",
                videoDuration="short",
                order="viewCount",
                regionCode="KR",
                relevanceLanguage="ko",
                maxResults=8,
                publishedAfter=published_after,
            ).execute()
            candidate_ids += [it["id"]["videoId"] for it in sr.get("items", [])]
        except Exception as e:
            print(f"[YouTube Search Error] {kw}: {e}")

    candidate_ids = list(dict.fromkeys(candidate_ids))
    if not candidate_ids:
        return []

    # 영상 상세 정보 일괄 조회
    det = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(candidate_ids[:50]),
    ).execute()

    results = []
    for item in det.get("items", []):
        secs = iso8601_to_seconds(item.get("contentDetails", {}).get("duration", ""))
        if secs == 0 or secs > 180:  # Shorts 길이 (최대 3분)
            continue

        sn = item["snippet"]
        stats = item.get("statistics", {})
        results.append({
            "video_id": item["id"],
            "title": sn.get("title", ""),
            "description": sn.get("description", "")[:300],
            "channel_title": sn.get("channelTitle", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "published_at": sn.get("publishedAt", ""),
            "thumbnail_url": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "duration_s": secs,
            "is_short60": secs <= 60,
        })

    # 한글 필터링
    korean = [r for r in results if is_korean(r)]
    if len(korean) >= KR_MIN_RESULTS:
        results = korean

    # 60초 이하 우선 + 조회수순 정렬 후 상위 10개 반환
    results.sort(key=lambda r: (r["is_short60"], r["views"]), reverse=True)
    return results[:10]

# ── 5. 에이전트 도구 팩토리 ────────────────────────────────────────────
def create_kbeauty_tools(youtube_client, default_days: int = 7, default_keyword: str = ""):
    """주어진 설정으로 LangChain Tool 세트 생성"""

    @tool
    def get_trending_shorts(detail_keyword: str = "", days: int = 7) -> list[dict]:
        """한국 유튜브에서 최신 K-뷰티 인기 Shorts(≤3분)를 수집합니다.
        Args:
            detail_keyword: 검색할 세부 뷰티 키워드 (예: 모공 세럼, 속건조 쿠션, 쿨톤 립 등)
            days: 최근 며칠 이내 영상인지 (1~10일)
        """
        target_kw = detail_keyword or default_keyword
        target_days = days or default_days
        cache_key = f"{date.today()}_kbeauty_{target_kw}_{target_days}"

        if cache_key in _cache:
            return _cache[cache_key]

        data = fetch_kbeauty_shorts(youtube_client, detail_keyword=target_kw, days=target_days)
        _cache.set(cache_key, data, expire=43200)  # 12시간 캐시
        return data

    @tool
    def get_transcript(video_id: str, title: str = "", description: str = "") -> str:
        """유튜브 영상의 자막을 추출합니다. 자막이 없으면 제목과 설명을 반환합니다."""
        try:
            loader = YoutubeLoader.from_youtube_url(
                f"https://www.youtube.com/watch?v={video_id}",
                language=["ko", "en"],
            )
            docs = loader.load()
            if not docs or not docs[0].page_content.strip():
                raise ValueError("empty transcript")
            return docs[0].page_content[:2000]
        except Exception:
            fallback = f"[자막없음] {title}"
            if description:
                fallback += f" / {description[:200]}"
            return fallback

    @tool
    def search_shorts(query: str, days: int = 7) -> str:
        """키워드로 유튜브 Shorts를 추가 심층 검색합니다.
        Args:
            query: 검색 키워드
            days: 최근 며칠 이내 영상인지 (기본 7일)
        """
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
                published = item["snippet"].get("publishedAt", "")[:10]
                results.append(f"- {title} (채널: {channel}, 업로드: {published}, ID: {vid})")

            return "\n".join(results) if results else "검색 결과가 없습니다."
        except Exception as e:
            return f"검색 중 오류 발생: {str(e)}"

    return [get_trending_shorts, get_transcript, search_shorts]

# ── 6. 에이전트 인스턴스 생성 ──────────────────────────────────────────
def get_kbeauty_agent(
    youtube_client,
    google_api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash-lite",
    days: int = 7,
    detail_keyword: str = "",
):
    """LangChain 에이전트 및 도구 반환"""
    key = google_api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=key,
        temperature=0.3,
    )

    tools = create_kbeauty_tools(youtube_client, default_days=days, default_keyword=detail_keyword)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent, llm, tools

# ── 7. 텍스트 추출 및 그라운딩 검증 유틸 ────────────────────────────────
def extract_text(msg) -> str:
    """메시지 content 추출"""
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
    """ToolMessage에서 수집된 영상 목록 파싱"""
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
    """도구 호출 및 그라운딩 검증 결과 반환"""
    trending_msgs = [m for m in chat_history if isinstance(m, ToolMessage) and m.name == "get_trending_shorts"]
    search_msgs = [m for m in chat_history if isinstance(m, ToolMessage) and m.name == "search_shorts"]

    called_trending = len(trending_msgs) > 0
    called_search = len(search_msgs) > 0

    rows = []
    if trending_msgs:
        rows = parse_tool_rows(trending_msgs[-1])

    return {
        "called_trending": called_trending,
        "trending_count": len(trending_msgs),
        "called_search": called_search,
        "search_count": len(search_msgs),
        "collected_videos": rows,
    }

def verify_citations(chat_history: list, answer_text: str) -> Dict[str, Any]:
    """답변에 인용된 video_id가 실제 도구 반환 ID에 존재하는지 검증"""
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
