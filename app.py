import os
import json
from datetime import date
import streamlit as st
from dotenv import load_dotenv

# 로컬 .env 파일 자동 로드
env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_file_path)

import agent_core
from langchain_core.messages import HumanMessage, AIMessage

# ── 페이지 기본 설정 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="TrendSetter Agent - K-뷰티 마케터 전용",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 커스텀 스타일링 ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #8A2BE2;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #666;
        margin-bottom: 25px;
    }
    .metric-card {
        background-color: #f8f9fc;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
    }
    .highlight-box {
        background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
        border-left: 5px solid #8A2BE2;
        padding: 16px 20px;
        border-radius: 8px;
        margin: 15px 0;
    }
    .video-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
        transition: transform 0.2s;
    }
    .video-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .badge-verified {
        background-color: #dcfce7;
        color: #166534;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ──────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_analysis" not in st.session_state:
    st.session_state.latest_analysis = ""
if "collected_videos" not in st.session_state:
    st.session_state.collected_videos = []
if "structured_report" not in st.session_state:
    st.session_state.structured_report = None

# ── 사이드바: 설정 및 필터 ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💄 K-뷰티 타겟팅 설정")

    # API 키 처리 (.env 우선, 없으면 st.secrets, 없으면 사용자 입력)
    env_yt = os.getenv("YOUTUBE_API_KEY", "")
    env_gm = os.getenv("GOOGLE_API_KEY", "")

    # Streamlit Secrets 지원
    if not env_yt and hasattr(st, "secrets") and "YOUTUBE_API_KEY" in st.secrets:
        env_yt = st.secrets["YOUTUBE_API_KEY"]
    if not env_gm and hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
        env_gm = st.secrets["GOOGLE_API_KEY"]

    with st.expander("🔑 API 키 설정 (보안 안전)", expanded=not (bool(env_yt) and bool(env_gm))):
        yt_key = st.text_input("YouTube Data API 키", value=env_yt, type="password")
        gm_key = st.text_input("Google Gemini API 키", value=env_gm, type="password")
        if env_yt and env_gm:
            st.success("✅ 시스템 API 키가 안전하게 로드되었습니다.")

    st.markdown("---")
    st.markdown("#### ⏱️ 트렌드 분석 기간")
    days_range = st.slider(
        "수집 기간 (최근 N일 이내 업로드)",
        min_value=1,
        max_value=10,
        value=7,
        help="최근 1~10일 이내에 업로드되어 급상승 중인 한국 K-뷰티 쇼츠를 필터링합니다."
    )
    if days_range <= 3:
        st.caption("🔥 **초단기 밈/바이럴**: 어제오늘 바로 뜬 급상승 트렌드 집중")
    else:
        st.caption("📈 **누적 바이럴**: 최근 1주일간 검증된 인기 K-뷰티 숏폼 집중")

    st.markdown("#### 🎯 K-뷰티 상세 키워드")
    detail_keyword = st.text_input(
        "상세 제품군 / 성분 / 고민 (선택)",
        placeholder="예: 모공 세럼, 속건조 쿠션, 쿨톤 립틴트, 진정 패드",
        help="비워두시면 K-뷰티 전체 인기 트렌드를 분석합니다."
    )

    st.markdown("#### 🏢 우리 브랜드 / 제품 정보 (선택)")
    brand_context = st.text_area(
        "우리 제품 소구점 (한 줄)",
        placeholder="예: 끈적임 없이 수분만 꽉 채워주는 저자극 어성초 진정 세럼",
        help="입력 시 트렌드 쇼츠를 접목한 브랜드 맞춤 숏폼 콘티와 카피를 추가 제안합니다."
    )

    st.markdown("---")
    model_choice = st.selectbox(
        "Gemini 모델 선택",
        options=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro"],
        index=0
    )

    if st.button("🧹 로컬 캐시 초기화"):
        agent_core.clear_cache()
        st.success("캐시가 비워졌습니다.")

# ── 메인 헤더 ────────────────────────────────────────────────────────
st.markdown('<div class="main-title">📈 TrendSetter Agent: K-Beauty</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">한국 유튜브 Shorts 트렌드 분석 & 환각 검증 숏폼 캠페인 기획 AI 에이전트</div>', unsafe_allow_html=True)

# ── 탭 레이아웃 ──────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🚀 실시간 트렌드 브리핑 & 캠페인 기획",
    "🔎 심층 탐색 & 환각 자가검증",
    "📋 Pydantic 구조화 리포트 (JSON)"
])

# ── 탭 1: 트렌드 브리핑 ──────────────────────────────────────────────
with tab1:
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run_briefing = st.button("✨ K-뷰티 트렌드 분석 시작", type="primary", use_container_width=True)

    if run_briefing:
        if not yt_key or not gm_key:
            st.error("사이드바에서 YouTube API 키와 Gemini API 키를 먼저 확인해 주세요.")
        else:
            with st.spinner("한국 유튜브 Shorts 실시간 데이터 수집 및 에이전트 분석 중... (환각 검증 파이프라인 가동)"):
                try:
                    yt_client = agent_core.build_youtube_client(yt_key)
                    agent, llm, tools = agent_core.get_kbeauty_agent(
                        youtube_client=yt_client,
                        google_api_key=gm_key,
                        model_name=model_choice,
                        days=days_range,
                        detail_keyword=detail_keyword
                    )

                    # 쿼리 프롬프트 생성
                    kw_desc = f"'{detail_keyword}' 관련" if detail_keyword.strip() else "전반적인"
                    prompt = (
                        f"최근 {days_range}일 동안 한국 유튜브에서 가장 인기 있는 {kw_desc} K-뷰티 Shorts 트렌드를 "
                        f"get_trending_shorts 도구로 수집해서 분석해줘. "
                        f"각 트렌드별 바이럴 훅(첫 3초), 타겟 고민, 브랜드 기회 점수, 캠페인 방향을 명확히 제시하고 "
                        f"마지막에 [골든타임 트렌드] 1개를 추천해줘."
                    )
                    if brand_context.strip():
                        prompt += f"\n우리 브랜드 정보: '{brand_context.strip()}'. 이 제품과 연결할 수 있는 숏폼 콘티 아이디어도 함께 제안해줘."

                    # 에이전트 실행
                    messages = [HumanMessage(content=prompt)]
                    res = agent.invoke({"messages": messages})
                    output_text = agent_core.extract_text(res["messages"][-1])

                    # 세션 저장
                    st.session_state.chat_history = res["messages"]
                    st.session_state.latest_analysis = output_text

                    # 그라운딩 데이터 검증
                    grounding = agent_core.verify_grounding(res["messages"])
                    st.session_state.collected_videos = grounding.get("collected_videos", [])

                except Exception as e:
                    st.error(f"분석 중 오류 발생: {e}")

    # 분석 결과 출력
    if st.session_state.latest_analysis:
        st.markdown("### 📊 실시간 K-뷰티 트렌드 브리핑")
        st.markdown(st.session_state.latest_analysis)

        # ── 🛡️ 환각 검증 패널 ────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🛡️ 환각 제로(Grounding) 실증 검증 패널")

        v_col1, v_col2 = st.columns([1, 1])

        with v_col1:
            st.markdown("#### 1. 에이전트 도구 호출 증빙")
            grounding = agent_core.verify_grounding(st.session_state.chat_history)
            if grounding["called_trending"]:
                st.success(f"✅ `get_trending_shorts` 실제 도구 호출 확인 (호출 {grounding['trending_count']}회) — 실존 데이터 수신 완료")
            else:
                st.warning("⚠️ 도구 호출 미확인 — 모델 사전 지식 기반 답변 가능성 있음")

            citations = agent_core.verify_citations(st.session_state.chat_history, st.session_state.latest_analysis)
            if citations["is_valid"]:
                st.success(f"✅ 인용된 영상 ID 100% 실존 일치 (인용: {len(citations['cited_ids'])}개 / 허위 ID 0개)")
            elif citations["ungrounded_ids"]:
                st.error(f"❌ 도구 결과에 없는 ID 인용 적발: {citations['ungrounded_ids']}")
            else:
                st.info("ℹ️ 본문에 명시된 video_id 없음")

        with v_col2:
            st.markdown("#### 2. 데이터 수집 스펙 요약")
            st.markdown(f"- **분석 타겟**: K-뷰티 버티컬 (한국어 영상 필터링 적용)")
            st.markdown(f"- **적용 기간**: 최근 {days_range}일 이내 업로드 영상")
            st.markdown(f"- **상세 키워드**: `{detail_keyword or '전체 K-뷰티'}`")
            st.markdown(f"- **수집된 실존 Shorts**: 총 {len(st.session_state.collected_videos)}편")

        # ── 수집된 실제 유튜브 영상 갤러리 ────────────────────────────
        if st.session_state.collected_videos:
            st.markdown("#### 🎬 근거가 된 실제 유튜브 Shorts 영상 목록 (클릭 시 원본 재생)")
            cols = st.columns(3)
            for idx, vid in enumerate(st.session_state.collected_videos):
                col = cols[idx % 3]
                with col:
                    thumb = vid.get("thumbnail_url")
                    vid_id = vid.get("video_id")
                    title = vid.get("title", "제목 없음")
                    views = vid.get("views", 0)
                    ch = vid.get("channel_title", "")
                    pub = (vid.get("published_at") or "")[:10]

                    st.markdown(f"""
                    <div class="video-card">
                        <a href="https://www.youtube.com/watch?v={vid_id}" target="_blank">
                            <img src="{thumb}" style="width:100%; border-radius:8px; aspect-ratio:16/9; object-fit:cover;" />
                        </a>
                        <div style="font-weight:bold; font-size:0.95rem; margin-top:8px; line-height:1.3;">
                            <a href="https://www.youtube.com/watch?v={vid_id}" target="_blank" style="text-decoration:none; color:#1C1730;">
                                {title[:40]}...
                            </a>
                        </div>
                        <div style="font-size:0.8rem; color:#6b7280; margin-top:4px;">
                            📺 {ch} | 📅 {pub}
                        </div>
                        <div style="font-size:0.85rem; color:#8A2BE2; font-weight:bold; margin-top:2px;">
                            👀 조회수 {views:,}회 (ID: <code>{vid_id}</code>)
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

# ── 탭 2: 심층 탐색 ──────────────────────────────────────────────────
with tab2:
    st.markdown("### 🔍 특정 트렌드 심층 탐색 (Deep Search)")
    st.markdown("기존 트렌드 목록 외에 특정 키워드나 제품으로 `search_shorts` 도구를 강제 호출하여 심층 탐색합니다.")

    deep_query = st.text_input("심층 탐색 키워드 입력", placeholder="예: 모델링팩 모공 수축, 탕후루 립광택")
    if st.button("🔎 심층 탐색 실행"):
        if not yt_key or not gm_key:
            st.error("사이드바에서 API 키를 확인해 주세요.")
        elif not deep_query.strip():
            st.warning("탐색할 키워드를 입력해 주세요.")
        else:
            with st.spinner("심층 검색 도구 실행 중..."):
                try:
                    yt_client = agent_core.build_youtube_client(yt_key)
                    agent, llm, tools = agent_core.get_kbeauty_agent(
                        youtube_client=yt_client,
                        google_api_key=gm_key,
                        model_name=model_choice,
                        days=days_range
                    )

                    deep_prompt = (
                        f"'{deep_query}' 키워드로 search_shorts 도구를 반드시 호출해서 실제 유튜브 영상을 더 찾아줘. "
                        f"반드시 도구가 반환한 제목과 video_id를 그대로 인용해서 마케팅 기회를 심층 분석해줘. "
                        f"도구 결과에 없는 ID는 절대 만들어내지 마."
                    )

                    messages = st.session_state.chat_history + [HumanMessage(content=deep_prompt)]
                    res = agent.invoke({"messages": messages})
                    output_text = agent_core.extract_text(res["messages"][-1])

                    st.session_state.chat_history = res["messages"]
                    st.markdown("#### 📑 심층 분석 결과")
                    st.markdown(output_text)

                    # 그라운딩 자동 점검
                    citations = agent_core.verify_citations(res["messages"], output_text)
                    st.markdown("---")
                    st.markdown("#### 🛡️ 인용 ID 일치율 자가점검")
                    if citations["is_valid"]:
                        st.success(f"✅ 인용된 모든 video_id가 실제 검색 결과에 존재합니다: {citations['cited_ids']}")
                    elif citations["ungrounded_ids"]:
                        st.error(f"❌ 가짜 ID 인용 감지됨 (환각): {citations['ungrounded_ids']}")
                    else:
                        st.info("ℹ️ 인용된 video_id가 없습니다.")

                except Exception as e:
                    st.error(f"심층 탐색 중 오류 발생: {e}")

# ── 탭 3: Pydantic 구조화 리포트 ──────────────────────────────────────
with tab3:
    st.markdown("### 📋 Pydantic 구조화 리포트 (TrendReport)")
    st.markdown("자유 텍스트 분석 결과를 **Pydantic 스키마 기반 JSON**으로 변환하여 대시보드나 DB에 즉시 적재할 수 있도록 합니다.")

    if not st.session_state.latest_analysis:
        st.info("먼저 탭 1에서 'K-뷰티 트렌드 분석'을 실행해 주세요.")
    else:
        if st.button("⚙️ JSON 구조화 리포트 생성"):
            with st.spinner("Pydantic 스키마로 구조화 중..."):
                try:
                    yt_client = agent_core.build_youtube_client(yt_key)
                    _, llm, _ = agent_core.get_kbeauty_agent(
                        youtube_client=yt_client,
                        google_api_key=gm_key,
                        model_name=model_choice
                    )

                    structured_llm = llm.with_structured_output(agent_core.TrendReport)
                    prompt_text = f"""
                    아래는 오늘({date.today()}) 분석한 한국 유튜브 Shorts K-뷰티 트렌드 결과입니다.
                    이를 TrendReport 형식으로 구조화하세요.

                    규칙:
                    - keyword 필드: "{detail_keyword or '전체 K-뷰티'}"
                    - days_range 필드: {days_range}
                    - 데이터에 없는 내용을 지어내지 마세요.

                    분석 내용:
                    {st.session_state.latest_analysis}
                    """
                    report = structured_llm.invoke(prompt_text)
                    st.session_state.structured_report = report.model_dump()
                    st.success("✅ 구조화 완료!")

                except Exception as e:
                    st.error(f"구조화 변환 실패: {e}")

        if st.session_state.structured_report:
            json_str = json.dumps(st.session_state.structured_report, indent=2, ensure_ascii=False)
            st.json(st.session_state.structured_report)

            st.download_button(
                label="📥 TrendReport JSON 다운로드",
                data=json_str,
                file_name=f"kbeauty_trend_report_{date.today()}.json",
                mime="application/json"
            )
