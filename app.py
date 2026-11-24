"""app.py — K-Beauty TrendSetter Pro (B2B v2 Edition)
Design System v2 기반 5단 B2B 의사결정 대시보드 (pipeline.py 단일 데이터 계약 연동)
"""
import html
import json
import os
from datetime import date
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import agent_core
import pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

st.set_page_config(
    page_title="K-Beauty TrendSetter Pro (B2B)",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System v2 CSS ──────────────────────────────────────────────
st.markdown(
    """
<style>
:root {
  --purple: #6C2BD9;
  --purple-dark: #4C1D95;
  --purple-soft: #F3EEFD;
  --gold: #BF8A12;
  --gold-soft: #FFFDF5;
  --ink: #1C1730;
  --ink-secondary: #374151;
  --muted: #6B7280;
  --bg: #FAF9FE;
  --surface: #FFFFFF;
  --surface-subtle: #FBF9FF;
  --line: #ECE9F5;
  --line-strong: #D8D3E8;
  --go: #0F766E;
  --go-soft: #E6F6F4;
  --warn: #B45309;
  --warn-soft: #FEF3C7;
  --drop: #4B5563;
  --drop-soft: #F3F4F6;
  --danger: #B91C1C;
  --danger-soft: #FEF2F2;
  --hot: #C2410C;
  --hot-soft: #FFF7ED;
}
.stApp { background-color: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; }
.block-container { max-width: 1120px; padding-top: 1.5rem; padding-bottom: 3rem; }
.tnum { font-variant-numeric: tabular-nums; }

/* Header */
.hero-bar {
  display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 12px;
  padding-bottom: 14px; border-bottom: 1px solid var(--line); margin-bottom: 14px;
}
.hero-title { font-size: 1.8rem; font-weight: 800; color: var(--ink); margin: 0; line-height: 1.25; }
.hero-sub { font-size: 0.9rem; color: var(--muted); margin-top: 4px; }
.mode-pill {
  display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700;
  background: var(--purple-soft); color: var(--purple-dark); border: 1px solid #DDD6FE;
}
.mode-pill.demo { background: var(--warn-soft); color: var(--warn); border-color: #FCD34D; }

/* Global Alert Banners */
.alert-banner {
  padding: 11px 16px; border-radius: 10px; font-size: 0.86rem; font-weight: 600; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.alert-warn { background: var(--warn-soft); color: var(--warn); border: 1px solid #F59E0B; border-left: 4px solid var(--warn); }
.alert-danger { background: var(--danger-soft); color: var(--danger); border: 1px solid #FCA5A5; border-left: 4px solid var(--danger); }
.alert-info { background: var(--drop-soft); color: var(--drop); border: 1px solid #D1D5DB; }

/* Section 1: Executive Summary Strip */
.kpi-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px;
}
.kpi-card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
  padding: 14px 16px; box-shadow: 0 1px 3px rgba(28,23,48,0.05);
}
.kpi-label { font-size: 0.78rem; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.kpi-val { font-size: 1.45rem; font-weight: 800; color: var(--ink); line-height: 1.2; font-variant-numeric: tabular-nums; }
.kpi-sub { font-size: 0.78rem; color: var(--muted); margin-top: 5px; font-variant-numeric: tabular-nums; }
.dist-pills { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 2px; }
.pill { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 999px; font-size: 0.76rem; font-weight: 700; }
.pill-go { background: var(--go-soft); color: var(--go); }
.pill-warn { background: var(--warn-soft); color: var(--warn); }
.pill-drop { background: var(--drop-soft); color: var(--drop); }
.pill-purple { background: var(--purple-soft); color: var(--purple); }
.pill-gold { background: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }
.pill-hot { background: var(--hot-soft); color: var(--hot); }

/* Section 2: Market Patterns Box */
.insight-box {
  background: linear-gradient(135deg, #F6F2FF 0%, #FFFFFF 100%);
  border: 1px solid #E0D8F5; border-left: 5px solid var(--purple);
  border-radius: 14px; padding: 18px 22px; margin-bottom: 22px;
}
.insight-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.insight-title { font-size: 1.08rem; font-weight: 800; color: var(--purple-dark); margin: 0; }
.pattern-row { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; font-size: 0.92rem; color: var(--ink-secondary); line-height: 1.5; }
.pattern-num {
  min-width: 22px; height: 22px; border-radius: 999px; background: var(--purple); color: #FFF;
  font-size: 0.76rem; font-weight: 800; display: inline-flex; align-items: center; justify-content: center; margin-top: 2px;
}

/* Section 3: Go Campaign Card */
.sec-heading { font-size: 1.15rem; font-weight: 800; color: var(--ink); margin: 18px 0 12px 0; }
.tcard {
  background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
  padding: 20px 22px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(28,23,48,0.05);
}
.tcard.gold { border: 2px solid var(--gold); background: var(--gold-soft); }
.tcard-top { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.badge-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.dots { font-size: 0.88rem; font-weight: 800; letter-spacing: 1px; font-variant-numeric: tabular-nums; }
.tcard-title { font-size: 1.12rem; font-weight: 800; color: var(--ink); margin: 6px 0 8px 0; line-height: 1.35; }
.tcard-reason { font-size: 0.91rem; color: var(--ink-secondary); line-height: 1.55; margin-bottom: 8px; }
.claim-chip {
  display: inline-block; background: var(--go-soft); color: var(--go); border-radius: 8px;
  padding: 4px 10px; font-size: 0.82rem; font-weight: 700; margin-bottom: 12px;
}

/* Quote Box */
.quote-box {
  background: #F4FBF9; border-left: 3px solid var(--go); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 12px;
}
.quote-meta { display: flex; justify-content: space-between; font-size: 0.76rem; font-weight: 700; color: var(--go); margin-bottom: 4px; }
.quote-text { font-size: 0.9rem; font-weight: 600; color: var(--ink); line-height: 1.5; }

/* 1:1 Evidence Video Strip */
.evid-item {
  display: flex; align-items: center; gap: 12px; background: var(--surface-subtle);
  border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; margin-bottom: 14px;
}
.evid-thumb { width: 96px; height: 54px; border-radius: 6px; object-fit: cover; flex-shrink: 0; background: #E5E7EB; }
.evid-body { flex: 1; min-width: 0; }
.evid-title { font-size: 0.88rem; font-weight: 700; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.evid-meta { font-size: 0.78rem; color: var(--muted); margin-top: 4px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-variant-numeric: tabular-nums; }
.evid-link {
  padding: 6px 12px; border-radius: 8px; border: 1px solid var(--line-strong);
  font-size: 0.78rem; font-weight: 700; color: var(--purple-dark); text-decoration: none; white-space: nowrap;
  background: #FFF;
}
.evid-link:hover { background: var(--purple-soft); }

/* 4-Stage Storyboard 2x2 */
.sb-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 10px; }
.sb-cell {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
}
.sb-label { font-size: 0.78rem; font-weight: 800; color: var(--purple-dark); margin-bottom: 5px; }
.sb-text { font-size: 0.88rem; color: var(--ink-secondary); line-height: 1.5; }
.note-strip {
  background: #FFF8F8; border: 1px solid #FECACA; border-radius: 10px;
  padding: 9px 12px; font-size: 0.81rem; color: var(--ink-secondary); line-height: 1.45;
}

/* Pivot Compact Card */
.pivot-card {
  display: flex; align-items: center; gap: 12px; background: var(--surface);
  border: 1px solid var(--line); border-left: 4px solid var(--warn); border-radius: 12px;
  padding: 12px 14px; margin-bottom: 10px;
}
.pivot-thumb { width: 72px; height: 40px; border-radius: 6px; object-fit: cover; flex-shrink: 0; background: #E5E7EB; }

/* Tables */
.b2b-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; background: #FFF; border-radius: 10px; overflow: hidden; }
.b2b-table th { background: var(--surface-subtle); color: var(--muted); font-weight: 700; text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); }
.b2b-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); color: var(--ink-secondary); vertical-align: middle; font-variant-numeric: tabular-nums; }
.b2b-table a { color: var(--purple-dark); font-weight: 600; text-decoration: none; }
.empty-box {
  border: 1px dashed var(--line-strong); border-radius: 14px; padding: 24px;
  text-align: center; color: var(--muted); background: #FFF; font-size: 0.92rem;
}

@media (max-width: 768px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .sb-grid { grid-template-columns: 1fr; }
  .evid-item { flex-direction: column; align-items: flex-start; }
}
</style>
""",
    unsafe_allow_html=True,
)


def _esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=True)


def _dot_gauge(score: int, decision: str) -> str:
    s = max(1, min(5, int(score)))
    filled = "●" * s + "○" * (5 - s)
    color = {
        "Go": "var(--gold)" if s == 5 else "var(--go)",
        "Pivot": "var(--warn)",
        "Drop": "var(--drop)",
    }.get(decision, "var(--muted)")
    return f'<span class="dots" style="color:{color};">{filled} {s}점</span>'


def _copy_buttons_widget(internal_md: str, dm_clean_md: str, needs_review: bool, key_suffix: str):
    """Streamlit용 원클릭 2종 복사 버튼 (클립보드 API + textarea 폴백 + 검수 경고 confirm)"""
    rep_js = json.dumps(internal_md).replace("</", "<\\/")
    dm_js = json.dumps(dm_clean_md).replace("</", "<\\/")
    dm_label = "⚠️ 검수 후 DM 복사" if needs_review else "💌 인플루언서 DM 복사 (깨끗한 본문)"
    dm_cls = "btn-danger" if needs_review else "btn-primary"
    confirm_js = "if(!confirm('검수 필요 항목이 포함되어 있습니다. 위반 내용을 확인 후 복사할까요?')) return;" if needs_review else ""
    components.html(
        f"""
        <style>
          body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Pretendard",sans-serif; }}
          .bar {{ display:flex; gap:10px; flex-wrap:wrap; }}
          button {{
            flex:1; min-width:200px; padding:10px 14px; border-radius:10px; font-size:13.5px; font-weight:700;
            cursor:pointer; transition:all .15s ease;
          }}
          .btn-sec {{ background:#F3EEFD; color:#4C1D95; border:1px solid #C4B5FD; }}
          .btn-sec:hover {{ background:#EDE9FE; }}
          .btn-primary {{ background:#6C2BD9; color:#FFF; border:1px solid #6C2BD9; }}
          .btn-primary:hover {{ background:#4C1D95; }}
          .btn-danger {{ background:#FEF2F2; color:#B91C1C; border:1.5px solid #B91C1C; }}
          .btn-danger:hover {{ background:#FEE2E2; }}
        </style>
        <div class="bar">
          <button id="b_rep_{key_suffix}" class="btn-sec" onclick="copyText_{key_suffix}(REP_{key_suffix}, 'b_rep_{key_suffix}', '📋 팀장/슬랙 보고 복사', false)">📋 팀장/슬랙 보고 복사</button>
          <button id="b_dm_{key_suffix}" class="{dm_cls}" onclick="copyText_{key_suffix}(DM_{key_suffix}, 'b_dm_{key_suffix}', '{dm_label}', true)">{dm_label}</button>
        </div>
        <script>
          const REP_{key_suffix} = {rep_js};
          const DM_{key_suffix} = {dm_js};
          function copyText_{key_suffix}(txt, btnId, origLabel, isDm) {{
            if (isDm) {{ {confirm_js} }}
            const btn = document.getElementById(btnId);
            const done = () => {{
              btn.textContent = "✅ 클립보드에 복사되었습니다!";
              setTimeout(() => {{ btn.textContent = origLabel; }}, 2000);
            }};
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              navigator.clipboard.writeText(txt).then(done).catch(() => fallbackCopy(txt, done));
            }} else {{
              fallbackCopy(txt, done);
            }}
          }}
          function fallbackCopy(txt, cb) {{
            const ta = document.createElement("textarea");
            ta.value = txt;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            try {{ document.execCommand("copy"); }} catch (e) {{}}
            document.body.removeChild(ta);
            cb();
          }}
        </script>
        """,
        height=54,
    )


def build_offline_rehearsal_result(product_name: str, days_range: int = 30) -> Dict[str, Any]:
    """qa/run_latest.json이 있으면 로드하고, 없으면 오프라인 골든셋 기반 리허설 결과를 생성합니다 (쿼터 0)."""
    latest_path = os.path.join(BASE_DIR, "qa", "run_latest.json")
    if os.path.exists(latest_path):
        try:
            with open(latest_path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("product") == product_name:
                data["_mode"] = "snapshot_file"
                return data
        except Exception:
            pass

    products = pipeline.load_products()
    prod = products[product_name]
    golden_path = os.path.join(BASE_DIR, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        gs_items = json.load(f)["items"]

    # 골든셋 중 기초/스킨케어 4건 + 대표 색조 6건 조합(jfsweQpxqsY 포함)
    skin_items = [it for it in gs_items if it["expected_domain"] == "기초/스킨케어"]
    color_items = [it for it in gs_items if it["expected_domain"] != "기초/스킨케어"][:6]
    selected = skin_items + color_items
    videos = [pipeline._ensure_video_metrics(it) for it in selected]
    for v in videos:
        v.setdefault("thumbnail_url", f"https://i.ytimg.com/vi/{v['video_id']}/mqdefault.jpg")

    raw_facts = [pipeline.Fact(video_id=it["video_id"], **it["sample_fact"]) for it in selected]
    facts = pipeline.audit_facts(raw_facts, videos)

    claims = prod["verified_claims"]
    raw_js = []
    for it in selected:
        vid = it["video_id"]
        if it["expected_domain"] == "기초/스킨케어":
            if it["text_source"] == "caption":
                raw_js.append(pipeline.Judgement(
                    video_id=vid, decision="Go", score=5 if vid == "brKNpouibqo" else 4,
                    reason=f"실제 자막 기반 스킨케어 포맷이 '{product_name}'의 확인된 소구 포인트와 직접 연결됨.",
                    linked_claim=claims[0],
                ))
            else:
                raw_js.append(pipeline.Judgement(
                    video_id=vid, decision="Pivot", score=3,
                    reason="기초 스킨케어 연관성은 있으나 자막 미확인 상태로 직접 시청 검토 필요.",
                    linked_claim=claims[0],
                ))
        else:
            raw_js.append(pipeline.Judgement(
                video_id=vid, decision="Drop", score=1,
                reason="색조/메이크업 영역으로 기초 스킨케어 제품과 부적합.",
                linked_claim="",
            ))
    judgements = pipeline.apply_judgement_rules(raw_js, facts, prod)

    go_items = [j for j in judgements if j["decision"] == "Go"][:3]
    briefs = []
    for g in go_items:
        vid = g["video_id"]
        f_obj = next(x for x in facts if x["video_id"] == vid)
        sb = pipeline.Storyboard(
            video_id=vid,
            hook=f"첫 3초: \"{f_obj['hook_quote'] or f_obj['what_happens']}\" 자막과 함께 제품 제형 클로즈업",
            before="세안 후 속건조·피부 당김이 느껴지는 일상 스킨케어 비포 컷",
            product_moment=f"{product_name} — {pipeline._clean_claim_for_creator(claims[0])} 중심으로 자연스럽게 사용 시연",
            cta="프로필 링크 또는 올리브영에서 데일리 루틴 제품 확인해보세요",
            creator_note="확인되지 않은 순위·즉각 효과·과대광고 수치 표현 금지, 공식 확인 문구 범위 내에서만 소개",
        )
        viols = pipeline._brief_violations(sb, prod)
        briefs.append({**sb.model_dump(), "violations": viols, "needs_review": bool(viols)})

    stats = {
        "videos": len(videos),
        "transcript_caption": sum(1 for v in videos if v["text_source"] == "caption"),
        "facts": len(facts),
        "evidence_verified": sum(1 for f in facts if f["evidence_ok"]),
        "go": sum(1 for j in judgements if j["decision"] == "Go"),
        "pivot": sum(1 for j in judgements if j["decision"] == "Pivot"),
        "drop": sum(1 for j in judgements if j["decision"] == "Drop"),
        "briefs": len(briefs),
        "briefs_need_review": sum(1 for b in briefs if b["needs_review"]),
    }
    matrix = pipeline.build_multi_product_matrix(
        videos, facts, products=products,
        primary_product=product_name, primary_judgements=judgements,
    )
    res: Dict[str, Any] = {
        "product": product_name,
        "report_date": date.today().isoformat(),
        "days_range": days_range,
        "videos": videos,
        "facts": facts,
        "market_patterns": [
            "전성분 함량(ppm)과 보습 핵심 성분을 20초 내외로 팩트체크하는 실험·리스트형 쇼츠 반응이 높음.",
            "푸석한 피부의 데일리 수분 케어 및 메이크업 전 기초 루틴 포맷이 꾸준한 수요를 형성.",
            "색조 믹싱·발색 쇼츠 비중이 높아 기초 브랜드 캠페인 기획 시 영역 필터링(Drop)이 필수적임.",
        ],
        "judgements": judgements,
        "briefs": briefs,
        "multi_product_matrix": matrix,
        "stats": stats,
        "product_confidence": prod.get("confidence", "medium"),
        "_mode": "offline_rehearsal",
    }
    res.update(pipeline.format_copyable_outputs(res))
    return res


# ── Sidebar Controls ──────────────────────────────────────────────────
products_map = pipeline.load_products()
product_names = list(products_map.keys())

with st.sidebar:
    st.markdown("### ⚙️ B2B 분석 설정")
    yt_key = st.text_input("YouTube API Key", value=os.getenv("YOUTUBE_API_KEY", ""), type="password")
    gg_key = st.text_input("Google Gemini API Key", value=os.getenv("GOOGLE_API_KEY", ""), type="password")

    selected_product = st.selectbox("대상 브랜드 제품 (products.json)", product_names, index=0)
    days_range = st.select_slider("수집 기간 (최근 N일)", options=[7, 14, 30], value=30,
                                  help="7/14/30일 실측 비교 지원 (기본 30일)")
    sort_choice = st.radio(
        "수집 정렬 기준",
        ["velocity", "views"],
        format_func=lambda x: "🔥 일평균 상승속도 (velocity)" if x == "velocity" else "👀 총 조회수 (views)",
    )
    detail_kw = st.text_input("추가 키워드 (선택)", placeholder="비워두면 기초 스킨케어 앵커 사용")
    model_name = st.selectbox("Gemini 무료 모델", ["gemini-2.5-flash-lite", "gemini-flash-latest"], index=0)

    used_u = agent_core.get_used_youtube_units()
    st.caption(f"📊 YouTube API 누적 사용량: **{used_u:,} / {agent_core.YOUTUBE_UNIT_LIMIT:,} 유닛**")
    st.progress(min(1.0, used_u / max(1, agent_core.YOUTUBE_UNIT_LIMIT)))

    st.markdown("---")
    run_live = st.button("🚀 실시간 트렌드 분석 실행", type="primary", use_container_width=True)
    run_demo = st.button("🧪 스냅샷/리허설 보기 (쿼터 0)", use_container_width=True)

    st.markdown("---")
    flash_msg = st.session_state.pop("onboarding_flash", None)
    with st.expander(
        "➕ 자사 제품 추가 / 상세페이지 원문으로 신뢰도 승격 (medium → high)",
        expanded=bool(flash_msg),
    ):
        if flash_msg:
            if flash_msg.get("level") == "success":
                st.success(flash_msg["message"])
            else:
                st.warning(flash_msg["message"])
            if flash_msg.get("warnings"):
                st.warning("🚫 격리된 금지 표현:\n- " + "\n- ".join(flash_msg["warnings"]))

        ob_mode = st.radio("등록 모드", ["기존 제품 신뢰도 승격", "신규 SKU 등록"], horizontal=True, key="ob_mode")
        if ob_mode == "기존 제품 신뢰도 승격":
            ob_name = st.selectbox("승격 대상 제품", product_names, key="ob_existing_name")
            ex_info = products_map.get(ob_name, {})
            default_claims = "\n".join(ex_info.get("verified_claims", []))
            default_fit = ", ".join(ex_info.get("fit_territory", []))
            default_nonfit = ", ".join(ex_info.get("non_fit_territory", []))
        else:
            ob_name = st.text_input("신규 제품명", placeholder="예: 올리고 히알루론산 카밍 크림", key="ob_new_name")
            default_claims, default_fit, default_nonfit = "", "속건조, 보습, 진정", "색조 메이크업, 헤어/바디"

        ob_claims = st.text_area(
            "공식 상세페이지 확인 문구 (줄바꿈 구분)",
            value=default_claims,
            height=110,
            key="ob_claims",
            help="공식 상세페이지 원문에서 확인된 성분·제형·사용법 문구만 줄바꿈으로 입력하세요.",
        )
        ob_fit = st.text_input("적합 영역 (쉼표 구분)", value=default_fit, key="ob_fit")
        ob_nonfit = st.text_input("부적합 영역 (쉼표 구분)", value=default_nonfit, key="ob_nonfit")
        ob_url = st.text_input("공식 상세페이지 URL (선택)", placeholder="https://blancdoux.com/...", key="ob_url")

        if st.button("💾 저장 및 신뢰도 high 승격", use_container_width=True, key="ob_save_btn"):
            try:
                saved = pipeline.upsert_product_from_text(
                    name=ob_name,
                    raw_claims_text=ob_claims,
                    fit_territory_csv=ob_fit,
                    non_fit_territory_csv=ob_nonfit,
                    source_url=ob_url,
                    save_to_file=True,
                )
                conf_after = saved["entry"]["confidence"]
                if saved.get("rejected_claims"):
                    st.session_state["onboarding_flash"] = {
                        "level": "warning",
                        "message": f"'{saved['product_name']}' 저장 완료 — 금지어 {len(saved['rejected_claims'])}건이 격리되어 confidence={conf_after} 유지됩니다.",
                        "warnings": saved["warnings"],
                    }
                else:
                    st.session_state["onboarding_flash"] = {
                        "level": "success",
                        "message": f"'{saved['product_name']}' 저장 완료 (confidence={conf_after} 승격)!",
                        "warnings": [],
                    }
                st.session_state["b2b_result"] = build_offline_rehearsal_result(saved["product_name"], days_range=days_range)
                st.session_state["is_rehearsal"] = True
                st.session_state["rehearsal_product"] = saved["product_name"]
                st.rerun()
            except Exception as e:
                st.error(f"저장 거부: {e}")

if "b2b_result" not in st.session_state:
    st.session_state["b2b_result"] = build_offline_rehearsal_result(selected_product, days_range=days_range)
    st.session_state["is_rehearsal"] = True
    st.session_state["rehearsal_product"] = selected_product
elif st.session_state.get("is_rehearsal") and st.session_state.get("rehearsal_product") != selected_product:
    st.session_state["b2b_result"] = build_offline_rehearsal_result(selected_product, days_range=days_range)
    st.session_state["rehearsal_product"] = selected_product

if run_demo:
    st.session_state["b2b_result"] = build_offline_rehearsal_result(selected_product, days_range=days_range)
    st.session_state["is_rehearsal"] = True
    st.session_state["rehearsal_product"] = selected_product

if run_live:
    if not yt_key or not gg_key:
        st.error("실시간 분석에는 YouTube API Key와 Google Gemini API Key가 모두 필요합니다.")
    else:
        try:
            with st.spinner("1/2. 한국 K-뷰티 쇼츠 클리핑 및 바이럴 지표 계산 중..."):
                yt_client = agent_core.build_youtube_client(yt_key)
                vids = agent_core.fetch_mega_kbeauty_shorts(
                    yt_client, detail_keyword=detail_kw, days=days_range, sort_by=sort_choice
                )
            if not vids:
                st.warning("수집된 쇼츠가 없습니다. 기간을 늘리거나 키워드를 비워보세요.")
            else:
                with st.spinner("2/2. 4단계 B2B 파이프라인(팩트 추출 → Go/Pivot/Drop 판정 → 4단 콘티 → 법무 감사) 실행 중..."):
                    res = pipeline.run_pipeline(
                        vids, selected_product, api_key=gg_key, model=model_name, days_range=days_range
                    )
                    res["_mode"] = "live"
                    st.session_state["b2b_result"] = res
                    st.session_state["is_rehearsal"] = False
                    st.success("분석이 완료되었습니다!")
        except RuntimeError as e:
            st.error(f"예산 가드 차단: {e}")
        except Exception as e:
            st.error(f"실행 중 오류가 발생했습니다: {e}")

# ── Main 5-Tier B2B Dashboard ─────────────────────────────────────────
res = st.session_state["b2b_result"]
product_name = res.get("product", selected_product)
videos = [pipeline._ensure_video_metrics(v) for v in res.get("videos", [])]
facts = res.get("facts", [])
judgements = res.get("judgements", [])
briefs = res.get("briefs", [])
stats = res.get("stats", {})
market_patterns = res.get("market_patterns", [])
report_date = res.get("report_date", date.today().isoformat())
res_days = res.get("days_range") or days_range
confidence = res.get("product_confidence", "unknown")
mode = res.get("_mode", "live")

v_by_id = {v["video_id"]: v for v in videos}
f_by_id = {f["video_id"]: f for f in facts}
b_by_id = {b["video_id"]: b for b in briefs}
j_by_id = {j["video_id"]: j for j in judgements}

# Header
mode_badge = (
    '<span class="mode-pill demo">🧪 스냅샷/리허설 모드 (API 쿼터 0)</span>'
    if mode != "live"
    else '<span class="mode-pill">🟢 LIVE 분석 결과</span>'
)
st.markdown(
    f"""
    <div class="hero-bar">
      <div>
        <div class="hero-title">💄 K-Beauty TrendSetter Pro</div>
        <div class="hero-sub">대상 제품: <b>{_esc(product_name)}</b> · 기준일: {_esc(report_date)} · 최근 {int(res_days)}일</div>
      </div>
      <div>{mode_badge}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Global Zero-Hiding Banners
if confidence != "high":
    st.markdown(
        f'<div class="alert-banner alert-warn">⚠️ <b>[제품 정보 확인 필요]</b> 현재 제품 문구는 요약 기반(신뢰도: {_esc(confidence)})입니다. 최종 광고·시딩 집행 전 공식 상세페이지 원문 및 임상 시험 조건을 반드시 확인하세요.</div>',
        unsafe_allow_html=True,
    )
if any(v.get("low_views_fallback") for v in videos):
    st.markdown(
        '<div class="alert-banner alert-info">ℹ️ 저유입 기준 완화 포함: 최소 조회수 기준을 넘는 영상이 부족해 일부 저유입 영상이 포함되었습니다.</div>',
        unsafe_allow_html=True,
    )

# Section 1: Executive Summary Strip (4-Column KPI)
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

st.markdown(
    f"""
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">🎬 클리핑 쇼츠</div>
        <div class="kpi-val">{total_v}건</div>
        <div class="kpi-sub">자막 확보 {cap_v}건 ({cap_pct}%)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">👀 평균 조회수</div>
        <div class="kpi-val">{avg_views:,}회</div>
        <div class="kpi-sub">평균 좋아요율 {avg_lr:.2f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">🔥 최고 상승속도</div>
        <div class="kpi-val">{max_vpd:,}회/일</div>
        <div class="kpi-sub">최근 {int(res_days)}일 급상승 1위 기준</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">📊 판정 분포 (합계 {len(go_items)+len(pivot_items)+len(drop_items)}건)</div>
        <div class="dist-pills">
          <span class="pill pill-go">🎯 Go {len(go_items)}</span>
          <span class="pill pill-warn">⚠️ Pivot {len(pivot_items)}</span>
          <span class="pill pill-drop">❌ Drop {len(drop_items)}</span>
        </div>
        <div class="kpi-sub">억지 연결 차단 완료 ({len(drop_items)}건 자동 필터)</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Section 2 (P1): Market Patterns Box
pat_html = "".join(
    f'<div class="pattern-row"><span class="pattern-num">{i}</span><div>{_esc(p)}</div></div>'
    for i, p in enumerate(market_patterns, 1)
) or '<div class="pattern-row">추출된 공통 시장 패턴이 없습니다.</div>'

st.markdown(
    f"""
    <div class="insight-box">
      <div class="insight-head">
        <div class="insight-title">🧭 이번 주 K-뷰티 시장 관통 패턴</div>
        <span class="pill pill-purple">브랜드 편향 0% · 실제 자막 기반</span>
      </div>
      {pat_html}
    </div>
    """,
    unsafe_allow_html=True,
)

# Section 2-2 (B2B-08): Multi-Product Triage Matrix
matrix = res.get("multi_product_matrix")
if not matrix and videos and facts:
    matrix = pipeline.build_multi_product_matrix(
        videos, facts, products=products_map,
        primary_product=product_name, primary_judgements=judgements,
    )

SHORT_PROD_LABELS = {
    "올리고 히알루론산 딥 토너": "딥 토너",
    "그린 플라보노이드 2.5 패드": "그린 2.5 패드",
    "올리고 히알루론산 워터리 스킨 마스크": "워터리 마스크",
}

if matrix and matrix.get("rows"):
    rec_p = matrix.get("recommended_product")
    rec_reason = matrix.get("recommendation_reason", "")
    if rec_p:
        rec_banner = (
            f'<div class="alert-banner" style="background:var(--go-soft);color:var(--go);border:1px solid #99F6E4;border-left:4px solid var(--go);">'
            f'🏆 <b>오늘의 추천 주력 제품:</b> {_esc(rec_reason)}</div>'
        )
    else:
        rec_banner = (
            f'<div class="alert-banner alert-warn">'
            f'⚠️ <b>오늘은 억지 집행 금지 — 전원 보류/테스트 권장</b> ({_esc(rec_reason)})</div>'
        )

    m_prods = matrix.get("products", [])
    th_prods = "".join(f"<th>{_esc(SHORT_PROD_LABELS.get(pn, pn))}</th>" for pn in m_prods)
    m_rows_html = []
    for row in matrix["rows"]:
        vid = row["video_id"]
        cells_html = []
        for pn in m_prods:
            c = row["cells"].get(pn, {"decision": "Drop", "score": 1})
            dec = c["decision"]
            sc = c["score"]
            p_cls = "pill-go" if dec == "Go" else "pill-warn" if dec == "Pivot" else "pill-drop"
            ico = "🎯" if dec == "Go" else "⚠️" if dec == "Pivot" else "❌"
            cells_html.append(f'<td><span class="pill {p_cls}">{ico} {_esc(dec)} {sc}점</span></td>')
        best_p = row.get("best_product")
        best_cell = (
            f'<span class="pill pill-gold">👑 {_esc(SHORT_PROD_LABELS.get(best_p, best_p))}</span>'
            if best_p
            else '<span class="pill pill-drop">보류/제외</span>'
        )
        m_rows_html.append(
            f"<tr>"
            f"<td><a href='https://youtube.com/shorts/{_esc(vid)}' target='_blank' rel='noopener'>{_esc(row['title'][:38])} ↗</a>"
            f"<div style='font-size:0.75rem;color:var(--muted);'>👀 {row['views']:,}회 · 🔥 {row['views_per_day']:,}회/일</div></td>"
            f"{''.join(cells_html)}"
            f"<td>{best_cell}</td>"
            f"</tr>"
        )

    st.markdown(rec_banner, unsafe_allow_html=True)
    with st.expander("🔀 더랩바이블랑두 3종 교차 매칭 매트릭스 상세 보기 (추가 YouTube 쿼터 0 · 기본 접힘)", expanded=False):
        st.markdown(
            f"""
            <div style="overflow-x:auto;">
              <table class="b2b-table">
                <thead><tr><th>영상 (조회수 · 일평균🔥)</th>{th_prods}<th>최적 추천</th></tr></thead>
                <tbody>{''.join(m_rows_html)}</tbody>
              </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Section 3 (P2 + P3): Go Campaign Cards
st.markdown(f'<div class="sec-heading">🎯 Go 판정 캠페인 컨셉 ({len(go_items)}건)</div>', unsafe_allow_html=True)

prod_banned = [
    pipeline._clean_banned_for_creator(x)
    for x in products_map.get(product_name, {}).get("unverified_removed_from_v1", [])
]
prod_banned_str = ", ".join(x for x in prod_banned if x)

if not go_items:
    st.markdown(
        '<div class="empty-box">이번 수집 배치에서는 우리 제품과 억지 연결 없이 바로 집행할 Go 컨셉이 없습니다.<br>아래 Pivot 후보를 직접 시청해 검토하거나 수집 기간을 조정해 보세요.</div>',
        unsafe_allow_html=True,
    )
else:
    for idx, j in enumerate(go_items):
        vid = j["video_id"]
        v = v_by_id.get(vid, {})
        f = f_by_id.get(vid, {})
        b = b_by_id.get(vid)
        is_top = idx == 0
        card_cls = "tcard gold" if is_top else "tcard"
        top_badge = '<span class="pill pill-gold">👑 TOP GO PICK</span>' if is_top else ""
        cap_badge = (
            '<span class="pill pill-go">✅ 자막 검증 완료</span>'
            if f.get("text_source") == "caption"
            else '<span class="pill pill-warn">⚠️ 자막 미확인 (직접 시청 필요)</span>'
        )
        quote = f.get("hook_quote") or f.get("evidence_quote") or "-"
        thumb = v.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
        pub_date = (v.get("published_at") or "-")[:10]
        needs_rev = bool(b and b.get("needs_review"))

        rev_banner = ""
        if needs_rev:
            v_str = "; ".join(b.get("violations", []))
            rev_banner = f'<div class="alert-banner alert-danger">🚨 <b>발송 보류 — 검수 필요:</b> {_esc(v_str)}</div>'

        sb_html = ""
        if b:
            sb_html = f"""
            <div class="sb-grid">
              <div class="sb-cell"><div class="sb-label">⚡ 1. 첫 3초 훅</div><div class="sb-text">{_esc(b['hook'])}</div></div>
              <div class="sb-cell"><div class="sb-label">👀 2. 비포 공감 상황</div><div class="sb-text">{_esc(b['before'])}</div></div>
              <div class="sb-cell"><div class="sb-label">💧 3. 제품 침투 시점</div><div class="sb-text">{_esc(b['product_moment'])}</div></div>
              <div class="sb-cell"><div class="sb-label">🛒 4. 구매/참여 CTA</div><div class="sb-text">{_esc(b['cta'])}</div></div>
            </div>
            <div class="note-strip">
              <b>📝 크리에이터 주의사항:</b> {_esc(b['creator_note'])}
              {f'<br><b>🚫 절대 금지 표현:</b> {_esc(prod_banned_str)}' if prod_banned_str else ''}
            </div>
            """

        st.markdown(
            f"""
            <div class="{card_cls}">
              <div class="tcard-top">
                <div class="badge-group">
                  {top_badge}
                  <span class="pill pill-go">🎯 Go</span>
                  <span class="pill pill-purple">{_esc(f.get('format_tag', '기타'))}</span>
                  {cap_badge}
                </div>
                <div>{_dot_gauge(j['score'], 'Go')}</div>
              </div>
              {rev_banner}
              <div class="tcard-title">{_esc(f.get('what_happens') or v.get('title', vid))}</div>
              <div class="tcard-reason"><b>📌 Go 근거:</b> {_esc(j['reason'])}</div>
              <div class="claim-chip">🔗 {_esc(pipeline._clean_claim_for_creator(j.get('linked_claim') or '')) or _esc(j.get('linked_claim') or '-')}</div>
              <div class="quote-box">
                <div class="quote-meta"><span>💬 실제 영상 자막 원문 인용</span><span>100% 원문 대조 통과</span></div>
                <div class="quote-text">"{_esc(quote)}"</div>
              </div>
              <div class="evid-item">
                <img class="evid-thumb" src="{_esc(thumb)}" alt="thumb"/>
                <div class="evid-body">
                  <div class="evid-title">{_esc(v.get('title', vid))}</div>
                  <div class="evid-meta">
                    <span>📺 {_esc(v.get('channel_title', '-'))}</span>
                    <span>👀 {v.get('views', 0):,}회</span>
                    {f'<span class="pill pill-go">🆕 NEW</span>' if v.get('is_new') else ''}
                    {f'<span class="pill pill-go">+{int(v.get("views_delta")):,}회 ↑</span>' if isinstance(v.get('views_delta'), int) and v.get('views_delta') > 0 else ''}
                    <span class="pill pill-hot">🔥 {v.get('views_per_day', 0):,}회/일</span>
                    <span>❤️ {v.get('like_rate', 0.0):.2f}%</span>
                    <span>📅 {_esc(pub_date)}</span>
                  </div>
                </div>
                <a class="evid-link" href="https://youtube.com/shorts/{_esc(vid)}" target="_blank" rel="noopener">쇼츠 보기 ↗</a>
              </div>
              {sb_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2종 원클릭 복사 액션 바 + 전문 미리보기/다운로드
    any_needs_rev = any(b.get("needs_review") for b in briefs)
    internal_md = res.get("internal_report_md", "")
    dm_clean_md = res.get("creator_dm_clean_md") or res.get("creator_guide_md", "")
    _copy_buttons_widget(internal_md, dm_clean_md, any_needs_rev, key_suffix="main")

    with st.expander("📄 팀장 보고서 / 인플루언서 DM 전문 미리보기 및 .md 다운로드", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📋 팀장/슬랙 보고용 1페이지 요약**")
            st.download_button(
                "⬇️ 보고서 .md 저장", data=internal_md,
                file_name=f"trend_report_{report_date}.md", mime="text/markdown",
            )
            st.code(internal_md, language="markdown")
        with c2:
            st.markdown("**💌 인플루언서 DM 발송 본문 (내부 주석 제거 완료)**")
            st.download_button(
                "⬇️ 촬영 가이드 .md 저장", data=dm_clean_md,
                file_name=f"creator_dm_{report_date}.md", mime="text/markdown",
            )
            st.code(dm_clean_md, language="markdown")

# Section 4 (P2): Pivot & Drop
if pivot_items:
    st.markdown(f'<div class="sec-heading">⚠️ Pivot — 서브 테스트 / 직접 시청 검토 ({len(pivot_items)}건)</div>', unsafe_allow_html=True)
    for j in pivot_items:
        vid = j["video_id"]
        v = v_by_id.get(vid, {})
        f = f_by_id.get(vid, {})
        thumb = v.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
        meta_badge = (
            '<span class="pill pill-warn">⚠️ 자막 미확인 (직접 시청 필요)</span>'
            if f.get("text_source") != "caption"
            else '<span class="pill pill-go">✅ 자막 검증 완료</span>'
        )
        st.markdown(
            f"""
            <div class="pivot-card">
              <img class="pivot-thumb" src="{_esc(thumb)}" alt="thumb"/>
              <div class="evid-body">
                <div class="badge-group" style="margin-bottom:4px;">
                  {meta_badge}
                  <span class="pill pill-purple">{_esc(f.get('format_tag', '기타'))}</span>
                  {_dot_gauge(j['score'], 'Pivot')}
                </div>
                <div class="evid-title"><a href="https://youtube.com/shorts/{_esc(vid)}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none;">{_esc(v.get('title', vid))} ↗</a></div>
                <div class="evid-meta">
                  <span>👀 {v.get('views', 0):,}회</span>
                  <span class="pill pill-hot">🔥 {v.get('views_per_day', 0):,}회/일</span>
                  <span>사유: {_esc(j['reason'])}</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with st.expander(f"❌ 부적합 탈락 {len(drop_items)}건 — 억지 연결 차단 내역 보기 (기본 접힘)", expanded=False):
    if not drop_items:
        st.info("탈락 항목이 없습니다.")
    else:
        rows_html = []
        for j in drop_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            ev_badge = "" if f.get("evidence_ok") else ' <span class="pill pill-drop">🚫 근거 검증 실패</span>'
            rows_html.append(
                f"<tr>"
                f"<td><span class='pill pill-drop'>{_esc(f.get('domain', '-'))}</span>{ev_badge}</td>"
                f"<td><a href='https://youtube.com/shorts/{_esc(vid)}' target='_blank' rel='noopener'>{_esc(v.get('title', vid)[:55])} ↗</a></td>"
                f"<td>{v.get('views', 0):,}회</td>"
                f"<td>{_esc(j['reason'])}</td>"
                f"</tr>"
            )
        st.markdown(
            f"""
            <table class="b2b-table">
              <thead><tr><th>도메인</th><th>영상 제목 (쇼츠 링크)</th><th>조회수</th><th>탈락 사유</th></tr></thead>
              <tbody>{''.join(rows_html)}</tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )

# Section 5 (P0): Clipping Top 10 Raw View
with st.expander(f"📊 클리핑 원본 Top {len(videos)} 전체 보기 (정렬 가능)", expanded=False):
    raw_sort = st.radio(
        "정렬 기준",
        ["🔥 일평균 조회수순", "👀 총 조회수순", "❤️ 좋아요율순"],
        horizontal=True,
        key="raw_sort_radio",
    )
    if raw_sort == "👀 총 조회수순":
        sorted_v = sorted(videos, key=lambda x: x.get("views", 0), reverse=True)
    elif raw_sort == "❤️ 좋아요율순":
        sorted_v = sorted(videos, key=lambda x: x.get("like_rate", 0.0), reverse=True)
    else:
        sorted_v = sorted(videos, key=lambda x: x.get("views_per_day", 0), reverse=True)

    t_rows = []
    for rank, v in enumerate(sorted_v, 1):
        vid = v["video_id"]
        f = f_by_id.get(vid, {})
        j = j_by_id.get(vid, {})
        dec = j.get("decision", "-")
        dec_cls = "pill-go" if dec == "Go" else "pill-warn" if dec == "Pivot" else "pill-drop"
        cap_ico = "✅" if v.get("text_source") == "caption" else "⚠️"
        delta_badge = (
            ' <span class="pill pill-go">🆕 NEW</span>'
            if v.get("is_new")
            else (
                f' <span class="pill pill-go">+{int(v.get("views_delta")):,} ↑</span>'
                if isinstance(v.get("views_delta"), int) and v.get("views_delta") > 0
                else ""
            )
        )
        t_rows.append(
            f"<tr>"
            f"<td><b>{rank}</b></td>"
            f"<td><a href='https://youtube.com/shorts/{_esc(vid)}' target='_blank' rel='noopener'>{_esc(v.get('title', vid)[:45])} ↗</a>{delta_badge}</td>"
            f"<td>{_esc(v.get('channel_title', '-'))}</td>"
            f"<td>{v.get('views', 0):,}</td>"
            f"<td><b>🔥 {v.get('views_per_day', 0):,}</b></td>"
            f"<td>{v.get('like_rate', 0.0):.2f}%</td>"
            f"<td>{_esc((v.get('published_at') or '-')[:10])}</td>"
            f"<td>{cap_ico}</td>"
            f"<td><span class='pill pill-purple'>{_esc(f.get('format_tag', '기타'))}</span></td>"
            f"<td><span class='pill {dec_cls}'>{_esc(dec)}</span></td>"
            f"</tr>"
        )
    st.markdown(
        f"""
        <table class="b2b-table">
          <thead>
            <tr><th>#</th><th>영상</th><th>채널</th><th>총조회수</th><th>일평균🔥</th><th>좋아요율</th><th>업로드일</th><th>자막</th><th>포맷</th><th>판정</th></tr>
          </thead>
          <tbody>{''.join(t_rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )
