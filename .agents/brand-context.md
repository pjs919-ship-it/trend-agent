# Brand Context

**Last updated:** 2026-11-27

## Brand
- **Name**: 트렌드핏 (TrendFit)
- **Subtitle**: 올리브영 출신 PM이 만든 K-뷰티 마케팅 AI 파트너
- **Category**: K-뷰티 숏폼 트렌드 분석 및 캠페인 기획 AI SaaS
- **Stage**: Phase 1 외부 유저 테스트 (지인·SNS 반응 및 PMF 측정)
- **URL**: Vercel 프로덕션 배포 (`https://trendfit.vercel.app`)

## Audience
- **Primary Audience**: K-뷰티 인하우스 마케터, 브랜드 매니저(BM), 인디 뷰티 대표
- **Key Problem**: 매일 아침 유튜브/SNS를 수동으로 뒤지며 어떤 포맷이 먹히는지, 우리 제품과 맞는 크리에이터가 누구인지 찾는 데 반나절씩 소비
- **Their Language**: 속건조, 수부지, 화잘먹, 톤그로, 갈웜 뮤트, 오가닉, 1초 컷, 후킹 자막, 시딩 DM

## Positioning
- **Differentiation**: 단순 트렌드 조회나 빈 프롬프트 챗봇이 아니라, 실제 K-뷰티 쇼츠 지표(`구독자 수 대비 N배`, `채널 평소 대비 N배`)를 먼저 걸러내고, 제품별 도메인(기초/색조/헤어·바디)과 타겟에 맞는 기획안·카피·시딩 가이드까지 1분 안에 끝냄
- **Anti-Personas**: 근거 없는 의약품·완치 과대광고 카피를 원하는 사용자, 단순 전 업종 유튜버 조회기 사용자

## Brand Personality & Voice
- **Archetype**: 똑똑하고 현장감 있는 K-뷰티 시니어 전략가 (올리브영 출신 PM)
- **Tone**: 능동형 · 짧은 호흡 · 쉬운 한국어 (토스 UX 라이팅 8원칙 준수, 개발자 용어 0건)
- **Visual Tokens**: `#F8F7F4` 웜 스톤 · `#FFFFFF` 서피스 · `#18181B` 잉크 · `#BE185D` 로즈 플럼 · `Pretendard Variable` (`400·500·600`)

## Proof & Guardrails
- **Data Guardrails**: `docs/POLICY.md` 기준 S/A/B/C 바이럴 등급, 화장품법 제13조 절대 금지어 차단, `products.json` 또는 사용자 입력 근거 외 허위 수치 금지
- **Learnings**:
  - Cycle #1: 키워드 검색·불필요 CTA 제거, 중분류▾ 탐색 계층화, 카드 우측 4대 지표 정돈
  - Cycle #2: 카테고리(기초/색조/헤어·바디) ↔ 타겟(피부타입/퍼스널컬러 12톤/두피·바디) MECE 자동 연동
