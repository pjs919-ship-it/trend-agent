# 📋 Product Backlog v2 (PM 노아 관리)

> 기준 시각: 2026-11-25 02:22 (자동 스프린트 스케줄 02:35 / 03:35 / 04:35 / 05:35 / 06:35 가동 중)

| 스프린트 | 시각 | 담당 | 목표 | 상태 |
|---|---|---|---|---|
| **Loop 0** | 01:30 | PM | 출처 확인된 `products.json` 및 `PLAYBOOK.md` 구축 | ✅ 완료 |
| **Sprint 1** | 01:45 ~ 02:00 | Engineer → QA | P0~P3 B2B 파이프라인 1차 구현 + 독립 QA | ❌ FAIL (결함 6건 반려) |
| **Sprint 2 / 2-R** | 02:00 ~ 02:10 | Engineer → QA | 6대 결함 + 레드팀 RT1~RT4 전수 수정 & 골든셋 15건 통과 | ✅ PASS (오프라인 코어) |
| **Sprint 3** | 02:11 ~ 02:16 | Engineer | 7/14/30일 + `mostPopular` 벤치마크 스크립트(`qa/benchmark_days.py`) | ⏸️ 드라이런 PASS (라이브 API 승인 대기) |
| **Sprint 4 / 5-R** | 02:11 ~ 02:22 | Designer → Engineer → QA | `DESIGN_SYSTEM.md` v2 + `app.py` & `TrendSetter_KBeauty_Pro.html` 전면 개편 + 8대 디자인 QA & 레드팀 통합 검수 | ✅ PASS (오프라인 통합 8/8) |
| **Sprint 6 (02:35~)** | 02:35 ~ 06:35 | PM + 3인 팀 | 성과 극대화 백로그(제품 3종 교차 매칭 매트릭스, 1클릭 주간 리포트, 추가 레드팀) + 06:35 최종 종합 보고 | ⏳ 스케줄 대기 |

## 완료된 백로그
- [x] **B2B-01 (P0)**: `agent_core.py` `views_per_day`, `like_rate`, `qa/usage_log.json`(1,500유닛 상한), 기초 중심 앵커 키워드
- [x] **B2B-02 (P1)**: `pipeline.py` Step 1 `format_tag` + `market_patterns`(2~3개) + 자막 노이즈 태그 제거
- [x] **B2B-03 (P2)**: `pipeline.py` Step 2 Go/Pivot/Drop + 영역 불일치/`non_fit`/자막 미확인(`meta`→Pivot 상한) 하드 가드레일
- [x] **B2B-04 (P3)**: `pipeline.py` Step 3 `internal_report_md` + `creator_guide_md` + `creator_dm_clean_md` (출처 주석/미확인 임상 0건)
- [x] **B2B-05 (QA)**: `qa/golden_set.json`(15건) + `qa/eval_golden.py` (Drop 100%, 날조 0건, RT1~RT4, 화장품법 제13조)
- [x] **B2B-06 (Data)**: `qa/benchmark_days.py` 구현 및 드라이런 통과 (라이브 실행은 외부 네트워크 승인 후 1회 실행 필요)
- [x] **B2B-07 (UI)**: `DESIGN_SYSTEM.md` v2 기반 `app.py` & `TrendSetter_KBeauty_Pro.html` 전면 개편 및 Designer 8/8 PASS

## 다음 스프린트 성과 극대화 백로그 (02:35~)
- [ ] **B2B-08 (성과 극대화)**: **제품 3종 교차 매칭 매트릭스 (Multi-Product Triage)** — 한 번의 클리핑으로 딥 토너 / 그린 2.5 패드 / 워터리 마스크 3종에 대한 Go/Pivot/Drop을 한 표로 비교해 "오늘 가장 승률 높은 제품×트렌드 조합"을 즉시 추천 (마케터 반복 실행 시간 66% 추가 절감)
- [ ] **B2B-09 (라이브 E2E 대기)**: 사용자 기상 후 외부 네트워크 허용 시 `python qa/benchmark_days.py` + `python qa/run_once.py` 1회 실행으로 라이브 실측 확정
