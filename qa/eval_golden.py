"""qa/eval_golden.py — 오프라인 QA 6대 결함 회귀 테스트 + 골든셋 15건 규칙/감사 자동 채점기
네트워크 없이 샌드박스에서 즉시 실행 가능:
  python qa/eval_golden.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import agent_core
import history_store
import pipeline


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(f"[FAIL] {msg}")


def test_defect_1_brief_violations(products):
    toner = products["올리고 히알루론산 딥 토너"]

    # 1-A: 정상 스크립트 + 금지어를 안내하는 creator_note → 위반 0건 (자기모순 오탐 제거)
    clean_sb = pipeline.Storyboard(
        video_id="Zl5CPQxmWFE",
        hook="전성분표 직접 확인해본 속건조 물토너 루틴",
        before="세안 후 속건조로 피부가 당기는 저녁 루틴",
        product_moment="저분자 히알루론산 워터 제형 토너를 화장솜에 적셔 15~20분 토너 팩으로 활용",
        cta="올리브영에서 올리고 히알루론산 딥 토너 확인해보세요",
        creator_note="주의: 올리브영 1위 토너, 7스킨 레이어링, 100% 흡수 같은 미확인 표현은 절대 사용 금지",
    )
    v_clean = pipeline._brief_violations(clean_sb, toner)
    _assert(v_clean == [], f"creator_note 오탐 발생: {v_clean}")

    # 1-B: 화장품법 과대광고 + 미확인 수치 → 전부 적발
    bad_sb = pipeline.Storyboard(
        video_id="Zl5CPQxmWFE",
        hook="올리브영 1등 수분 토너! 3초 만에 즉각 진정",
        before="24시간 속건조 고민",
        product_moment="10배 수분 흡수되는 기적의 토너, 피부 염증 완화 및 재생 효과",
        cta="지금 1위 제품 구매",
        creator_note="정상 메모",
    )
    v_bad = pipeline._brief_violations(bad_sb, toner)
    joined = " | ".join(v_bad)
    for must_catch in ["1등", "3초", "즉각", "24시간", "10배", "기적", "재생", "1위"]:
        _assert(must_catch in joined, f"과대광고 미탐('{must_catch}'): {v_bad}")
    return f"PASS (clean=0 violations, overclaim={len(v_bad)} violations caught)"


def test_defect_2_agent_core_p0():
    # 2-A: 색조 키워드 제거 확인
    _assert("메이크업 꿀팁" not in agent_core.KBEAUTY_MEGA_KEYWORDS, "색조 키워드('메이크업 꿀팁') 잔존")
    _assert(len(agent_core.KBEAUTY_MEGA_KEYWORDS) >= 3, "기초 앵커 키워드 부족")

    # 2-B: float 기반 days_since_published (47시간 전 = 1.96일, 2배 왜곡 제거)
    now = datetime(2026, 11, 25, 0, 0, 0, tzinfo=timezone.utc)
    pub_47h = (now - timedelta(hours=47)).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = agent_core.compute_video_metrics(views=100000, likes=3000, published_at=pub_47h, now_utc=now)
    _assert(1.9 <= m["days_since_published"] <= 2.0, f"47h 경과일 오류: {m}")
    _assert(50000 <= m["views_per_day"] <= 52000, f"views_per_day 왜곡: {m}")
    _assert(m["like_rate"] == 3.0, f"like_rate 오류: {m}")

    # 2-C: 최근 1시간 영상도 최소 0.25일 하한 적용
    pub_1h = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    m_1h = agent_core.compute_video_metrics(views=10000, likes=500, published_at=pub_1h, now_utc=now)
    _assert(m_1h["days_since_published"] == 0.25, f"최소 0.25일 하한 미적용: {m_1h}")

    # 2-D: YouTube 유닛 상한(1,500) 가드 테스트 (임시 로그 파일)
    with tempfile.TemporaryDirectory() as td:
        tmp_log = os.path.join(td, "usage_log.json")
        t1 = agent_core.record_youtube_units(1000, action="test1", log_path=tmp_log)
        _assert(t1 == 1000, f"유닛 기록 오류: {t1}")
        blocked = False
        try:
            agent_core.record_youtube_units(501, action="test_overflow", log_path=tmp_log)
        except RuntimeError:
            blocked = True
        _assert(blocked, "1,500유닛 초과 시 RuntimeError 미발생")

    # 2-E: 미사용 YoutubeLoader import 제거 확인 (Defect 6)
    _assert(not hasattr(agent_core, "YoutubeLoader"), "미사용 YoutubeLoader가 agent_core에 남아있음")
    return "PASS (keywords, 47h float velocity, 0.25d floor, 1500-unit guard, no dead import)"


def test_defect_3_and_4_step2_guardrails(products):
    toner = products["올리고 히알루론산 딥 토너"]
    pad = products["그린 플라보노이드 2.5 패드"]
    valid_claim = toner["verified_claims"][0]

    # 3: text_source="meta" 영상은 LLM이 Go(5점)를 줘도 Pivot(3점)으로 상한 제한
    meta_fact = {
        "video_id": "meta_vid_1",
        "domain": "기초/스킨케어",
        "format_tag": "응급처치 루틴형",
        "what_happens": "속건조 물토너 루틴",
        "product_types": ["토너"],
        "evidence_ok": True,
        "text_source": "meta",
    }
    raw_meta_go = [pipeline.Judgement(
        video_id="meta_vid_1", decision="Go", score=5,
        reason="속건조 토너와 일치", linked_claim=valid_claim,
    )]
    res_meta = pipeline.apply_judgement_rules(raw_meta_go, [meta_fact], toner)[0]
    _assert(res_meta["decision"] == "Pivot" and res_meta["score"] == 3, f"meta Go 차단 실패: {res_meta}")
    _assert(any("자막 미확인" in fl for fl in res_meta["flags"]), f"자막 미확인 플래그 누락: {res_meta}")

    # 4-A: 기초/스킨케어 내부 non_fit_territory (각질 필링 패드 vs 그린 패드) 강제 Drop
    exfol_fact = {
        "video_id": "exfol_1",
        "domain": "기초/스킨케어",
        "format_tag": "제품 리뷰형",
        "what_happens": "아하 바하 각질 제거 필링 패드로 묵은 각질 닦아내기",
        "product_types": ["각질 필링 패드"],
        "evidence_ok": True,
        "text_source": "caption",
    }
    raw_exfol_go = [pipeline.Judgement(
        video_id="exfol_1", decision="Go", score=5,
        reason="패드 제품이라 적합", linked_claim=pad["verified_claims"][0],
    )]
    res_exfol = pipeline.apply_judgement_rules(raw_exfol_go, [exfol_fact], pad)[0]
    _assert(res_exfol["decision"] == "Drop" and res_exfol["score"] <= 2, f"non_fit_territory 차단 실패: {res_exfol}")

    # 4-B: linked_claim 2글자("토너") 우회 차단
    _assert(not pipeline._is_valid_linked_claim("토너", toner["verified_claims"]), "2글자 linked_claim 우회 허용됨")
    _assert(pipeline._is_valid_linked_claim(valid_claim, toner["verified_claims"]), "정상 linked_claim 거부됨")
    cap_fact = {**meta_fact, "video_id": "cap_vid_1", "text_source": "caption"}
    raw_short_lc = [pipeline.Judgement(
        video_id="cap_vid_1", decision="Go", score=5,
        reason="토너 연결", linked_claim="토너",
    )]
    res_short = pipeline.apply_judgement_rules(raw_short_lc, [cap_fact], toner)[0]
    _assert(res_short["decision"] == "Pivot" and res_short["score"] == 3, f"2글자 linked_claim 강등 실패: {res_short}")

    # 4-C: evidence_ok=False 영상 증발 방지 (합계 100% 일치)
    bad_ev_fact = {**cap_fact, "video_id": "bad_ev_1", "evidence_ok": False}
    res_all = pipeline.apply_judgement_rules(raw_short_lc, [cap_fact, bad_ev_fact], toner)
    _assert(len(res_all) == 2, f"evidence_ok=False 증발 발생: {len(res_all)}")
    bad_ev_j = next(j for j in res_all if j["video_id"] == "bad_ev_1")
    _assert(bad_ev_j["decision"] == "Drop", f"evidence_ok=False가 Drop이 아님: {bad_ev_j}")

    return "PASS (meta->Pivot cap, non_fit->Drop, 2-char linked_claim blocked, no evaporated videos)"


def test_defect_5_and_6_outputs_and_brief_ids(products):
    # 5: 2종 복사 산출물 검증 (products.json 미노출, confidence=medium 경고, needs_review 상단 경고, 메타데이터)
    dummy_result = {
        "product": "올리고 히알루론산 딥 토너",
        "report_date": "2026-11-25",
        "days_range": 30,
        "product_confidence": "medium",
        "market_patterns": ["성분 함량 팩트체크형 쇼츠 강세", "속건조 보습 성분 비교 콘텐츠 확산"],
        "videos": [{
            "video_id": "Zl5CPQxmWFE",
            "title": "일명 수지 세럼 성분표 숫자 다 더하니 3%",
            "channel_title": "FLIKO",
            "views": 162,
            "likes": 0,
            "published_at": "2026-11-19T12:02:34Z",
            "text_source": "caption",
        }],
        "facts": [{
            "video_id": "Zl5CPQxmWFE",
            "domain": "기초/스킨케어",
            "format_tag": "비포/애프터 실험형",
            "what_happens": "전성분표 함량 비교",
            "hook_quote": "성분표 숫자 다 더하니 3%",
            "evidence_quote": "히알루론산 함량을 직접 확인",
            "evidence_ok": True,
            "text_source": "caption",
        }],
        "judgements": [{
            "video_id": "Zl5CPQxmWFE",
            "decision": "Go",
            "score": 4,
            "reason": "함량 공개 포맷 일치",
            "linked_claim": products["올리고 히알루론산 딥 토너"]["verified_claims"][1],
            "flags": [],
        }],
        "briefs": [{
            "video_id": "Zl5CPQxmWFE",
            "hook": "전성분표 함량 확인",
            "before": "속건조 고민",
            "product_moment": "소듐하이알루로네이트 2,700ppm 토너",
            "cta": "올리브영 확인",
            "creator_note": "미확인 표현 금지",
            "violations": ["테스트 위반"],
            "needs_review": True,
        }],
        "stats": {"videos": 1, "transcript_caption": 1, "go": 1, "pivot": 0, "drop": 0},
    }
    outs = pipeline.format_copyable_outputs(dummy_result)
    rep = outs["internal_report_md"]
    guide = outs["creator_guide_md"]
    dm_clean = outs["creator_dm_clean_md"]

    _assert("products.json" not in guide and "products.json" not in dm_clean, "개발자 파일명(products.json) 노출")
    _assert("제품 정보 확인 필요" in rep and "제품 정보 확인 필요" in guide, "confidence=medium 경고 누락")
    _assert("발송 보류 — 검수 필요" in rep and "발송 보류 — 검수 필요" in guide, "needs_review 상단 경고 누락")
    _assert("2026-11-25" in rep and "최근 30일" in rep and "2026-11-19" in rep, "기준일/수집기간/업로드일 누락")
    _assert("자막 확인 완료" in guide and "자막 확보(caption)" in rep, "자막 출처 표기 누락")
    _assert("<!-- 마케터 내부 확인용 (발송 시 제외) -->" in guide, "creator_guide_md 내부 확인 블록 누락")
    _assert("--- [아래부터 복사해서 인플루언서에게 전달] ---" in guide, "creator_guide_md 본문 구분선 누락")

    # 순수 DM 본문(creator_dm_clean_md)에 내부 출처 주석·경고·리서치 어투 0건 검증
    for forbidden_in_dm in [
        "products.json", "요약", "kurly", "glowpick", "costco", "blancdoux.com",
        "내세움", "제품 정보 확인 필요", "발송 보류", "마케터 내부 확인용",
    ]:
        _assert(forbidden_in_dm not in dm_clean, f"creator_dm_clean_md에 내부 문구 노출('{forbidden_in_dm}')")

    # 워터리 스킨 마스크 디테일 2건 검증: 미확인 임상(111.25%) 자동 제외 + 금지 문구 내부 정정 괄호 제거
    mask_res = {**dummy_result, "product": "올리고 히알루론산 워터리 스킨 마스크", "briefs": [], "judgements": []}
    mask_dm = pipeline.format_copyable_outputs(mask_res)["creator_dm_clean_md"]
    _assert("111.25%" not in mask_dm and "시험 조건" not in mask_dm, f"워터리 마스크 미확인 임상 문구 노출: {mask_dm}")
    _assert("대나무 유래로 정정" not in mask_dm and "단정 표현" not in mask_dm, f"금지 문구 내부 정정 괄호 노출: {mask_dm}")
    _assert("식물성 초밀착 시트" in mask_dm and "열감 내리는 효과" in mask_dm, f"정제된 금지 문구 누락: {mask_dm}")

    # 6: write_briefs가 go_ids 밖의 ID를 필터링하는지 검증 (Mock LLM)
    class MockStructuredLLM:
        def invoke(self, _prompt):
            return pipeline.BriefSheet(briefs=[
                pipeline.Storyboard(
                    video_id="Zl5CPQxmWFE", hook="정상 훅", before="속건조 고민",
                    product_moment="저분자 히알루론산 워터 제형 토너", cta="확인해보세요",
                    creator_note="과대광고 금지",
                ),
                pipeline.Storyboard(
                    video_id="jfsweQpxqsY", hook="비인가 ID 훅", before="블러셔",
                    product_moment="억지 연결", cta="구매", creator_note="메모",
                ),
            ])

    class MockLLM:
        def with_structured_output(self, _schema):
            return MockStructuredLLM()

    facts_map = {
        "Zl5CPQxmWFE": dummy_result["facts"][0],
        "jfsweQpxqsY": {**dummy_result["facts"][0], "video_id": "jfsweQpxqsY"},
    }
    briefs_out = pipeline.write_briefs(
        MockLLM(), dummy_result["judgements"], facts_map, "올리고 히알루론산 딥 토너", products
    )
    _assert([b["video_id"] for b in briefs_out] == ["Zl5CPQxmWFE"], f"go_ids 필터링 실패: {briefs_out}")
    return "PASS (no products.json leak, medium/needs_review banners, metadata, go_ids strict filter)"


def eval_golden_set(products):
    golden_path = os.path.join(ROOT, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        gs = json.load(f)
    items = gs["items"]
    target_product = gs["_meta"]["target_product"]
    toner = products[target_product]
    valid_claim = toner["verified_claims"][0]

    # 1) Step 1 audit_facts 검증 (15건 정상 인용 + 1건 날조 인용 차단)
    videos = [pipeline._ensure_video_metrics(it) for it in items]
    raw_facts = [
        pipeline.Fact(video_id=it["video_id"], **it["sample_fact"])
        for it in items
    ]
    audited = pipeline.audit_facts(raw_facts, videos)
    _assert(len(audited) == len(items), f"팩트 수 불일치: {len(audited)} != {len(items)}")
    fabricated_pass = sum(1 for f in audited if not f["evidence_ok"])
    _assert(fabricated_pass == 0, f"정상 골든셋 인용 검증 실패: {fabricated_pass}건")

    # 날조 인용 탐지 테스트
    fake_fact = pipeline.Fact(
        video_id="jfsweQpxqsY",
        domain="색조/메이크업",
        format_tag="믹싱 꿀팁형",
        what_happens="날조된 내용",
        product_types=["립틴트"],
        hook_quote="영상에 절대 없는 가짜 훅 문장",
        evidence_quote="영상에 절대 없는 가짜 근거 문장",
    )
    fake_audited = pipeline.audit_facts([fake_fact], [videos[0]])[0]
    _assert(not fake_audited["evidence_ok"] and fake_audited["hook_quote"] == "", "날조 인용 차단 실패")

    # 2) 적대적 LLM(전부 Go 5점 반환) 대비 하드 가드레일 테스트
    adversarial_js = [
        pipeline.Judgement(
            video_id=it["video_id"],
            decision="Go",
            score=5,
            reason="전부 Go 시도",
            linked_claim=valid_claim,
        )
        for it in items
    ]
    adv_out = pipeline.apply_judgement_rules(adversarial_js, audited, toner)
    _assert(len(adv_out) == len(items), "합계 불일치")

    # 정답이 Drop인 11건(jfsweQpxqsY 포함) 전부 강제 Drop 되는지 확인
    expected_drops = [it["video_id"] for it in items if it["expected_decision_for_toner"] == "Drop"]
    adv_by_id = {j["video_id"]: j for j in adv_out}
    drop_hits = sum(1 for vid in expected_drops if adv_by_id[vid]["decision"] == "Drop")
    drop_acc = round(drop_hits / len(expected_drops) * 100, 1)
    _assert(adv_by_id["jfsweQpxqsY"]["decision"] == "Drop", "jfsweQpxqsY 강제 Drop 실패!")
    _assert(drop_acc >= 90.0, f"Drop 정확도 미달: {drop_acc}%")

    # 자막 없는 RdXhzcCVtsw(meta)가 적대적 Go(5)에도 Pivot(3) 이하로 막히는지 확인
    _assert(adv_by_id["RdXhzcCVtsw"]["decision"] == "Pivot", f"meta 영상 Go 차단 실패: {adv_by_id['RdXhzcCVtsw']}")

    # Go/Pivot/Drop 분포 집계 (전부 Go 금지 확인)
    go_cnt = sum(1 for j in adv_out if j["decision"] == "Go")
    pivot_cnt = sum(1 for j in adv_out if j["decision"] == "Pivot")
    drop_cnt = sum(1 for j in adv_out if j["decision"] == "Drop")
    _assert(go_cnt + pivot_cnt + drop_cnt == len(items), "Go+Pivot+Drop 합계 불일치")
    _assert(go_cnt < len(items), "전부 Go 판정 금지 위반")

    return {
        "total_items": len(items),
        "expected_drops": len(expected_drops),
        "drop_hits": drop_hits,
        "drop_accuracy_pct": drop_acc,
        "jfsweQpxqsY_decision": adv_by_id["jfsweQpxqsY"]["decision"],
        "fabricated_quote_blocked": True,
        "distribution_under_adversarial_llm": {"Go": go_cnt, "Pivot": pivot_cnt, "Drop": drop_cnt},
    }


def test_redteam_rt1_to_rt4(products):
    toner = products["올리고 히알루론산 딥 토너"]
    pad = products["그린 플라보노이드 2.5 패드"]

    # RT1: 정상 숏폼 연출 타임코드('첫 3초', '초반 3초', '3초 훅', '5초 컷', '10초 이내') → 오탐 0건
    rt1_ok = pipeline.Storyboard(
        video_id="Zl5CPQxmWFE",
        hook="첫 3초: 화장솜에 토너를 듬뿍 적시는 클로즈업 (3초 훅)",
        before="초반 3초 컷 전환 후 10초 이내 속건조 고민 공감, 5초 컷으로 피부 결 표현",
        product_moment="저분자 히알루론산 워터 제형 토너로 15분~20분 토너 팩 연출",
        cta="올리브영에서 확인해보세요",
        creator_note="과대광고 금지",
    )
    v_rt1_ok = pipeline._brief_violations(rt1_ok, toner)
    _assert(v_rt1_ok == [], f"RT1 정상 연출 타임코드 오탐: {v_rt1_ok}")

    # RT1-B: 효능 과장 수치('1초 컷', '3초 만에') → 반드시 적발
    rt1_bad = pipeline.Storyboard(
        video_id="Zl5CPQxmWFE",
        hook="속건조 1초 컷! 3초 만에 촉촉해지는 물토너",
        before="건조한 피부",
        product_moment="저분자 히알루론산 워터 제형 토너",
        cta="확인해보세요",
        creator_note="메모",
    )
    v_rt1_bad = " | ".join(pipeline._brief_violations(rt1_bad, toner))
    _assert("1초" in v_rt1_bad and "3초" in v_rt1_bad, f"RT1 효능 과장 수치 미탐: {v_rt1_bad}")

    # RT2: 화장품법 제13조 의약품/미인증 기능성/과장 표현 → 전부 적발
    rt2_bad = pipeline.Storyboard(
        video_id="Zl5CPQxmWFE",
        hook="올영 랭킹 1등! 여드름 완치 수준으로 가라앉는 토너",
        before="아토피 피부염으로 붉어진 얼굴",
        product_moment="피부과 시술 없이 모공 축소, 주름 개선, 미백 효과 확실",
        cta="품절 대란 베스트셀러 지금 구매",
        creator_note="메모",
    )
    v_rt2 = " | ".join(pipeline._brief_violations(rt2_bad, toner))
    for kw in ["여드름 완치", "아토피", "피부염", "피부과 시술", "모공 축소", "주름 개선", "미백", "품절 대란", "베스트셀러"]:
        _assert(kw in v_rt2, f"RT2 화장품법 제13조 표현 미탐('{kw}'): {v_rt2}")

    # RT3: 유튜브 자동자막 비음성 태그([음악], [박수], >>) 제거 후 정상 인용 통과
    rt3_video = {
        "video_id": "rt3_vid",
        "title": "속건조 토너팩",
        "views": 50000,
        "likes": 1000,
        "published_at": "2026-11-20T00:00:00Z",
        "text_source": "caption",
        "source_text": ">> 오늘 피부가 [음악] 너무 당겨서 [박수] 토너팩 해봤어요",
    }
    rt3_fact = pipeline.Fact(
        video_id="rt3_vid",
        domain="기초/스킨케어",
        format_tag="응급처치 루틴형",
        what_happens="피부가 당겨서 토너팩 진행",
        product_types=["토너"],
        hook_quote="오늘 피부가 너무 당겨서 토너팩 해봤어요",
        evidence_quote="오늘 피부가 너무 당겨서 토너팩 해봤어요",
    )
    rt3_audited = pipeline.audit_facts([rt3_fact], [rt3_video])[0]
    _assert(rt3_audited["evidence_ok"] is True and rt3_audited["hook_quote"] != "", f"RT3 자막 태그 오탐: {rt3_audited}")

    # RT4: '각질 부각될 때 패드로 5분 팩' → 정상 Go 유지 (오탐 Drop 방지)
    rt4_fact = {
        "video_id": "rt4_vid",
        "domain": "기초/스킨케어",
        "format_tag": "응급처치 루틴형",
        "what_happens": "화장 전 건조해서 각질 부각될 때 진정 패드로 5분 팩하기",
        "product_types": ["진정 패드"],
        "evidence_ok": True,
        "text_source": "caption",
    }
    rt4_raw = [pipeline.Judgement(
        video_id="rt4_vid", decision="Go", score=5,
        reason="메이크업 전 진정 5~10분 팩 루틴과 직접 일치",
        linked_claim=pad["verified_claims"][5],
    )]
    rt4_out = pipeline.apply_judgement_rules(rt4_raw, [rt4_fact], pad)[0]
    _assert(rt4_out["decision"] == "Go" and rt4_out["score"] == 5, f"RT4 각질 부각 오탐 Drop 발생: {rt4_out}")

    return "PASS (RT1 timecodes/1초컷, RT2 화장품법 제13조 9종, RT3 [음악]태그, RT4 각질부각 Go 유지)"


def test_multi_product_matrix(products):
    golden_path = os.path.join(ROOT, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        items = json.load(f)["items"]

    videos = [pipeline._ensure_video_metrics(it) for it in items]
    raw_facts = [pipeline.Fact(video_id=it["video_id"], **it["sample_fact"]) for it in items]
    facts = pipeline.audit_facts(raw_facts, videos)

    mat = pipeline.build_multi_product_matrix(videos, facts, products=products)
    _assert(len(mat["products"]) == 3, f"3종 제품 수 불일치: {mat['products']}")
    _assert(len(mat["rows"]) == len(items), f"매트릭스 행 수 불일치: {len(mat['rows'])}")

    row_by_id = {r["video_id"]: r for r in mat["rows"]}
    # 1) jfsweQpxqsY(틴트 블러셔)가 3개 제품 모두 Drop인지 확인
    jf = row_by_id["jfsweQpxqsY"]
    for pname in mat["products"]:
        _assert(jf["cells"][pname]["decision"] == "Drop", f"jfsweQpxqsY가 {pname}에서 Drop 아님: {jf['cells'][pname]}")
    _assert(jf["best_product"] is None, f"jfsweQpxqsY에 best_product 부여됨: {jf}")

    # 2) 수분세럼 영상(brKNpouibqo, 마스크/시트 언급 없음) → 딥 토너 Go, 워터리 마스크는 제형 키워드 부재로 Pivot 상한
    hyd = row_by_id["brKNpouibqo"]
    _assert(hyd["cells"]["올리고 히알루론산 딥 토너"]["decision"] == "Go", f"수분 영상 토너 Go 실패: {hyd['cells']}")
    _assert(hyd["cells"]["올리고 히알루론산 워터리 스킨 마스크"]["decision"] == "Pivot", f"제형 없는 수분 영상 마스크 Pivot 캡 실패: {hyd['cells']}")

    # 2-B) 시트 마스크 1일 1팩 영상 → 워터리 스킨 마스크 Go & best_product
    mask_vid = {
        "video_id": "mask_sheet_1",
        "title": "메이크업 전 속당김 잡는 1일 1팩 대나무 시트 마스크 루틴",
        "views": 65000,
        "likes": 2200,
        "published_at": "2026-11-22T00:00:00Z",
        "text_source": "caption",
        "source_text": "메이크업 전 속당김 잡는 1일 1팩 시트 마스크 루틴 10분만 올려두면 촉촉",
    }
    mask_fact = pipeline.audit_facts([
        pipeline.Fact(
            video_id="mask_sheet_1",
            domain="기초/스킨케어",
            format_tag="응급처치 루틴형",
            what_happens="메이크업 전 속당김 완화를 위한 1일 1팩 시트 마스크 수분 루틴",
            product_types=["시트 마스크팩"],
            hook_quote="메이크업 전 속당김 잡는 1일 1팩 시트 마스크 루틴",
            evidence_quote="10분만 올려두면 촉촉",
        )
    ], [mask_vid])
    mask_mat = pipeline.build_multi_product_matrix([mask_vid], mask_fact, products=products)
    _assert(
        mask_mat["rows"][0]["best_product"] == "올리고 히알루론산 워터리 스킨 마스크",
        f"시트 마스크 영상 best_product 오류: {mask_mat['rows'][0]}",
    )

    # 3) 자막 미확인(RdXhzcCVtsw, meta)은 3종 모두 Go 불가(최대 Pivot 3점)
    rd = row_by_id["RdXhzcCVtsw"]
    for pname in mat["products"]:
        _assert(rd["cells"][pname]["decision"] != "Go", f"meta 영상이 {pname}에서 Go 통과: {rd['cells'][pname]}")

    # 4) 트러블 진정·쿨링 패드 영상 → 그린 플라보노이드 2.5 패드가 best_product로 선정
    pad_vid = {
        "video_id": "pad_calm_1",
        "title": "트러블 열감 올라왔을 때 쿨링 진정 패드 5분 팩 루틴",
        "views": 88000,
        "likes": 3100,
        "published_at": "2026-11-22T00:00:00Z",
        "text_source": "caption",
        "source_text": "트러블 열감 올라왔을 때 쿨링 진정 패드 5분 팩으로 예민해진 피부 진정 루틴",
    }
    pad_fact = pipeline.audit_facts([
        pipeline.Fact(
            video_id="pad_calm_1",
            domain="기초/스킨케어",
            format_tag="응급처치 루틴형",
            what_happens="트러블 열감과 자극으로 예민해진 피부에 쿨링 진정 패드 5분 팩 시연",
            product_types=["진정 토너 패드"],
            hook_quote="트러블 열감 올라왔을 때 쿨링 진정 패드 5분 팩",
            evidence_quote="예민해진 피부 진정 루틴",
        )
    ], [pad_vid])
    pad_mat = pipeline.build_multi_product_matrix([pad_vid], pad_fact, products=products)
    pad_row = pad_mat["rows"][0]
    _assert(
        pad_row["best_product"] == "그린 플라보노이드 2.5 패드",
        f"트러블 쿨링 패드 영상 best_product 오류: {pad_row}",
    )

    # 5) 전원 색조(Go 0건) 시 recommended_product=None 및 억지 집행 금지 문구 확인
    only_color_v = [videos[0]]
    only_color_f = [facts[0]]
    zero_mat = pipeline.build_multi_product_matrix(only_color_v, only_color_f, products=products)
    _assert(zero_mat["recommended_product"] is None and "억지 집행 금지" in zero_mat["recommendation_reason"], f"전원 Drop 추천 배너 오류: {zero_mat}")

    # 6) internal_report_md에 3종 교차 매칭 요약 포함 확인
    rep_md = pipeline.format_copyable_outputs({
        "product": "올리고 히알루론산 딥 토너",
        "report_date": "2026-11-25",
        "days_range": 30,
        "videos": videos,
        "facts": facts,
        "judgements": [],
        "briefs": [],
        "multi_product_matrix": mat,
        "stats": {"videos": len(videos), "transcript_caption": 4},
        "product_confidence": "medium",
    })["internal_report_md"]
    _assert(
        "제품 3종 교차 매칭 요약" in rep_md and "오늘의 추천 주력 제품" in rep_md and "합계 " in rep_md,
        "internal_report_md에 3종 교차 매칭 요약/합계 점수 병기 누락",
    )

    return f"PASS (jfsweQpxqsY=3종 Drop, 수분->토너/마스크 Go, 트러블쿨링->패드 best_product, 추천={mat['recommended_product']})"


def test_history_delta_and_onboarding(products):
    # 1) 시계열 스냅샷 비교 (임시 파일): 1회차 저장 → 2회차 조회수 +12,000 + 신규 1건
    with tempfile.TemporaryDirectory() as td:
        hist_path = os.path.join(td, "history.json")
        v1 = [
            {"video_id": "brKNpouibqo", "title": "기존 수분세럼 쇼츠", "views": 10000, "likes": 300,
             "published_at": "2026-11-20T00:00:00Z", "text_source": "caption"},
        ]
        run1 = history_store.annotate_with_history(v1, save=True, store_path=hist_path)
        _assert(run1[0]["has_prev_snapshot"] is False and run1[0]["is_new"] is False and run1[0]["views_delta"] is None,
                f"1회차 스냅샷 초기값 오류: {run1[0]}")

        v2 = [
            {"video_id": "brKNpouibqo", "title": "기존 수분세럼 쇼츠", "views": 22000, "likes": 650,
             "published_at": "2026-11-20T00:00:00Z", "text_source": "caption"},
            {"video_id": "new_vid_999", "title": "오늘 새로 뜬 토너팩 쇼츠", "views": 35000, "likes": 1200,
             "published_at": "2026-11-25T00:00:00Z", "text_source": "caption"},
        ]
        run2 = history_store.annotate_with_history(v2, save=True, store_path=hist_path)
        by_id = {x["video_id"]: x for x in run2}
        _assert(by_id["brKNpouibqo"]["has_prev_snapshot"] is True and by_id["brKNpouibqo"]["is_new"] is False,
                f"기존 영상 판별 오류: {by_id['brKNpouibqo']}")
        _assert(by_id["brKNpouibqo"]["views_delta"] == 12000, f"views_delta 계산 오류: {by_id['brKNpouibqo']}")
        _assert(by_id["new_vid_999"]["is_new"] is True and by_id["new_vid_999"]["views_delta"] is None,
                f"신규 영상 판별 오류: {by_id['new_vid_999']}")

        # internal_report_md에 🆕 NEW 및 +12,000 표기 검증
        rep = pipeline.format_copyable_outputs({
            "product": "올리고 히알루론산 딥 토너",
            "report_date": "2026-11-25",
            "days_range": 30,
            "videos": run2,
            "facts": [
                {"video_id": "brKNpouibqo", "domain": "기초/스킨케어", "format_tag": "응급처치 루틴형",
                 "hook_quote": "기존 수분세럼", "evidence_quote": "기존 수분세럼", "evidence_ok": True, "text_source": "caption"},
                {"video_id": "new_vid_999", "domain": "기초/스킨케어", "format_tag": "응급처치 루틴형",
                 "hook_quote": "오늘 새로 뜬 토너팩", "evidence_quote": "오늘 새로 뜬 토너팩", "evidence_ok": True, "text_source": "caption"},
            ],
            "judgements": [
                {"video_id": "brKNpouibqo", "decision": "Go", "score": 5, "reason": "수분 케어 일치", "linked_claim": products["올리고 히알루론산 딥 토너"]["verified_claims"][0]},
                {"video_id": "new_vid_999", "decision": "Go", "score": 4, "reason": "토너팩 일치", "linked_claim": products["올리고 히알루론산 딥 토너"]["verified_claims"][3]},
            ],
            "briefs": [],
            "stats": {"videos": 2, "transcript_caption": 2, "has_prev_snapshot": True, "new_videos_count": 1},
            "product_confidence": "high",
        })["internal_report_md"]
        _assert("🆕 NEW" in rep and "+12,000" in rep, f"internal_report_md에 NEW/+12,000 누락:\n{rep}")

        # 1-B) history_store 병합 유지 검증: 3회차에 new_vid_999만 저장해도 기존 brKNpouibqo 이력이 유지되어야 함
        history_store.annotate_with_history(
            [{"video_id": "only_third_vid", "title": "3회차 신규", "views": 500, "likes": 10}],
            save=True, store_path=hist_path,
        )
        loaded_hist = history_store.load_history(store_path=hist_path)
        _assert("brKNpouibqo" in loaded_hist["videos"] and "only_third_vid" in loaded_hist["videos"],
                f"history_store 병합 실패(기존 이력 소실): {list(loaded_hist['videos'].keys())}")

    # 2) 자사 제품 상세페이지 온보딩: 금지어 격리(rejected_claims) + confidence=medium 유지 + 전량 금지 시 거부
    up_mixed = pipeline.upsert_product_from_text(
        name="올리고 히알루론산 신제품 크림",
        raw_claims_text="- 저분자 히알루론산 크림 제형\n- 여드름 완치 및 아토피 피부염 치료 효과",
        fit_territory_csv="속건조, 보습 장벽",
        non_fit_territory_csv="색조 메이크업",
        source_url="https://blancdoux.com/new",
        save_to_file=False,
    )
    _assert(up_mixed["entry"]["confidence"] == "medium", f"금지어 혼입 시 high 승격 차단 실패: {up_mixed}")
    _assert(len(up_mixed["entry"]["verified_claims"]) == 1, f"금지어 격리 실패(verified_claims 오염): {up_mixed}")
    _assert(len(up_mixed["rejected_claims"]) == 1, f"rejected_claims 누락: {up_mixed}")

    # 2-B) 정상 문구만 입력 시 confidence=high 승격
    up_clean = pipeline.upsert_product_from_text(
        name="올리고 히알루론산 신제품 크림",
        raw_claims_text="- 저분자 히알루론산 크림 제형\n- 민감성 피부 자극 테스트 완료",
        fit_territory_csv="속건조, 보습 장벽",
        non_fit_territory_csv="색조 메이크업",
        save_to_file=False,
    )
    _assert(up_clean["entry"]["confidence"] == "high" and up_clean["rejected_claims"] == [], f"정상 온보딩 high 승격 실패: {up_clean}")

    # 2-C) 금지어만 입력 시 ValueError로 저장 거부
    refused = False
    try:
        pipeline.upsert_product_from_text(
            name="금지 테스트 크림",
            raw_claims_text="- 여드름 완치 아토피 치료 크림",
            save_to_file=False,
        )
    except ValueError:
        refused = True
    _assert(refused, "금지어만 입력 시 저장 거부(ValueError) 미발생")

    # 2-D) 의약품 오인 금지어 무조건 차단: verified_claims에 억지로 넣어도 _brief_violations가 무조건 적발
    poisoned_prod = {"verified_claims": ["여드름 완치 및 아토피 피부염 치료"], "unverified_removed_from_v1": []}
    poisoned_sb = pipeline.Storyboard(
        video_id="poison_1", hook="여드름 완치 토너", before="아토피 피부염 고민",
        product_moment="피부과 시술 대신 치료 효과", cta="확인해보세요", creator_note="메모",
    )
    pv = " | ".join(pipeline._brief_violations(poisoned_sb, poisoned_prod))
    _assert("완치" in pv and "아토피" in pv and "피부염" in pv and "피부과 시술" in pv,
            f"의약품 오인 무조건 차단 실패: {pv}")

    return "PASS (delta=+12,000, merge OK, banned quarantine/refusal, absolute medical guard)"


def test_shareable_html_export(products):
    dummy = {
        "product": "올리고 히알루론산 딥 토너",
        "report_date": "2026-11-25",
        "days_range": 30,
        "product_confidence": "medium",
        "market_patterns": ["전성분 팩트체크형 쇼츠 강세", "속건조 응급처치 루틴 확산"],
        "videos": [
            {
                "video_id": "xss_vid_1",
                "title": "<script>alert(1)</script> 속건조 토너 루틴",
                "channel_title": "<b>테스트채널</b>",
                "views": 120000,
                "likes": 4500,
                "published_at": "2026-11-20T00:00:00Z",
                "text_source": "caption",
                "low_views_fallback": True,
            },
            {
                "video_id": "jfsweQpxqsY",
                "title": "립틴트 블러셔 믹싱",
                "channel_title": "색조랩",
                "views": 156361,
                "likes": 4820,
                "published_at": "2026-11-15T00:00:00Z",
                "text_source": "caption",
            },
        ],
        "facts": [
            {
                "video_id": "xss_vid_1",
                "domain": "기초/스킨케어",
                "format_tag": "응급처치 루틴형",
                "what_happens": "속건조 피부에 토너팩 시연",
                "hook_quote": "속건조 토너팩",
                "evidence_quote": "속건조 토너팩",
                "evidence_ok": True,
                "text_source": "caption",
            },
            {
                "video_id": "jfsweQpxqsY",
                "domain": "색조/메이크업",
                "format_tag": "믹싱 꿀팁형",
                "what_happens": "립틴트와 컨실러 믹싱",
                "hook_quote": "립틴트 믹싱",
                "evidence_quote": "립틴트 믹싱",
                "evidence_ok": True,
                "text_source": "caption",
            },
        ],
        "judgements": [
            {
                "video_id": "xss_vid_1",
                "decision": "Go",
                "score": 5,
                "reason": "속건조 토너팩 포맷 직접 일치",
                "linked_claim": products["올리고 히알루론산 딥 토너"]["verified_claims"][0],
            },
            {
                "video_id": "jfsweQpxqsY",
                "decision": "Drop",
                "score": 1,
                "reason": "[규칙] 색조/메이크업 영역 불일치",
                "linked_claim": "",
            },
        ],
        "briefs": [
            {
                "video_id": "xss_vid_1",
                "hook": "첫 3초 토너팩 클로즈업",
                "before": "속건조 고민",
                "product_moment": "저분자 히알루론산 워터 제형 토너",
                "cta": "올리브영 확인",
                "creator_note": "과대광고 금지",
                "violations": ["테스트 위반 항목"],
                "needs_review": True,
            }
        ],
        "multi_product_matrix": {
            "products": list(products.keys()),
            "recommended_product": "올리고 히알루론산 딥 토너",
            "recommendation_reason": "올리고 히알루론산 딥 토너 (Go 1건·합계 5점)",
            "product_summary": {},
            "rows": [],
        },
    }
    html_out = pipeline.export_shareable_html_report(dummy)
    _assert(html_out.startswith("<!DOCTYPE html>"), "HTML5 독타입 누락")
    _assert("@media print" in html_out, "@media print 인쇄 최적화 CSS 누락")
    _assert("kpi-grid" in html_out and "Go 판정 캠페인 컨셉" in html_out, "KPI/Go 카드 누락")
    _assert("색조/메이크업 영역 불일치" in html_out, "Drop 탈락 사유 누락")
    _assert("3종 교차 매칭 추천 주력 제품" in html_out, "3종 교차 매칭 추천 배너 누락")
    _assert("발송 보류" in html_out, "needs_review=True 발송 보류 경고 누락")
    _assert("&lt;script&gt;alert(1)&lt;/script&gt;" in html_out, "XSS 이스케이프 누락")
    _assert("<script>" not in html_out.lower(), "원시 <script> 태그가 보고서 HTML에 존재")
    _assert("kurly, glowpick 요약" not in html_out, "내부 출처 괄호 주석 노출")
    return f"PASS ({len(html_out)} chars, @media print, XSS escaped, 0 <script>, needs_review banner)"


def test_step1_step2_kr_flow(products):
    # 1) KR_EXPLORE_TREE 16개 뷰티 전용 경로 + 5개 유통·고민 빠른 칩 검증 ("all" 제거)
    expected_keys = {
        "beauty", "beauty/skincare", "beauty/makeup", "beauty/hairbody",
        "beauty/skincare/toner", "beauty/skincare/serum", "beauty/skincare/cream",
        "beauty/skincare/sun", "beauty/skincare/mask", "beauty/skincare/cleansing",
        "beauty/makeup/lip", "beauty/makeup/blush", "beauty/makeup/cushion", "beauty/makeup/eye",
        "beauty/hairbody/hair", "beauty/hairbody/body",
    }
    _assert("all" not in agent_core.KR_EXPLORE_TREE, "all 경로가 아직 남아있음")
    _assert(set(agent_core.KR_EXPLORE_TREE.keys()) == expected_keys,
            f"KR_EXPLORE_TREE 경로 불일치: {set(agent_core.KR_EXPLORE_TREE.keys())}")
    _assert(agent_core.KR_EXPLORE_TREE["beauty"]["parent"] is None, "beauty 루트 parent가 None이 아님")
    for k, node in agent_core.KR_EXPLORE_TREE.items():
        _assert(len(node["keywords"]) == 3, f"{k} 키워드 수 != 3: {node['keywords']}")
    _assert(len(agent_core.KR_BEAUTY_QUICK_CHIPS) == 5, f"빠른 칩 수 != 5: {agent_core.KR_BEAUTY_QUICK_CHIPS.keys()}")

    # 1-B) get_beauty_viral_grade() S/A/B/C 기준 및 소형 채널 왜곡 방지 검증
    _assert(agent_core.get_beauty_viral_grade(120000, 4000, 1.5)["grade"] == "S", "10만 조회수 S등급 실패")
    _assert(agent_core.get_beauty_viral_grade(15000, 1500, 6.2)["grade"] == "S", "1만↑+구독자 5배↑ S등급 실패")
    _assert(agent_core.get_beauty_viral_grade(100, 50, 10.0)["grade"] == "C", "소형 채널 100회/10배 왜곡 차단 실패")
    _assert(agent_core.get_beauty_viral_grade(35000, 1200, 1.2)["grade"] == "A", "3만 조회수 A등급 실패")
    _assert(agent_core.get_beauty_viral_grade(12000, 500, 1.2)["grade"] == "B", "1만 조회수 B등급 실패")

    # 2) is_spam_video() 필터 검증
    _assert(agent_core.is_spam_video({"views": 0, "title": "정상 제목"}), "조회수 0 스팸 미탐")
    _assert(agent_core.is_spam_video({"views": 5000, "title": "#a #b #c #d #e #f #g #h 과다태그"}), "해시태그 8개 스팸 미탐")
    _assert(agent_core.is_spam_video({"views": 5000, "title": "올영 무료나눔 이벤트 참여하세요"}), "스팸 키워드 미탐")
    _assert(not agent_core.is_spam_video({"views": 12000, "title": "속건조 토너팩 추천 #shorts #스킨케어"}), "정상 영상 스팸 오탐")

    # 3) 색조 제품('촉촉한 탕후루 립틴트', '색조 > 립·틴트') 양방향 Step 2 매칭 검증
    golden_path = os.path.join(ROOT, "qa", "golden_set.json")
    with open(golden_path, encoding="utf-8") as f:
        gs_items = json.load(f)["items"]
    jf_it = next(x for x in gs_items if x["video_id"] == "jfsweQpxqsY")
    br_it = next(x for x in gs_items if x["video_id"] == "brKNpouibqo")
    vids = [pipeline._ensure_video_metrics(jf_it), pipeline._ensure_video_metrics(br_it)]
    facts = pipeline.audit_facts([
        pipeline.Fact(video_id="jfsweQpxqsY", **jf_it["sample_fact"]),
        pipeline.Fact(video_id="brKNpouibqo", **br_it["sample_fact"]),
    ], vids)
    step1_mock = {
        "path_label": "한국 > 뷰티 > 색조메이크업 > 립·틴트",
        "days_range": 30,
        "report_date": "2026-11-25",
        "videos": vids,
        "facts": facts,
        "market_patterns": ["립틴트와 컨실러를 믹싱하는 멀티 유즈 메이크업 포맷 인기"],
        "recommended_formats": pipeline._summarize_recommended_formats(facts, vids),
        "stats": {"videos": 2, "transcript_caption": 2},
    }

    class MockStep2LLM:
        def with_structured_output(self, schema):
            class _Runner:
                def invoke(self_inner, _prompt):
                    if schema is pipeline.JudgementSheet:
                        return pipeline.JudgementSheet(judgements=[
                            pipeline.Judgement(
                                video_id="jfsweQpxqsY", decision="Go", score=5,
                                reason="립틴트 블러셔 믹싱 포맷과 글로우 립틴트 소구가 직접 일치",
                                linked_claim="맑은 과즙 광택 글로우 립틴트",
                            ),
                            pipeline.Judgement(
                                video_id="brKNpouibqo", decision="Go", score=5,
                                reason="수분감으로 억지 연결 시도",
                                linked_claim="맑은 과즙 광택 글로우 립틴트",
                            ),
                        ])
                    return pipeline.BriefSheet(briefs=[
                        pipeline.Storyboard(
                            video_id="jfsweQpxqsY",
                            hook="첫 3초: 손등에 립틴트 한 방울 떨어뜨려 블러셔 믹싱",
                            before="볼터치와 립 컬러가 따로 노는 메이크업 고민",
                            product_moment="맑은 과즙 광택 글로우 립틴트를 볼에 톡톡 블렌딩",
                            cta="올리브영에서 컬러 차트 확인해보세요",
                            creator_note="과대광고 수치 표현 금지",
                            copy_ideas=["립 하나로 치크까지 맑은 광택", "손등 1방울 믹싱 데일리 립틴트", "글로우 립·치크 원톤 메이크업"],
                        )
                    ])
            return _Runner()

    res2 = pipeline.run_step2_match(
        step1_mock,
        product_category="색조 > 립·틴트",
        product_name="촉촉한 탕후루 립틴트",
        brand_keywords="맑은 과즙 광택 글로우 립틴트, 볼에 톡톡 블러셔 겸용",
        llm=MockStep2LLM(),
    )
    j_map = {j["video_id"]: j for j in res2["judgements"]}
    _assert(res2["expected_domain"] == "색조/메이크업", f"색조 도메인 매핑 실패: {res2['expected_domain']}")
    _assert(j_map["jfsweQpxqsY"]["decision"] == "Go", f"색조 제품에 jfsweQpxqsY Go 실패: {j_map['jfsweQpxqsY']}")
    _assert(j_map["brKNpouibqo"]["decision"] == "Drop", f"색조 제품에 기초 세럼 Drop 실패: {j_map['brKNpouibqo']}")
    _assert(len(res2["briefs"]) == 1 and len(res2["briefs"][0]["copy_ideas"]) == 3, f"copy_ideas 3종 누락: {res2['briefs']}")
    _assert("추천 카피 3종" in res2["internal_report_md"] and "추천 카피 3종" in res2["creator_dm_clean_md"], "복사 산출물에 카피 3종 누락")
    _assert("바로 쓸 마케팅 카피 3종" in res2["shareable_html_report"], "HTML 보고서에 카피 3종 누락")

    # 4) copy_ideas에 화장품법 금지어가 들어갔을 때 _brief_violations 적발 검증
    bad_copy_sb = pipeline.Storyboard(
        video_id="jfsweQpxqsY", hook="정상 훅", before="정상 비포",
        product_moment="맑은 과즙 광택 글로우 립틴트", cta="확인해보세요", creator_note="메모",
        copy_ideas=["여드름 완치 1등 립틴트", "3초 만에 즉각 볼륨업", "정상 카피"],
    )
    v_copy = " | ".join(pipeline._brief_violations(bad_copy_sb, {"verified_claims": ["맑은 과즙 광택 글로우 립틴트"], "unverified_removed_from_v1": []}))
    _assert("완치" in v_copy and "1등" in v_copy and "3초" in v_copy, f"copy_ideas 금지어 미탐: {v_copy}")

    return "PASS (13 KR paths, spam filter, color-product jfsweQpxqsY=Go & serum=Drop, copy_ideas 3x + guard)"


def main():
    products = pipeline.load_products()
    print("=== [1] QA 6대 결함 회귀 테스트 ===")
    print("  Defect 1 (Step 4 감사/과대광고):", test_defect_1_brief_violations(products))
    print("  Defect 2 & 6 (P0 키워드/지표/유닛가드/import):", test_defect_2_agent_core_p0())
    print("  Defect 3 & 4 (meta/non_fit/linked_claim/합계):", test_defect_3_and_4_step2_guardrails(products))
    print("  Defect 5 & 6 (2종 복사 산출물/DM 정화/go_ids):", test_defect_5_and_6_outputs_and_brief_ids(products))
    print("  Red-Team RT1~RT4:", test_redteam_rt1_to_rt4(products))
    print("  B2B-08 Multi-Product Matrix:", test_multi_product_matrix(products))
    print("  B2B-10 History Delta & Onboarding:", test_history_delta_and_onboarding(products))
    print("  B2B-12 Shareable HTML Report:", test_shareable_html_export(products))
    print("  KR 2-Stage Explore & Match:", test_step1_step2_kr_flow(products))

    print("\n=== [2] 골든셋 15건 오프라인 자동 채점 ===")
    summary = eval_golden_set(products)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nALL TESTS PASSED!")


if __name__ == "__main__":
    main()
