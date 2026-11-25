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

# ── 1. 제품 정보 로드 (products.json 단일 출처) & YouTube 예산 가드 ──────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, "products.json")
USAGE_LOG_PATH = os.path.join(BASE_DIR, "qa", "usage_log.json")
YOUTUBE_UNIT_LIMIT = 1500


def load_products(path: str = PRODUCTS_PATH) -> Dict[str, Any]:
    """products.json에서 확인된 제품 정보를 로드하고 하위 호환 필드를 구성합니다."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f).get("products", {})
    out: Dict[str, Any] = {}
    for name, info in raw.items():
        claims = info.get("verified_claims", [])
        fit_terr = info.get("fit_territory", [])
        out[name] = {
            **info,
            # 하위 호환성 유지 (app.py 등 기존 참조용, 확인된 문구만 조합)
            "name": name,
            "tagline": claims[0] if claims else name,
            "key_features": ", ".join(claims),
            "target_concern": ", ".join(fit_terr),
        }
    return out


BLANCDOUX_PRODUCTS = load_products()


def get_used_youtube_units(log_path: str = USAGE_LOG_PATH) -> int:
    """qa/usage_log.json에서 누적 YouTube Data API 사용 유닛을 반환합니다."""
    if not os.path.exists(log_path):
        return 0
    try:
        with open(log_path, encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("total_units", 0))
    except Exception:
        return 0


def record_youtube_units(
    units: int,
    action: str = "",
    meta: Optional[Dict[str, Any]] = None,
    log_path: str = USAGE_LOG_PATH,
    limit: int = YOUTUBE_UNIT_LIMIT,
) -> int:
    """YouTube API 호출 전 누적 유닛을 확인·기록합니다. 상한 초과 시 RuntimeError 발생."""
    if units < 0:
        raise ValueError("units는 0 이상이어야 합니다.")
    data: Dict[str, Any] = {"total_units": 0, "limit": limit, "events": []}
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass

    current = int(data.get("total_units", 0))
    if current + units > limit:
        raise RuntimeError(
            f"YouTube API 누적 유닛 상한({limit}) 초과로 호출을 차단했습니다: "
            f"현재 {current} + 요청 {units} = {current + units} > {limit}"
        )

    new_total = current + units
    data["total_units"] = new_total
    data["limit"] = limit
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []
    events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "units": units,
        "total_after": new_total,
        "meta": meta or {},
    })
    data["events"] = events

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return new_total

# ── 2. 한국(KR) 기준 2단계 탐색 트리 & 앵커 키워드 ─────────────────────
KR_EXPLORE_TREE: Dict[str, Dict[str, Any]] = {
    "beauty": {
        "label": "뷰티 전체",
        "parent": None,
        "level": 0,
        "mode": "search",
        "keywords": ["올리브영 추천템", "화장품 추천", "뷰티 꿀템"],
    },
    "beauty/skincare": {
        "label": "기초 스킨케어",
        "parent": "beauty",
        "level": 1,
        "mode": "search",
        "keywords": ["스킨케어", "기초 루틴", "속건조"],
    },
    "beauty/makeup": {
        "label": "색조 메이크업",
        "parent": "beauty",
        "level": 1,
        "mode": "search",
        "keywords": ["메이크업", "립틴트", "블러셔"],
    },
    "beauty/hairbody": {
        "label": "헤어·바디",
        "parent": "beauty",
        "level": 1,
        "mode": "search",
        "keywords": ["헤어케어 추천", "바디로션 추천", "샴푸 추천"],
    },
    "beauty/skincare/toner": {
        "label": "토너·패드",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["토너 추천", "토너패드", "닦토"],
    },
    "beauty/skincare/serum": {
        "label": "세럼·앰플",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["수분세럼", "앰플 추천", "진정세럼"],
    },
    "beauty/skincare/cream": {
        "label": "크림·로션",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["수분크림", "장벽크림", "로션 추천"],
    },
    "beauty/skincare/sun": {
        "label": "선크림",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["선크림 추천", "무기자차", "선세럼"],
    },
    "beauty/skincare/mask": {
        "label": "마스크팩",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["마스크팩 추천", "1일1팩", "수분팩"],
    },
    "beauty/skincare/cleansing": {
        "label": "클렌징",
        "parent": "beauty/skincare",
        "level": 2,
        "mode": "search",
        "keywords": ["클렌징오일 추천", "클렌징폼", "블랙헤드 클렌징"],
    },
    "beauty/makeup/lip": {
        "label": "립·틴트",
        "parent": "beauty/makeup",
        "level": 2,
        "mode": "search",
        "keywords": ["립틴트 추천", "립조합", "글로우립"],
    },
    "beauty/makeup/blush": {
        "label": "블러셔",
        "parent": "beauty/makeup",
        "level": 2,
        "mode": "search",
        "keywords": ["블러셔 추천", "치크 꿀팁", "쿨톤 블러셔"],
    },
    "beauty/makeup/cushion": {
        "label": "쿠션·파데",
        "parent": "beauty/makeup",
        "level": 2,
        "mode": "search",
        "keywords": ["쿠션 추천", "파데 추천", "화잘먹"],
    },
    "beauty/makeup/eye": {
        "label": "아이메이크업",
        "parent": "beauty/makeup",
        "level": 2,
        "mode": "search",
        "keywords": ["아이섀도우", "속눈썹 꿀팁", "아이라인"],
    },
    "beauty/hairbody/hair": {
        "label": "샴푸·트리트먼트",
        "parent": "beauty/hairbody",
        "level": 2,
        "mode": "search",
        "keywords": ["샴푸 추천", "트리트먼트 추천", "두피케어"],
    },
    "beauty/hairbody/body": {
        "label": "바디케어",
        "parent": "beauty/hairbody",
        "level": 2,
        "mode": "search",
        "keywords": ["바디로션 추천", "바디워시 추천", "바디미스트"],
    },
}

SPAM_KEYWORDS = (
    "무료나눔",
    "이벤트 참여",
    "쿠팡파트너스 링크",
    "구독 좋아요 알람",
    "댓글 이벤트 참여",
)

# 조회수 10만~수백만 회를 유발하는 대한민국 기초 스킨케어 뷰티 쇼츠 핵심 검색 앵커 (하위 호환)
KBEAUTY_MEGA_KEYWORDS = [
    "올리브영 스킨케어 추천",
    "피부 뒤집어졌을때",
    "화잘먹 기초 루틴",
    "스킨케어 꿀조합",
    "올영 세일 쟁여템",
    "속건조 토너 추천",
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
_cache = diskcache.Cache(os.path.join(BASE_DIR, "cache_store"))

def clear_cache():
    _cache.clear()

# ── 5. 유튜브 메가 쇼츠 수집 유틸리티 ───────────────────────────────────
_HANGUL = re.compile(r"[가-힣]")
_HASHTAG_RE = re.compile(r"#\S+")
MIN_HANGUL = 4

def is_korean(row: dict, min_hangul: int = MIN_HANGUL) -> bool:
    """해시태그를 제외한 제목+설명에서 완성형 한글이 min_hangul자 이상인지 확인 (해외 #메이크업 낚시 차단)."""
    title_clean = _HASHTAG_RE.sub("", row.get("title", ""))
    desc_clean = _HASHTAG_RE.sub("", row.get("description", ""))
    if len(_HANGUL.findall(title_clean)) >= min_hangul:
        return True
    return len(_HANGUL.findall(f"{title_clean} {desc_clean}")) >= max(min_hangul, 6)

def recent_published_after(days: int = 7) -> str:
    days = max(1, min(days, 30))
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

def compute_video_metrics(views: int, likes: int, published_at: str, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """영상의 경과일(float, 최소 0.25일), 일평균 조회수, 좋아요 반응률을 계산합니다."""
    now = now_utc or datetime.now(timezone.utc)
    try:
        pub_dt = datetime.fromisoformat((published_at or "").replace("Z", "+00:00"))
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        elapsed_hours = max(0.0, (now - pub_dt).total_seconds() / 3600.0)
        days_since = round(max(0.25, elapsed_hours / 24.0), 2)
    except Exception:
        days_since = 1.0
    views_per_day = int(round(views / days_since))
    like_rate = round(likes / max(1, views) * 100, 2)
    return {
        "days_since_published": days_since,
        "views_per_day": views_per_day,
        "like_rate": like_rate,
    }


def fetch_mega_kbeauty_shorts(
    youtube,
    detail_keyword: str = "",
    days: int = 7,
    min_views: int = 10000,  # 최소 조회수 임계치 (노이즈 방지)
    sort_by: str = "velocity",  # "velocity" (일평균+총조회수 복합) | "views" (총조회수)
    max_queries: int = 3,
) -> List[Dict[str, Any]]:
    """대한민국 뷰티 카테고리(Howto & Style) 메가 트렌드 쇼츠 정밀 수집"""
    if detail_keyword.strip():
        dk = detail_keyword.strip()
        search_keywords = [f"{dk} 올리브영", f"{dk} 추천", f"{dk} 꿀조합", dk][:max_queries]
    else:
        search_keywords = KBEAUTY_MEGA_KEYWORDS[:max_queries]

    published_after = recent_published_after(days=days)
    candidate_ids = []

    # 1) 키워드별 검색 (search.list = 100 unit/회)
    for kw in search_keywords:
        try:
            record_youtube_units(100, action="search.list", meta={"q": kw, "category": "26", "days": days})
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
        except RuntimeError:
            raise
        except Exception as e:
            # Howto & Style 카테고리 미지원 시 일반 검색 폴백
            try:
                record_youtube_units(100, action="search.list_fallback", meta={"q": kw, "days": days})
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
            except RuntimeError:
                raise
            except Exception as e2:
                print(f"[YouTube Search Error] {kw}: {e2}")

    candidate_ids = list(dict.fromkeys(candidate_ids))
    if not candidate_ids:
        return []

    # 2) 영상 상세 정보 일괄 조회 (videos.list = 1 unit)
    record_youtube_units(1, action="videos.list", meta={"count": len(candidate_ids[:50])})
    det = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(candidate_ids[:50]),
    ).execute()

    now_utc = datetime.now(timezone.utc)
    results = []
    for item in det.get("items", []):
        secs = iso8601_to_seconds(item.get("contentDetails", {}).get("duration", ""))
        if secs == 0 or secs > 120:  # Shorts 규격 (최대 2분 이하)
            continue

        sn = item["snippet"]
        stats = item.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        pub_raw = sn.get("publishedAt", "")
        metrics = compute_video_metrics(views, likes, pub_raw, now_utc=now_utc)

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
            "low_views_fallback": False,
        })

    # 2-1) min_views 기준 적용 (충분한 결과가 없을 때만 안전 폴백 + 경고 플래그)
    high_impact = [r for r in results if r["views"] >= min_views]
    if len(high_impact) >= 5:
        results = high_impact
    else:
        for r in results:
            if r["views"] < min_views:
                r["low_views_fallback"] = True

    # 한글 필터링
    korean = [r for r in results if is_korean(r)]
    if len(korean) >= 3:
        results = korean

    # 3) 정렬 (기본: 급상승 속도 + 총조회수 복합 점수 / 선택: views 단독)
    if sort_by == "views":
        results.sort(key=lambda r: r["views"], reverse=True)
    else:
        results.sort(key=lambda r: (r["views_per_day"] * 0.6 + r["views"] * 0.4), reverse=True)
    return results[:10]


def is_spam_video(row: Dict[str, Any]) -> bool:
    """조회수 0, 과도한 해시태그(8개 이상), 낚시 스팸 키워드 영상을 판별합니다."""
    if int(row.get("views", 0)) <= 0:
        return True
    title = row.get("title", "") or ""
    desc = row.get("description", "") or ""
    if title.count("#") >= 8:
        return True
    blob = f"{title} {desc}"
    if any(kw in blob for kw in SPAM_KEYWORDS):
        return True
    return False


def get_beauty_viral_grade(
    views: int,
    views_per_day: int,
    views_per_subscriber: Optional[float] = None,
) -> Dict[str, str]:
    """K-뷰티 쇼츠 현실화 등급 판정 (소형 채널 100회/10명=10배 왜곡 방지 포함)."""
    if views >= 100000 or (
        views >= 10000
        and views_per_subscriber is not None
        and views_per_subscriber >= 5.0
    ):
        return {"grade": "S", "label": "🔥 S등급 · 메가 바이럴"}
    if views >= 30000 or views_per_day >= 3000:
        return {"grade": "A", "label": "⚡ A등급 · 급상승"}
    if views >= 10000 or views_per_day >= 1000:
        return {"grade": "B", "label": "📈 B등급 · 초기 반응"}
    return {"grade": "C", "label": "🔍 C등급 · 참고용"}


def fetch_channel_subscribers(youtube, channel_ids: List[str]) -> Dict[str, Optional[int]]:
    """최대 50개 채널의 구독자 수를 1회 배치 조회합니다 (비공개/0명은 None)."""
    unique_ids = list(dict.fromkeys([cid for cid in channel_ids if cid]))[:50]
    if not unique_ids or not hasattr(youtube, "channels"):
        return {}
    try:
        record_youtube_units(1, action="channels.list", meta={"count": len(unique_ids)})
        resp = youtube.channels().list(
            part="statistics",
            id=",".join(unique_ids),
        ).execute()
        out: Dict[str, Optional[int]] = {}
        for item in resp.get("items", []):
            cid = item.get("id", "")
            stats = item.get("statistics", {})
            if stats.get("hiddenSubscriberCount"):
                out[cid] = None
            else:
                subs = int(stats.get("subscriberCount", 0) or 0)
                out[cid] = subs if subs > 0 else None
        return out
    except RuntimeError:
        raise
    except Exception as e:
        print(f"[KR Step1 Channel Subscribers Error] {e}")
        return {}


def _format_youtube_api_error(exc: Exception) -> str:
    """유튜브 API 오류를 마케터가 이해할 수 있는 한국어 안내 문장으로 바꿉니다."""
    raw = str(exc)
    low = raw.lower()
    if "quotaexceeded" in low or "dailylimitexceeded" in low or "quota" in low:
        return "오늘 유튜브 API 무료 조회 한도를 모두 썼어요. 매일 오후 4~5시에 초기화되니 그때 다시 시도하거나, [예시 화면 미리보기]를 이용해 보세요."
    if "keyinvalid" in low or "api key not valid" in low or "api_key_invalid" in low:
        return "유튜브 API 키가 올바르지 않아요. 왼쪽 사이드바 'API 키 설정'에서 키를 다시 확인해 주세요."
    if "accessnotconfigured" in low or "has not been used" in low:
        return "이 구글 프로젝트에서 YouTube Data API v3가 꺼져 있어요. Google Cloud 콘솔에서 사용 설정을 켜 주세요."
    return f"유튜브 데이터를 불러오지 못했어요: {raw}"


def fetch_kr_step1_shorts(
    youtube,
    path_key: str = "beauty",
    days: int = 30,
    sort_by: str = "subscriber_ratio",
    min_views: int = 5000,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """한국(KR) 뷰티 전용 1단계 계층 탐색 쇼츠 수집 (당일 캐시 재사용)."""
    node = KR_EXPLORE_TREE.get(path_key)
    if not node:
        raise ValueError(f"지원하지 않는 탐색 경로입니다: {path_key}")

    cache_key = f"{date.today()}_kr_step1_v5_{path_key}_{days}_{sort_by}"
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    now_utc = datetime.now(timezone.utc)
    published_after = recent_published_after(days=days)
    candidate_ids: List[str] = []
    last_search_err: Optional[Exception] = None
    for kw in node["keywords"][:3]:
        try:
            # 대형 뷰티 유튜버 대부분이 People & Blogs(22)로 올리고 제목에 shorts를 쓰지 않으므로
            # videoCategoryId=26 및 " shorts" 강제 접미사를 제거하고 videoDuration="short"로 순수 검색
            record_youtube_units(100, action="search.list", meta={"path_key": path_key, "q": kw, "days": days})
            sr = youtube.search().list(
                part="snippet",
                q=kw,
                type="video",
                videoDuration="short",
                order="viewCount",
                regionCode="KR",
                relevanceLanguage="ko",
                maxResults=50,
                publishedAfter=published_after,
            ).execute()
            candidate_ids += [it["id"]["videoId"] for it in sr.get("items", [])]
        except RuntimeError:
            raise
        except Exception as e2:
            last_search_err = e2
            print(f"[KR Step1 Search Error] {path_key}/{kw}: {e2}")
            low_err = str(e2).lower()
            if "quotaexceeded" in low_err or "keyinvalid" in low_err or "api key not valid" in low_err:
                break

    candidate_ids = list(dict.fromkeys(candidate_ids))
    if not candidate_ids:
        if last_search_err is not None:
            raise RuntimeError(_format_youtube_api_error(last_search_err))
        return []

    record_youtube_units(1, action="videos.list", meta={"path_key": path_key, "count": len(candidate_ids[:50])})
    det = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(candidate_ids[:50]),
    ).execute()

    raw_items = det.get("items", [])
    channel_ids = [it.get("snippet", {}).get("channelId", "") for it in raw_items]
    channel_subs = fetch_channel_subscribers(youtube, channel_ids)

    max_len = 180
    results: List[Dict[str, Any]] = []
    for item in raw_items:
        secs = iso8601_to_seconds(item.get("contentDetails", {}).get("duration", ""))
        if secs == 0 or secs > max_len:
            continue
        sn = item["snippet"]
        stats = item.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        pub_raw = sn.get("publishedAt", "")
        metrics = compute_video_metrics(views, likes, pub_raw, now_utc=now_utc)
        metrics["comment_rate"] = round((comments / max(1, views)) * 100.0, 2)
        cid = sn.get("channelId", "")
        subs = channel_subs.get(cid)
        ratio = round(views / subs, 2) if (subs and subs > 0) else None
        grade_info = get_beauty_viral_grade(views, metrics["views_per_day"], ratio)
        row = {
            "video_id": item["id"],
            "title": sn.get("title", ""),
            "description": sn.get("description", "")[:300],
            "channel_id": cid,
            "channel_title": sn.get("channelTitle", ""),
            "subscriber_count": subs,
            "views_per_subscriber": ratio,
            "viral_grade": grade_info["grade"],
            "viral_grade_label": grade_info["label"],
            "views": views,
            "likes": likes,
            "comments": comments,
            **metrics,
            "published_at": pub_raw[:10],
            "thumbnail_url": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "duration_s": secs,
            "is_short60": secs <= 60,
            "low_views_fallback": False,
            "explore_path": path_key,
        }
        if is_spam_video(row):
            continue
        results.append(row)

    high_impact = [r for r in results if r["views"] >= min_views]
    if len(high_impact) >= 5:
        results = high_impact
    else:
        for r in results:
            if r["views"] < min_views:
                r["low_views_fallback"] = True

    korean = [r for r in results if is_korean(r)]
    if len(korean) >= 3:
        results = korean

    if sort_by == "views":
        results.sort(key=lambda r: r["views"], reverse=True)
    elif sort_by == "comments":
        results.sort(key=lambda r: (r["comments"], r["views"]), reverse=True)
    elif sort_by in ("fast", "velocity"):
        results.sort(key=lambda r: (r["views_per_day"], r["views"]), reverse=True)
    else:
        # 기본: 확산력 순 (조회수 1만 이상이면서 구독자 대비 배수가 높은 영상 우선)
        results.sort(
            key=lambda r: (
                1 if (r["views"] >= 10000 and r.get("views_per_subscriber")) else 0,
                r.get("views_per_subscriber") or 0.0,
                r["views_per_day"],
                r["views"],
            ),
            reverse=True,
        )

    # 동일 제목 중복 재업로드 제거 (정렬 상위 1건만 유지)
    deduped = []
    seen_titles = set()
    for r in results:
        tkey = re.sub(r"[\s\W_]+", "", r.get("title", "")).lower()[:28]
        if tkey and tkey in seen_titles:
            continue
        if tkey:
            seen_titles.add(tkey)
        deduped.append(r)

    final_rows = deduped[:10]
    if use_cache and final_rows:
        _cache.set(cache_key, final_rows, expire=43200)
    return final_rows

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
            record_youtube_units(100, action="search_shorts", meta={"q": query, "days": days or default_days})
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
    """선택된 더랩바이블랑두 제품과 트렌드를 접목한 4단 콘티 생성 (products.json 기반)"""
    products = load_products()
    prod_info = products.get(product_name, {
        "name": product_name,
        "tagline": product_name,
        "key_features": "확인된 제품 문구 없음",
        "unverified_removed_from_v1": [],
    })
    banned = ", ".join(prod_info.get("unverified_removed_from_v1", []))

    prompt = f"""
    당신은 K-뷰티 숏폼 전문 크리에이티브 디렉터입니다.
    지금 한국 유튜브에서 터지고 있는 트렌드와 더랩바이블랑두(THE LAB by blanc doux) 제품을 접목하여
    마케터가 바로 인플루언서에게 전달하거나 직접 촬영할 수 있는 4단 숏폼 콘티를 작성하세요.

    [트렌드 정보]
    - 트렌드: {trend_title}
    - 내용: {trend_summary}

    [더랩바이블랑두 제품 정보 — 아래 확인된 문구만 사용]
    - 제품명: {prod_info['name']}
    - 요약: {prod_info['tagline']}
    - 확인된 문구: {prod_info['key_features']}
    - 금지 표현: {banned or '확인되지 않은 수치·순위·효능 표현 금지'}

    [작성 규칙]
    - hook_scene: 첫 3초 시선 강탈 훅 (구체적 행동 + 대사/자막)
    - setup_scene: 문제 제기 및 비포 공감대 (10초 이내)
    - solution_scene: 제품 특장점과 텍스처/흡수감 연출 (확인된 문구 범위 안에서만)
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
