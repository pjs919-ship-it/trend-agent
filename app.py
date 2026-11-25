"""app.py — 숏폼레이더 (ShortformRadar) K-뷰티 유튜브 쇼츠 트렌드 분석 UI
1단계: 한국 K-뷰티 유튜브 쇼츠 인기 흐름 탐색 (뷰티 계층 + 5대 실무 지표)
2단계: 방금 본 트렌드를 홍보할 상품에 입혀 추천/보류/제외 + 카피 3종 + 4단 콘티 + 보고서 생성
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
    page_title="숏폼레이더 (ShortformRadar) — K-뷰티 쇼츠 트렌드",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
.block-container { max-width: 1120px; padding-top: 1.4rem; padding-bottom: 3rem; }
.hero-bar { display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:10px; padding-bottom:14px; border-bottom:1px solid var(--line); margin-bottom:16px; }
.hero-title { font-size:1.75rem; font-weight:800; color:var(--ink); margin:0; }
.hero-sub { font-size:0.9rem; color:var(--muted); margin-top:4px; }
.step-tag { display:inline-block; padding:3px 10px; border-radius:999px; background:var(--purple-soft); color:var(--purple-dark); font-size:0.76rem; font-weight:800; margin-bottom:4px; }
.welcome-box { border:1.5px dashed var(--line-strong); border-radius:16px; padding:34px 22px; text-align:center; background:#FFF; color:var(--muted); margin:14px 0; }
.alert-banner { padding:10px 14px; border-radius:10px; font-size:0.85rem; font-weight:600; margin-bottom:12px; }
.alert-warn { background:var(--warn-soft); color:var(--warn); border-left:4px solid var(--warn); }
.alert-danger { background:var(--danger-soft); color:var(--danger); border-left:4px solid var(--danger); }
.pill { display:inline-flex; align-items:center; padding:3px 9px; border-radius:999px; font-size:0.75rem; font-weight:700; }
.pill-go { background:var(--go-soft); color:var(--go); }
.pill-warn { background:var(--warn-soft); color:var(--warn); }
.pill-drop { background:var(--drop-soft); color:var(--drop); }
.pill-purple { background:var(--purple-soft); color:var(--purple); }
.pill-gold { background:#FEF3C7; color:#92400E; border:1px solid #F59E0B; }
.pill-hot { background:var(--hot-soft); color:var(--hot); }
.insight-box { background:linear-gradient(135deg,#F6F2FF 0%,#FFF 100%); border:1px solid #E0D8F5; border-left:5px solid var(--purple); border-radius:14px; padding:16px 20px; margin:12px 0 16px; }
.pattern-row { display:flex; align-items:flex-start; gap:10px; margin-bottom:7px; font-size:0.91rem; color:var(--ink-secondary); }
.pattern-num { min-width:22px; height:22px; border-radius:999px; background:var(--purple); color:#FFF; font-size:0.75rem; font-weight:800; display:inline-flex; align-items:center; justify-content:center; margin-top:2px; }
.shorts-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-bottom:18px; }
.short-card { display:flex; gap:12px; background:#FFF; border:1px solid var(--line); border-radius:12px; padding:12px; }
.short-thumb { width:104px; height:60px; border-radius:8px; object-fit:cover; flex-shrink:0; background:#E5E7EB; }
.short-title { font-size:0.88rem; font-weight:700; color:var(--ink); text-decoration:none; display:block; margin-bottom:4px; }
.short-meta { font-size:0.76rem; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-variant-numeric:tabular-nums; }
.short-fact { font-size:0.8rem; color:var(--ink-secondary); margin-top:5px; }
.tcard { background:#FFF; border:1px solid var(--line); border-radius:16px; padding:20px 22px; margin-bottom:14px; }
.tcard.gold { border:2px solid var(--gold); background:var(--gold-soft); }
.tcard-top { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
.badge-group { display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
.tcard-title { font-size:1.1rem; font-weight:800; margin:6px 0 8px; }
.quote-box { background:#F4FBF9; border-left:3px solid var(--go); border-radius:8px; padding:9px 13px; margin:10px 0; font-size:0.88rem; }
.copy-box { background:#F6F2FF; border-left:3px solid var(--purple); border-radius:8px; padding:10px 14px; margin:10px 0; }
.sb-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin:10px 0; }
.sb-cell { background:#FFF; border:1px solid var(--line); border-radius:10px; padding:11px 13px; font-size:0.86rem; color:var(--ink-secondary); }
.sb-label { font-size:0.77rem; font-weight:800; color:var(--purple-dark); margin-bottom:4px; }
.note-strip { background:#FFF8F8; border:1px solid #FECACA; border-radius:10px; padding:9px 12px; font-size:0.8rem; color:var(--ink-secondary); }
.pivot-card { display:flex; align-items:center; gap:12px; background:#FFF; border:1px solid var(--line); border-left:4px solid var(--warn); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.pivot-thumb { width:72px; height:40px; border-radius:6px; object-fit:cover; flex-shrink:0; }
.b2b-table { width:100%; border-collapse:collapse; font-size:0.83rem; background:#FFF; }
.b2b-table th { background:var(--surface-subtle); color:var(--muted); text-align:left; padding:8px; border-bottom:1px solid var(--line); }
.b2b-table td { padding:8px; border-bottom:1px solid var(--line); color:var(--ink-secondary); font-variant-numeric:tabular-nums; }
.b2b-table a { color:var(--purple-dark); font-weight:600; text-decoration:none; }
@media (max-width:768px) { .shorts-grid, .sb-grid { grid-template-columns:1fr; } }
</style>
""",
    unsafe_allow_html=True,
)

PRODUCT_CATEGORIES = [
    "기초 > 토너·패드",
    "기초 > 세럼·앰플",
    "기초 > 크림·로션",
    "기초 > 선크림",
    "기초 > 마스크팩",
    "기초 > 클렌징",
    "색조 > 립·틴트",
    "색조 > 블러셔",
    "색조 > 쿠션·파데",
    "색조 > 아이메이크업",
    "헤어·바디 > 샴푸·트리트먼트",
    "헤어·바디 > 바디케어",
]

PRESET_EXAMPLES = {
    "toner": ("기초 > 토너·패드", "올리고 히알루론산 딥 토너", "저분자 히알루론산 워터 제형 토너, 소듐하이알루로네이트 2,700ppm, 속건조 케어, 화장솜 15~20분 토너 팩"),
    "pad": ("기초 > 토너·패드", "그린 플라보노이드 2.5 패드", "비건 진정 토너 패드, 이오시딘 2.5% 함유, 외부 자극·트러블 진정, 5~10분 고밀착 패드 팩"),
    "mask": ("기초 > 마스크팩", "올리고 히알루론산 워터리 스킨 마스크", "저분자 올리고 히알루론산 1,000ppm, 대나무 유래 비건 시트, 메이크업 전 1일 1팩, 10~20분 사용"),
    "lip": ("색조 > 립·틴트", "촉촉한 탕후루 립틴트", "맑은 과즙 광택 글로우 립틴트, 볼에 톡톡 블러셔 겸용, 촉촉한 데일리 립 컬러"),
}


def _esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=True)


def _format_ko_num(n: Any) -> str:
    num = int(n or 0)
    if num >= 100_000_000:
        return f"{num / 100_000_000:.1f}".rstrip("0").rstrip(".") + "억"
    if num >= 10_000:
        return f"{num / 10_000:.1f}".rstrip("0").rstrip(".") + "만"
    return f"{num:,}"


def _node_of(path_key: str) -> Dict[str, Any]:
    return (
        agent_core.KR_EXPLORE_TREE.get(path_key)
        or agent_core.KR_EXPLORE_TREE["beauty"]
    )


def _path_chain(path_key: str) -> List[str]:
    chain: List[str] = []
    cur = path_key
    while cur and cur in agent_core.KR_EXPLORE_TREE:
        chain.insert(0, cur)
        cur = agent_core.KR_EXPLORE_TREE[cur]["parent"]
    return chain or ["beauty"]


def _path_label(path_key: str) -> str:
    return " > ".join(_node_of(k)["label"] for k in _path_chain(path_key))


def _children_of(path_key: str) -> List[str]:
    return [k for k, v in agent_core.KR_EXPLORE_TREE.items() if v.get("parent") == path_key]


def _copy_buttons_widget(internal_md: str, dm_clean_md: str, needs_review: bool, key_suffix: str):
    rep_js = json.dumps(internal_md).replace("</", "<\\/")
    dm_js = json.dumps(dm_clean_md).replace("</", "<\\/")
    dm_label = "⚠️ 검수 후 인플루언서 DM 복사" if needs_review else "💌 인플루언서 DM 복사"
    dm_cls = "btn-danger" if needs_review else "btn-primary"
    confirm_js = "if(!confirm('검수 필요 항목이 포함되어 있습니다. 내용을 확인 후 복사할까요?')) return;" if needs_review else ""
    components.html(
        f"""
        <style>
          body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Pretendard",sans-serif; }}
          .bar {{ display:flex; gap:10px; flex-wrap:wrap; }}
          button {{ flex:1; min-width:200px; padding:10px 14px; border-radius:10px; font-size:13.5px; font-weight:700; cursor:pointer; }}
          .btn-sec {{ background:#F3EEFD; color:#4C1D95; border:1px solid #C4B5FD; }}
          .btn-primary {{ background:#6C2BD9; color:#FFF; border:1px solid #6C2BD9; }}
          .btn-danger {{ background:#FEF2F2; color:#B91C1C; border:1.5px solid #B91C1C; }}
        </style>
        <div class="bar">
          <button id="b_rep_{key_suffix}" class="btn-sec" onclick="copyTxt_{key_suffix}(REP_{key_suffix}, 'b_rep_{key_suffix}', '📋 팀장 보고 요약 복사', false)">📋 팀장 보고 요약 복사</button>
          <button id="b_dm_{key_suffix}" class="{dm_cls}" onclick="copyTxt_{key_suffix}(DM_{key_suffix}, 'b_dm_{key_suffix}', '{dm_label}', true)">{dm_label}</button>
        </div>
        <script>
          const REP_{key_suffix} = {rep_js};
          const DM_{key_suffix} = {dm_js};
          function copyTxt_{key_suffix}(txt, id, orig, isDm) {{
            if (isDm) {{ {confirm_js} }}
            const btn = document.getElementById(id);
            const done = () => {{ btn.textContent = "✅ 클립보드에 복사되었습니다!"; setTimeout(() => {{ btn.textContent = orig; }}, 2000); }};
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              navigator.clipboard.writeText(txt).then(done).catch(() => fb(txt, done));
            }} else {{ fb(txt, done); }}
          }}
          function fb(txt, cb) {{
            const ta = document.createElement("textarea"); ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
            document.body.appendChild(ta); ta.select(); try {{ document.execCommand("copy"); }} catch (e) {{}}
            document.body.removeChild(ta); cb();
          }}
        </script>
        """,
        height=54,
    )


def _build_preview_step1(path_label: str, days_range: int) -> Dict[str, Any]:
    golden_path = os.path.join(BASE_DIR, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        gs_items = json.load(f)["items"]
    skin_items = [it for it in gs_items if it["expected_domain"] == "기초/스킨케어"]
    color_items = [it for it in gs_items if it["expected_domain"] != "기초/스킨케어"][:4]
    selected = skin_items + color_items
    videos = [pipeline._ensure_video_metrics(it) for it in selected]
    for v in videos:
        v.setdefault("thumbnail_url", f"https://i.ytimg.com/vi/{v['video_id']}/mqdefault.jpg")
    raw_facts = [pipeline.Fact(video_id=it["video_id"], **it["sample_fact"]) for it in selected]
    facts = pipeline.audit_facts(raw_facts, videos)
    return {
        "mode": "preview",
        "path_label": path_label,
        "days_range": days_range,
        "report_date": date.today().isoformat(),
        "videos": videos,
        "facts": facts,
        "market_patterns": [
            "전성분 함량 숫자와 보습 핵심 성분을 20초 내외로 비교하는 팩트체크형 쇼츠가 높은 반응을 얻고 있습니다.",
            "화장 전 푸석한 피부에 수분 제품을 바로 시연하는 응급처치 루틴 포맷의 저장·공유가 강세입니다.",
            "립틴트·컨실러 믹싱 같은 색조 꿀팁도 조회수가 높아, 우리 제품 영역에 맞는 선별이 중요합니다.",
        ],
        "recommended_formats": pipeline._summarize_recommended_formats(facts, videos),
        "stats": {"videos": len(videos), "transcript_caption": sum(1 for v in videos if v["text_source"] == "caption")},
    }


def _build_preview_step2(step1_res: Dict[str, Any], cat: str, prod_name: str, keywords: str) -> Dict[str, Any]:
    exp_domain = pipeline._expected_domain_from_category(cat)
    products_ctx = dict(pipeline.load_products())
    if prod_name not in products_ctx:
        products_ctx[prod_name] = pipeline._build_temp_product_spec(cat, prod_name, keywords, exp_domain)
    prod = products_ctx[prod_name]
    claims = prod["verified_claims"]
    facts = step1_res["facts"]
    raw_js = []
    for f in facts:
        if f["domain"] != exp_domain:
            raw_js.append(pipeline.Judgement(
                video_id=f["video_id"], decision="Drop", score=1,
                reason=f"영상 영역({f['domain']})이 우리 제품 영역({exp_domain})과 달라 제외했습니다.",
                linked_claim="",
            ))
        elif f["text_source"] != "caption":
            raw_js.append(pipeline.Judgement(
                video_id=f["video_id"], decision="Pivot", score=3,
                reason="영역은 맞지만 자막이 없어 직접 시청 후 결정하는 것을 권장합니다.",
                linked_claim=claims[0],
            ))
        else:
            raw_js.append(pipeline.Judgement(
                video_id=f["video_id"], decision="Go", score=5,
                reason=f"'{f.get('format_tag', '기타')}' 포맷이 '{prod_name}'의 핵심 특징과 자연스럽게 연결됩니다.",
                linked_claim=claims[0],
            ))
    judgements = pipeline.apply_judgement_rules(raw_js, facts, prod, expected_domain=exp_domain)
    go_items = [j for j in judgements if j["decision"] == "Go"][:3]
    briefs = []
    for g in go_items:
        f_obj = next(x for x in facts if x["video_id"] == g["video_id"])
        clean_claim = pipeline._clean_claim_for_creator(claims[0]) or claims[0]
        sb = pipeline.Storyboard(
            video_id=g["video_id"],
            hook=f"첫 3초: \"{f_obj['hook_quote'] or f_obj['what_happens']}\" 자막과 함께 제품 사용 직전 클로즈업",
            before=f"평소 {cat} 고민이 드러나는 공감 비포 장면",
            product_moment=f"{prod_name} — {clean_claim} 특징을 자연스럽게 시연",
            cta="프로필 링크 또는 올리브영에서 데일리 루틴 제품 확인해보세요",
            creator_note="확인되지 않은 순위·즉각 효과·의약품 오인 표현 절대 금지",
            copy_ideas=[
                f"{prod_name}, {f_obj.get('format_tag', '루틴')}으로 바로 따라 해보는 데일리 케어",
                f"복잡한 단계 대신 딱 하나, {clean_claim}",
                f"요즘 뜨는 쇼츠 포맷 그대로 담은 {prod_name} 리얼 사용기",
            ],
        )
        viols = pipeline._brief_violations(sb, prod)
        briefs.append({**sb.model_dump(), "violations": viols, "needs_review": bool(viols)})

    res: Dict[str, Any] = {
        "product": prod_name,
        "product_category": cat,
        "expected_domain": exp_domain,
        "path_label": step1_res.get("path_label", ""),
        "report_date": step1_res.get("report_date", date.today().isoformat()),
        "days_range": step1_res.get("days_range", 30),
        "videos": step1_res["videos"],
        "facts": facts,
        "market_patterns": step1_res.get("market_patterns", []),
        "judgements": judgements,
        "briefs": briefs,
        "stats": {
            "videos": len(step1_res["videos"]),
            "transcript_caption": sum(1 for v in step1_res["videos"] if v.get("text_source") == "caption"),
            "go": sum(1 for j in judgements if j["decision"] == "Go"),
            "pivot": sum(1 for j in judgements if j["decision"] == "Pivot"),
            "drop": sum(1 for j in judgements if j["decision"] == "Drop"),
        },
        "product_confidence": prod.get("confidence", "custom"),
    }
    res.update(pipeline.format_copyable_outputs(res))
    res["shareable_html_report"] = pipeline.export_shareable_html_report(res)
    return res


# ── Session Defaults ──────────────────────────────────────────────────
st.session_state.setdefault("explore_path", "beauty")
st.session_state.setdefault("step1_res", None)
st.session_state.setdefault("step2_res", None)
st.session_state.setdefault("s2_cat", PRODUCT_CATEGORIES[0])
st.session_state.setdefault("s2_name", "")
st.session_state.setdefault("s2_kw", "")

# ── Sidebar ───────────────────────────────────────────────────────────
env_yt = os.getenv("YOUTUBE_API_KEY", "")
env_gg = os.getenv("GOOGLE_API_KEY", "")
products_map = pipeline.load_products()
product_names = list(products_map.keys())

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    with st.expander("🔑 API 키 설정", expanded=not (env_yt and env_gg)):
        yt_key = st.text_input("유튜브 API 키", value=env_yt, type="password")
        gg_key = st.text_input("제미나이 AI API 키", value=env_gg, type="password")

    model_label = st.selectbox("AI 분석 모델", ["빠른 무료 모델 (추천)", "표준 무료 모델"], index=0)
    model_name = "gemini-2.5-flash-lite" if "빠른" in model_label else "gemini-flash-latest"

    used_u = agent_core.get_used_youtube_units()
    st.caption(f"📊 오늘 유튜브 검색 사용량: **{used_u:,} / {agent_core.YOUTUBE_UNIT_LIMIT:,}**")
    st.progress(min(1.0, used_u / max(1, agent_core.YOUTUBE_UNIT_LIMIT)))

    if st.button("🗑️ 오늘 캐시 비우기", use_container_width=True):
        agent_core.clear_cache()
        st.success("캐시를 초기화했습니다.")

    st.markdown("---")
    flash_msg = st.session_state.pop("onboarding_flash", None)
    with st.expander("➕ 자사 제품 추가 / 공식 문구 등록", expanded=bool(flash_msg)):
        if flash_msg:
            if flash_msg.get("level") == "success":
                st.success(flash_msg["message"])
            else:
                st.warning(flash_msg["message"])
            if flash_msg.get("warnings"):
                st.warning("🚫 격리된 금지 표현:\n- " + "\n- ".join(flash_msg["warnings"]))

        ob_mode = st.radio("등록 방식", ["기존 제품 문구 보강", "신규 제품 등록"], horizontal=True, key="ob_mode")
        if ob_mode == "기존 제품 문구 보강":
            ob_name = st.selectbox("대상 제품", product_names, key="ob_ex")
            ex = products_map.get(ob_name, {})
            d_claims = "\n".join(ex.get("verified_claims", []))
            d_fit = ", ".join(ex.get("fit_territory", []))
            d_nonfit = ", ".join(ex.get("non_fit_territory", []))
        else:
            ob_name = st.text_input("신규 제품명", placeholder="예: 올리고 히알루론산 카밍 크림", key="ob_new")
            d_claims, d_fit, d_nonfit = "", "속건조, 보습, 진정", "색조 메이크업, 헤어/바디"

        ob_claims = st.text_area("공식 상세페이지 확인 문구 (줄바꿈 구분)", value=d_claims, height=100, key="ob_claims")
        ob_fit = st.text_input("적합 영역 (쉼표 구분)", value=d_fit, key="ob_fit")
        ob_nonfit = st.text_input("부적합 영역 (쉼표 구분)", value=d_nonfit, key="ob_nonfit")
        if st.button("💾 공식 제품 정보 저장", use_container_width=True, key="ob_save"):
            try:
                saved = pipeline.upsert_product_from_text(
                    name=ob_name, raw_claims_text=ob_claims,
                    fit_territory_csv=ob_fit, non_fit_territory_csv=ob_nonfit, save_to_file=True,
                )
                if saved.get("rejected_claims"):
                    st.session_state["onboarding_flash"] = {
                        "level": "warning",
                        "message": f"'{saved['product_name']}' 저장 완료 (금지 표현 {len(saved['rejected_claims'])}건 자동 격리).",
                        "warnings": saved["warnings"],
                    }
                else:
                    st.session_state["onboarding_flash"] = {
                        "level": "success",
                        "message": f"'{saved['product_name']}' 공식 문구 저장 완료!",
                        "warnings": [],
                    }
                st.rerun()
            except Exception as e:
                st.error(f"저장 거부: {e}")

# ── Header ────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-bar">
      <div>
        <div class="hero-title">📡 숏폼레이더 <span style="font-size:0.95rem;font-weight:700;color:var(--muted);">ShortformRadar</span></div>
        <div class="hero-sub">K-뷰티 마케터를 위한 유튜브 쇼츠 트렌드 분석 &amp; 캠페인 기획</div>
      </div>
      <span class="pill pill-purple">한국 뷰티 전용</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Step 1: 요즘 뷰티 쇼츠 트렌드 먼저 보기 ──────────────────────────────
st.markdown('<span class="step-tag">1단계 · 뷰티 트렌드 탐색</span>', unsafe_allow_html=True)
st.markdown("### 요즘 뜨는 K-뷰티 쇼츠 먼저 보기")

cur_path = st.session_state["explore_path"]
if cur_path not in agent_core.KR_EXPLORE_TREE:
    cur_path = "beauty"
    st.session_state["explore_path"] = "beauty"
chain = _path_chain(cur_path)

# 경로 Breadcrumb 버튼
crumb_cols = st.columns(len(chain) + 2)
for i, k in enumerate(chain):
    lbl = _node_of(k)["label"]
    btn_type = "primary" if i == len(chain) - 1 else "secondary"
    if crumb_cols[i].button(f"{lbl}", key=f"crumb_{k}", type=btn_type, use_container_width=True):
        st.session_state["explore_path"] = k
        st.rerun()

# 하위 세부 품목 칩 버튼
children = _children_of(cur_path)
if children:
    st.caption("👇 더 좁혀보고 싶다면 하위 카테고리를 눌러보세요:")
    ch_cols = st.columns(min(6, len(children)))
    for i, ck in enumerate(children):
        if ch_cols[i % len(ch_cols)].button(f"+ {_node_of(ck)['label']}", key=f"child_{ck}", use_container_width=True):
            st.session_state["explore_path"] = ck
            st.rerun()
else:
    st.caption("위 경로 버튼을 눌러 상위 카테고리로 돌아갈 수 있어요.")

c_days, c_sort = st.columns([1, 1.8])
with c_days:
    days_label = st.radio("수집 기간", ["🔥 최근 7일 (급상승)", "🏆 최근 30일 (대세)"], index=1, horizontal=True)
    days_val = 7 if "7일" in days_label else 30
with c_sort:
    sort_label = st.radio(
        "정렬 기준",
        ["🏆 등급·인기 순", "📈 확산력 순", "🔥 하루 평균 순", "👀 조회수 순", "💬 댓글 많은 순"],
        index=0,
        horizontal=True,
        help=(
            "• 등급·인기 순: 등급(S→A→B→C) → 누적 조회수 → 좋아요 수 → 댓글 수 순\n"
            "• 확산력 순: 구독자 수 대비 조회수가 몇 배나 터졌는지 순 (작은 채널인데 알고리즘을 타 크게 뜬 영상 우선)\n"
            "• 하루 평균 순: 올라온 뒤 하루 평균 조회수가 높은 순\n"
            "• 조회수 순: 누적 조회수가 높은 순\n"
            "• 댓글 많은 순: 시청자 질문과 반응(댓글)이 많은 순"
        ),
    )
    if "등급" in sort_label:
        sort_key = "grade"
    elif "하루 평균" in sort_label:
        sort_key = "fast"
    elif "조회수" in sort_label:
        sort_key = "views"
    elif "댓글" in sort_label:
        sort_key = "comments"
    else:
        sort_key = "subscriber_ratio"

b1, b2 = st.columns([2, 1])
run_s1_live = b1.button("🚀 이 카테고리 트렌드 보기", type="primary", use_container_width=True)
run_s1_preview = b2.button("👀 예시 화면 미리보기", use_container_width=True)

if run_s1_preview:
    st.session_state["step1_res"] = _build_preview_step1(_path_label(cur_path), days_val)
    st.session_state["step2_res"] = None

def _load_snapshot_entry(path_key: str, days_val: int) -> Optional[Dict[str, Any]]:
    snap_path = os.path.join(BASE, "data", "trends_snapshot.json")
    if not os.path.exists(snap_path):
        return None
    try:
        with open(snap_path, encoding="utf-8") as f:
            snap = json.load(f)
        entry = snap.get("entries", {}).get(f"{path_key}_{days_val}")
        if entry and entry.get("videos"):
            return entry
    except Exception:
        pass
    return None


if run_s1_live:
    snap_entry = _load_snapshot_entry(cur_path, days_val)
    if snap_entry:
        st.session_state["step1_res"] = snap_entry
        st.session_state["step2_res"] = None
        st.success(f"⚡ 최신 배치 스냅샷({snap_entry.get('updated_at_kst', '')})을 바로 불러왔어요. (API 한도 0 사용)")
    elif not yt_key or not gg_key:
        st.error("왼쪽 사이드바 'API 키 설정'에 유튜브 API 키와 제미나이 AI API 키를 모두 입력해주세요.")
    else:
        try:
            with st.spinner(f"1/2. '{_path_label(cur_path)}' 한국 뷰티 쇼츠를 모으고 있어요..."):
                yt_client = agent_core.build_youtube_client(yt_key)
                vids = agent_core.fetch_kr_step1_shorts(
                    yt_client, path_key=cur_path, days=days_val, sort_by=sort_key
                )
            if not vids:
                if days_val < 30:
                    st.warning("최근 7일 안에 조건에 맞는 쇼츠가 없어요. 기간을 '최근 30일 (대세)'로 바꿔 다시 찾아보세요.")
                else:
                    st.warning("최근 30일 조건에 맞는 쇼츠를 찾지 못했어요. 상위 카테고리를 골라 다시 찾아보세요.")
            else:
                with st.spinner("2/2. AI가 요즘 뜨는 포맷과 핵심 흐름을 정리하고 있어요..."):
                    s1 = pipeline.run_step1_explore(
                        vids, path_label=_path_label(cur_path), days_range=days_val,
                        api_key=gg_key, model=model_name,
                    )
                    s1["mode"] = "live"
                    s1["path_key"] = cur_path
                    st.session_state["step1_res"] = s1
                    st.session_state["step2_res"] = None
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"분석 중 오류가 발생했어요: {e}")

# ── Step 1 결과 또는 초기 대기 화면 ────────────────────────────────────
s1 = st.session_state["step1_res"]
if not s1:
    st.markdown(
        """
        <div class="welcome-box">
          <h3 style="margin:0 0 8px;color:var(--ink);">어떤 뷰티 카테고리의 쇼츠 트렌드를 볼까요?</h3>
          <p style="margin:0;">위에서 <b>뷰티 전체 → 기초 스킨케어 / 색조 메이크업 / 헤어·바디 → 세부 품목</b>을 고르고<br>
          <b>[🚀 이 카테고리 트렌드 보기]</b>를 눌러보세요. API 키가 없다면 <b>[👀 예시 화면 미리보기]</b>로 먼저 둘러볼 수 있어요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    if int(s1.get("days_range", 30)) != days_val:
        st.info(f"⏱️ 기간을 최근 {days_val}일로 바꿨어요. [🚀 이 카테고리 트렌드 보기]를 눌러 새 결과를 불러오세요.")

    pats_html = "".join(
        f'<div class="pattern-row"><span class="pattern-num">{i}</span><div>{_esc(p)}</div></div>'
        for i, p in enumerate(s1.get("market_patterns", []), 1)
    )
    fmt_chips = " ".join(
        f'<span class="pill pill-purple">🎬 {_esc(r["format_tag"])} ({r["count"]}건)</span>'
        for r in s1.get("recommended_formats", [])
    )
    st.markdown(
        f"""
        <div class="insight-box">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
            <b style="font-size:1.05rem;color:var(--purple-dark);">🧭 '{_esc(s1.get('path_label', ''))}' 요즘 뜨는 핵심 흐름 ({int(s1.get('days_range', 30))}일 기준)</b>
            <div>{fmt_chips}</div>
          </div>
          {pats_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    vids_disp = list(s1.get("videos", []))
    _grade_rank = {"S": 4, "A": 3, "B": 2, "C": 1}
    if sort_key == "grade":
        vids_disp.sort(
            key=lambda x: (
                _grade_rank.get(
                    agent_core.get_beauty_viral_grade(
                        int(x.get("views", 0)),
                        int(x.get("views_per_day", 0)),
                        x.get("views_per_subscriber"),
                    )["grade"],
                    1,
                ),
                int(x.get("views", 0)),
                int(x.get("likes", 0)),
                int(x.get("comments", 0)),
            ),
            reverse=True,
        )
    elif sort_key == "views":
        vids_disp.sort(key=lambda x: (x.get("views", 0), x.get("likes", 0), x.get("comments", 0)), reverse=True)
    elif sort_key == "comments":
        vids_disp.sort(key=lambda x: (x.get("comments", 0), x.get("views", 0)), reverse=True)
    elif sort_key == "fast":
        vids_disp.sort(key=lambda x: (x.get("views_per_day", 0), x.get("views", 0)), reverse=True)
    else:
        vids_disp.sort(
            key=lambda x: (
                1 if (x.get("views", 0) >= 10000 and x.get("views_per_subscriber")) else 0,
                x.get("views_per_subscriber") or 0.0,
                x.get("views_per_day", 0),
                x.get("views", 0),
            ),
            reverse=True,
        )

    f_by_id = {f["video_id"]: f for f in s1.get("facts", [])}
    ratio_tip = "구독자 수보다 조회수가 몇 배 더 나왔는지 보여줘요. 배수가 높을수록 채널 규모보다 소재 자체가 인기를 끈 영상이에요."
    grade_cls_map = {"S": "pill-gold", "A": "pill-hot", "B": "pill-go", "C": "pill-drop"}
    cards_html = []
    for v in vids_disp:
        vid = v["video_id"]
        f = f_by_id.get(vid, {})
        thumb = v.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
        g_info = agent_core.get_beauty_viral_grade(
            int(v.get("views", 0)),
            int(v.get("views_per_day", 0)),
            v.get("views_per_subscriber"),
        )
        g_cls = grade_cls_map.get(g_info["grade"], "pill-drop")
        ratio_val = v.get("views_per_subscriber")
        ratio_html = (
            f'<span class="pill pill-purple" title="{ratio_tip}">📈 구독자 대비 {ratio_val}배</span>'
            if ratio_val is not None
            else ""
        )
        delta_val = v.get("views_delta")
        delta_html = (
            f'<span class="pill pill-go">⬆️ 이전보다 +{_format_ko_num(delta_val)}</span>'
            if delta_val and int(delta_val) > 0
            else ""
        )
        pub_raw = str(v.get("published_at", ""))[:10].replace("-", ".")
        pub_html = f"<span>📅 {_esc(pub_raw)}</span><span>·</span>" if pub_raw else ""
        cards_html.append(
            f'<div class="short-card">'
            f'<img class="short-thumb" src="{_esc(thumb)}" alt="thumb"/>'
            f'<div style="flex:1;min-width:0;">'
            f'<a class="short-title" href="https://youtube.com/shorts/{_esc(vid)}" target="_blank" rel="noopener">{_esc(v.get("title", vid))} ↗</a>'
            f'<div class="short-meta" style="margin-bottom:4px;">'
            f'<span class="pill {g_cls}">{_esc(g_info["label"])}</span>'
            f'<b style="color:var(--ink);">👀 조회수 {_format_ko_num(v.get("views", 0))}</b>'
            f'<span class="pill pill-hot">🔥 하루 평균 {_format_ko_num(v.get("views_per_day", 0))}</span>'
            f'{ratio_html}'
            f'</div>'
            f'<div class="short-meta">'
            f'{pub_html}'
            f'<span>❤️ 좋아요 {_format_ko_num(v.get("likes", 0))}</span>'
            f'<span>· 💬 댓글 {int(v.get("comments", 0)):,}개</span>'
            f'{delta_html}'
            f'<span>· {_esc(f.get("format_tag", "기타"))}</span>'
            f'</div>'
            f'<div class="short-fact">{_esc(f.get("what_happens", ""))}</div>'
            f'</div></div>'
        )
    st.markdown(f'<div class="shorts-grid">{"".join(cards_html)}</div>', unsafe_allow_html=True)

    # ── Step 2: 홍보할 상품에 입히기 ────────────────────────────────────
    st.markdown("---")
    st.markdown('<span class="step-tag">2단계 · 홍보할 상품에 맞추기</span>', unsafe_allow_html=True)
    st.markdown("### 방금 본 트렌드를 홍보할 상품에 입히기")

    st.caption("⚡ 예시 상품 바로 채우기:")
    pcols = st.columns(4)
    for col, (pk, label) in zip(pcols, [
        ("toner", "💧 딥 토너"),
        ("pad", "🌿 그린 2.5 패드"),
        ("mask", "🧊 워터리 마스크"),
        ("lip", "💄 촉촉한 립틴트 (색조)"),
    ]):
        if col.button(label, key=f"preset_{pk}", use_container_width=True):
            cat_v, name_v, kw_v = PRESET_EXAMPLES[pk]
            st.session_state["s2_cat"] = cat_v
            st.session_state["s2_name"] = name_v
            st.session_state["s2_kw"] = kw_v
            st.rerun()

    ic1, ic2, ic3 = st.columns([1, 1.2, 1.8])
    with ic1:
        s2_cat = st.selectbox("상품 카테고리", PRODUCT_CATEGORIES, key="s2_cat")
    with ic2:
        s2_name = st.text_input("홍보할 상품명", placeholder="예: 올리고 히알루론산 딥 토너", key="s2_name")
    with ic3:
        s2_kw = st.text_input("강조할 핵심 특징", placeholder="예: 저분자 히알루론산 워터 토너, 속건조 케어", key="s2_kw")

    if st.button("✨ 이 트렌드로 캠페인·카피 만들기", type="primary", use_container_width=True):
        if not s2_name.strip():
            st.warning("홍보할 상품명을 입력해주세요.")
        elif s1.get("mode") == "live" and gg_key:
            try:
                with st.spinner("방금 본 트렌드와 홍보할 상품을 매칭하고 카피 3종·4단 콘티를 만들고 있어요..."):
                    st.session_state["step2_res"] = pipeline.run_step2_match(
                        s1, product_category=s2_cat, product_name=s2_name.strip(),
                        brand_keywords=s2_kw, api_key=gg_key, model=model_name,
                    )
            except Exception as e:
                st.error(f"기획 생성 중 오류: {e}")
        else:
            st.session_state["step2_res"] = _build_preview_step2(s1, s2_cat, s2_name.strip(), s2_kw)

# ── Step 2 결과 렌더링 ────────────────────────────────────────────────
s2 = st.session_state["step2_res"]
if s2 and s1:
    v_by_id = {v["video_id"]: v for v in s2.get("videos", [])}
    f_by_id = {f["video_id"]: f for f in s2.get("facts", [])}
    b_by_id = {b["video_id"]: b for b in s2.get("briefs", [])}
    go_items = [j for j in s2.get("judgements", []) if j["decision"] == "Go"]
    pv_items = [j for j in s2.get("judgements", []) if j["decision"] == "Pivot"]
    dr_items = [j for j in s2.get("judgements", []) if j["decision"] == "Drop"]

    if s2.get("product_confidence") not in ("high",):
        st.markdown(
            '<div class="alert-banner alert-warn">⚠️ <b>[제품 정보 확인 안내]</b> 최종 광고·시딩 집행 전 공식 상세페이지 원문 및 표시광고 기준을 반드시 확인하세요.</div>',
            unsafe_allow_html=True,
        )

    st.markdown(f"#### 🎯 '{_esc(s2['product'])}' 맞춤 추천 컨셉 ({len(go_items)}건)")
    if not go_items:
        st.info("이번 탐색 결과에서는 억지 연결 없이 바로 쓸 수 있는 추천 컨셉이 없습니다. 위에서 다른 세부 카테고리를 탐색해보세요.")
    else:
        for idx, j in enumerate(go_items):
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            b = b_by_id.get(vid)
            is_top = idx == 0
            dots = "●" * int(j["score"]) + "○" * (5 - int(j["score"]))
            cap_b = '<span class="pill pill-go">✅ 자막 확인 완료</span>' if f.get("text_source") == "caption" else '<span class="pill pill-warn">⚠️ 자막 미확인 (직접 시청 권장)</span>'
            rev_b = (
                f'<div class="alert-banner alert-danger">🚨 <b>발송 보류 — 검수 필요:</b> {_esc("; ".join(b.get("violations", [])))}</div>'
                if (b and b.get("needs_review"))
                else ""
            )
            copies = (b.get("copy_ideas") or []) if b else []
            copy_html = (
                '<div class="copy-box"><b style="color:var(--purple-dark);font-size:0.8rem;">✍️ 바로 쓸 마케팅 카피 3종</b>'
                + "".join(f'<div style="font-size:0.89rem;font-weight:600;margin-top:3px;">• {_esc(c)}</div>' for c in copies[:3])
                + "</div>"
                if copies
                else ""
            )
            sb_html = ""
            if b:
                sb_html = (
                    f'<div class="sb-grid">'
                    f'<div class="sb-cell"><div class="sb-label">⚡ 1. 첫 3초 훅</div>{_esc(b["hook"])}</div>'
                    f'<div class="sb-cell"><div class="sb-label">👀 2. 비포 공감 상황</div>{_esc(b["before"])}</div>'
                    f'<div class="sb-cell"><div class="sb-label">💧 3. 제품 등장 시점</div>{_esc(b["product_moment"])}</div>'
                    f'<div class="sb-cell"><div class="sb-label">🛒 4. 마무리 안내(CTA)</div>{_esc(b["cta"])}</div>'
                    f'</div>'
                    f'<div class="note-strip"><b>📝 주의사항:</b> {_esc(b["creator_note"])}</div>'
                )
            st.markdown(
                f"""
                <div class="tcard {'gold' if is_top else ''}">
                  <div class="tcard-top">
                    <div class="badge-group">
                      {'<span class="pill pill-gold">👑 최우선 추천</span>' if is_top else ''}
                      <span class="pill pill-go">🎯 추천 (Go)</span>
                      <span class="pill pill-purple">{_esc(f.get('format_tag', '기타'))}</span>
                      {cap_b}
                    </div>
                    <span style="font-weight:800;color:{'var(--gold)' if is_top else 'var(--go)'};">{dots} {int(j['score'])}점</span>
                  </div>
                  {rev_b}
                  <div class="tcard-title">{_esc(f.get('what_happens') or v.get('title', vid))}</div>
                  <div style="font-size:0.9rem;color:var(--ink-secondary);margin-bottom:6px;"><b>📌 추천 이유:</b> {_esc(j['reason'])}</div>
                  <div class="quote-box">💬 "{_esc(f.get('hook_quote') or f.get('evidence_quote') or '-')}" · <a href="https://youtube.com/shorts/{_esc(vid)}" target="_blank" rel="noopener" style="color:var(--purple-dark);font-weight:700;">원본 쇼츠 보기 ↗</a></div>
                  {copy_html}
                  {sb_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    any_rev = any(b.get("needs_review") for b in s2.get("briefs", []))
    _copy_buttons_widget(s2.get("internal_report_md", ""), s2.get("creator_dm_clean_md", ""), any_rev, key_suffix="s2")
    st.download_button(
        "📄 팀장 결재용 1페이지 보고서 HTML 저장 (PDF 인쇄·이메일 첨부용)",
        data=s2.get("shareable_html_report") or pipeline.export_shareable_html_report(s2),
        file_name=f"kbeauty_executive_report_{s2.get('report_date', date.today().isoformat())}.html",
        mime="text/html",
        use_container_width=True,
    )

    if pv_items:
        st.markdown(f"#### ⚠️ 보류 — 직접 시청 후 검토 ({len(pv_items)}건)")
        for j in pv_items:
            vid = j["video_id"]
            v = v_by_id.get(vid, {})
            f = f_by_id.get(vid, {})
            thumb = v.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
            st.markdown(
                f'<div class="pivot-card">'
                f'<img class="pivot-thumb" src="{_esc(thumb)}" alt="thumb"/>'
                f'<div><span class="pill pill-warn">⚠️ 자막 미확인 (직접 시청 필요)</span> '
                f'<span class="pill pill-purple">{_esc(f.get("format_tag", "기타"))}</span>'
                f'<div style="font-weight:700;margin-top:4px;"><a href="https://youtube.com/shorts/{_esc(vid)}" target="_blank" style="color:var(--ink);text-decoration:none;">{_esc(v.get("title", vid))} ↗</a></div>'
                f'<div style="font-size:0.8rem;color:var(--muted);">{_esc(j["reason"])}</div></div></div>',
                unsafe_allow_html=True,
            )

    with st.expander(f"❌ 제외된 영상 {len(dr_items)}건 보기 (억지 연결 자동 차단 · 기본 접힘)", expanded=False):
        if not dr_items:
            st.info("제외된 항목이 없습니다.")
        else:
            rows = "".join(
                f"<tr><td><span class='pill pill-drop'>{_esc(f_by_id.get(j['video_id'],{}).get('domain','-'))}</span></td>"
                f"<td><a href='https://youtube.com/shorts/{_esc(j['video_id'])}' target='_blank'>{_esc(v_by_id.get(j['video_id'],{}).get('title', j['video_id'])[:50])} ↗</a></td>"
                f"<td>{v_by_id.get(j['video_id'],{}).get('views',0):,}회</td>"
                f"<td>{_esc(j['reason'])}</td></tr>"
                for j in dr_items
            )
            st.markdown(
                f'<div style="overflow-x:auto;"><table class="b2b-table"><thead><tr><th>영역</th><th>영상 제목</th><th>조회수</th><th>제외 이유</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True,
            )
