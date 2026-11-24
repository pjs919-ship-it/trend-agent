# 📋 Product Backlog v2 (PM 노아 관리)

> 기준 시각: 2026-11-25 01:45 ~ 07:00 (자동 스프린트 스케줄 운영)

| 스프린트 | 예정 시각 | 담당 | 목표 | 상태 |
|---|---|---|---|---|
| **Loop 0** | 01:30 | PM | 출처 확인된 `products.json` 및 `PLAYBOOK.md` 구축 | ✅ 완료 |
| **Sprint 1** | 01:45 ~ 02:00 | Engineer → QA | P0~P3 B2B 파이프라인 구현 + 1차 독립 QA | ❌ FAIL (결함 6건 반려) |
| **Sprint 2** | 02:00 ~ 03:30 | Engineer → QA | QA 결함 6건 전수 수정 + 오프라인 골든셋 15개(`qa/golden_set.json`) & 자동 채점기(`qa/eval_golden.py`) 통과 | 🔄 진행중 |
| **Sprint 3** | 03:35 ~ 04:30 | Engineer → QA | 7일 / 14일 / 30일 + `mostPopular`(cat 26) 실측 비교로 최적 수집 전략 확정 | ⏳ 예약됨 |
| **Sprint 4** | 04:35 ~ 05:30 | Designer → Engineer | `DESIGN_SYSTEM.md` v2 수립 + `TrendSetter_KBeauty_Pro.html` & `app.py` B2B 위계 전면 개편 | ⏳ 예약됨 |
| **Sprint 5** | 05:35 ~ 06:30 | QA → Engineer/Designer | 레드팀 공격 (블랑두 3개 제품 전체 + 신규 키워드 테스트) + 발견 결함 전수 수정 | ⏳ 예약됨 |
| **Sprint 6** | 06:35 ~ 06:55 | PM + QA | 최종 실사용 리허설 리포트(`docs/QA_REPORT.md`), `RELEASE_NOTES.md`, Git 커밋 및 최종 보고 | ⏳ 예약됨 |

## 현재 백로그 상세 (P0 → P3)
- [ ] **B2B-01 (P0)**: `agent_core.py`에 `views_per_day`, `like_rate`, `qa/usage_log.json` (1,500유닛 상한 가드) 추가
- [ ] **B2B-02 (P1)**: `pipeline.py` Step 1에 `format_tag`(포맷 분류) 및 전체 영상 관통 `market_patterns`(2~3개) 추가
- [ ] **B2B-03 (P2)**: `pipeline.py` Step 2 Go/Pivot/Drop 판정 로직 정교화 및 `jfsweQpxqsY` Drop 검증
- [ ] **B2B-04 (P3)**: `pipeline.py` Step 3에 `[팀장 보고용 요약]` + `[크리에이터 전달용 가이드]` 2종 출력 포맷 추가
- [ ] **B2B-05 (QA)**: 정답 라벨 골든셋(`qa/golden_set.json`) 구축 및 자동 채점기(`qa/eval_golden.py`) 작성
- [ ] **B2B-06 (Data)**: 7/14/30일 기간 비교 실측 스크립트(`qa/benchmark_days.py`) 실행 및 기본 기간 확정
- [ ] **B2B-07 (UI)**: HTML 및 Streamlit에 [클리핑 Top 10(상승속도·반응률·포맷)] → [시장 패턴] → [Go 카드 + 자막인용 + 2종 복사] → [Drop 접기] 위계 구현
