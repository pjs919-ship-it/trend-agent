# 🚀 Release Notes: K-Beauty TrendSetter Pro (v2.0 — B2B Edition)
**작성 일시**: 2026-11-25 02:22 (PM 노아 중간 릴리즈 기준, 07:00까지 추가 스프린트 예정)  
**대상**: 더랩바이블랑두 (THE LAB by blanc doux) 및 K-뷰티 인하우스 마케터

---

## 1. v1.0 대비 근본적 아키텍처 전환 (B2B Jobs-to-be-Done)
v1.0의 치명적 결함(제목만 보고 브랜드 문구를 날조해 색조 틴트 영상에 토너 5점을 준 가짜 그라운딩)을 폐기하고, **마케터의 실제 업무 4단계(P0→P3)**와 **4단계 독립 감사 파이프라인**으로 전면 재구축했습니다.

1. **P0. 인기 쇼츠 클리핑 & 상승 속도 지표 (`agent_core.py`)**:
   - 색조 오염 키워드 제거 및 기초 스킨케어 앵커 재편, 최대 30일 기간 지원.
   - 총 조회수뿐 아니라 **`일평균 조회수(views_per_day)`**와 **`좋아요 반응률(like_rate)`** 계산 및 복합 속도(`velocity`) 정렬.
   - `qa/usage_log.json` 기반 YouTube 일일 예산 가드(1,500유닛 상한) 탑재.
2. **P1. 편향 없는 시장 팩트 & 관통 패턴 (`pipeline.py` Step 1)**:
   - 브랜드 정보를 완전 차단한 상태에서 자막 원문 인용, `format_tag`(7종), 전체 관통 `market_patterns`(2~3개) 추출.
3. **P2. 냉정한 브랜드 핏 판정 (`pipeline.py` Step 2)**:
   - `products.json`(출처 확인 문구만 수록, 미확인 7스킨·올리브영 1위·2.5mm 제거)과 대조해 **Go / Pivot / Drop** 판정.
   - 하드 가드레일: 영역 불일치(색조 등) 및 `non_fit_territory` 충돌 시 강제 Drop, 자막 미확인(`meta`) 영상은 최대 Pivot(3점) 상한, 2글자 근거 우회 차단.
4. **P3. 2종 즉시 복사 산출물 & 화장품법 제13조 감사 (`pipeline.py` Step 3~4)**:
   - `[팀장/슬랙 보고용 요약]`과 `[인플루언서 DM 발송용 깨끗한 본문(내부 출처·미확인 임상·개발자 파일명 0건)]` 분리 생성.
   - 촬영 연출 타임코드(`첫 3초`)는 허용하고, 화장품법 제13조 의약품/기능성 오인 표현(`완치`, `아토피`, `주름 개선`, `미백`, `1초 컷` 등)은 자동 적발·반려.
5. **B2B 5단 위계 듀얼 UI (`app.py`, `TrendSetter_KBeauty_Pro.html`)**:
   - Executive Summary Strip(4열 KPI) → P1 시장 패턴 → P2+P3 Go 카드(자막 원문 인용·1:1 썸네일·4단 콘티·2종 복사) → Pivot(`⚠️ 자막 미확인`) & Drop(기본 접힘) → P0 원본 Top 10 정렬 뷰.
   - API 쿼터 0으로 즉시 화면 검증 가능한 **스냅샷/리허설 모드** 탑재(실측 조회수 그대로 표기).

---

## 2. 정직한 검증 현황 (02:22 기준)
- **✅ 통과 (오프라인 코어·디자인·레드팀 통합 PASS)**:
  - `python qa/eval_golden.py`: 6대 QA 결함 + 레드팀 RT1~RT4 + 골든셋 15건(Drop 정확도 100%, `jfsweQpxqsY=Drop`, 날조 인용 0건) 전부 통과.
  - `python qa/benchmark_days.py --dry-run`: 904/1,500유닛 예산 내 통과.
  - Designer 8대 디자인 QA 체크리스트 8/8 전항목 PASS.
  - 블랑두 3개 제품(`딥 토너`, `그린 2.5 패드`, `워터리 마스크`) DM 출력 전문 검수 통과.
- **⏸️ 미완료 (외부 네트워크 권한 승인 대기 — 아침에 1회 실행 필요)**:
  - `python qa/benchmark_days.py` (7/14/30일 + `mostPopular` 라이브 실측 비교)
  - `python qa/run_once.py --days 30` (실제 Gemini LLM 콘티 구체성 라이브 E2E 실증)
