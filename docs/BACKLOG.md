# 📋 Product Backlog & Sprint Plan

---

## 🏃 Sprint Overview (오늘 오전 7시 완료 목표)

| 스프린트 | 목표 | 상태 |
|---|---|:---:|
| **Sprint 1: 기반 및 문서화** | Git 원격 저장소 연동, PRD 및 디자인 시스템 수립 | ✅ 완료 |
| **Sprint 2: 수집 엔진 고도화** | 10만+ 조회수 메가 쇼츠 수집 알고리즘 및 블랑두 프리셋 지원 (`agent_core.py`) | 🔄 진행중 |
| **Sprint 3: K-뷰티 Pro HTML 앱** | `TrendSetter (1).html` 능가하는 단독 실행형 웹앱 (`TrendSetter_KBeauty_Pro.html`) | ⏳ 대기 |
| **Sprint 4: Streamlit UI 전면 개편** | `app.py`에 동일 수준의 커스텀 위계 및 카드 컴포넌트 이식 | ⏳ 대기 |
| **Sprint 5: 5대 PMF 지표 검증** | 더랩바이블랑두 3대 제품 테스트, 조회수 및 환각 검증, 최종 릴리즈 | ⏳ 대기 |

---

## 📌 Detailed Backlog Items

### [Sprint 2: Core Engine]
- [x] **TS-101**: K-뷰티 메가 앵커 키워드 및 `Howto & Style` 카테고리(ID 26) 필터 결합
- [x] **TS-102**: 1~10일 기간 내 조회수 상위(수만~수십만 회 이상) 우선 랭킹 알고리즘 구현
- [x] **TS-103**: 더랩바이블랑두 3대 제품(딥 토너, 2.5 패드, 워터리 마스크) 프리셋 템플릿 정의
- [x] **TS-104**: 4단 숏폼 콘티([첫 3초 훅] - [연출] - [소구점] - [CTA]) Pydantic 스키마 설계

### [Sprint 3: Standalone Web App]
- [x] **TS-201**: `TrendSetter (1).html`의 마켓 인사이트, 도트 게이지, 칩, 골든픽 계층 복원
- [x] **TS-202**: 각 트렌드 카드 하단에 근거 영상 썸네일+조회수 1:1 직결 임베드
- [x] **TS-203**: 블랑두 3대 제품 원클릭 버튼 및 맞춤 숏폼 콘티 생성 패널 탑재
- [x] **TS-204**: 원클릭 노션/슬랙 마크다운 요약 복사 및 JSON 다운로드 기능 추가

### [Sprint 4: Streamlit Web Dashboard]
- [x] **TS-301**: Streamlit 기본 마크다운을 대체하는 커스텀 CSS 카드 렌더러 구현
- [x] **TS-302**: 사이드바에 블랑두 3대 제품 원클릭 셀렉터 추가
- [x] **TS-303**: 최신 Gemini 모델(`gemini-2.5-flash-lite`, `gemini-flash-latest`) 자동 연동

### [Sprint 5: PMF Verification]
- [ ] **TS-401**: 조회수 10만+ 영상 필터링 동작 여부 자체 채점
- [ ] **TS-402**: 환각 제로(인용 ID 100% 실존 일치) 무결성 테스트
- [ ] **TS-403**: 최종 Git 커밋 및 릴리즈 노트 작성
