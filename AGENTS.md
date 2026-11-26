# AGENTS.md — K-Beauty TrendSetter 상시 작업 원칙

> **최상위 사명**: "이 제품을 통해 우리는 고객(K-뷰티 마케터)의 문제를 해결하고, 고객에게 고용되어야 한다."

## 1. 단일 기준서 (Single Source of Truth)
- 모든 수집·정렬·등급·매칭·법무·보안 기준은 `docs/POLICY.md`를 따른다.
- 정책서(`docs/POLICY.md`)는 **수치 기준이나 판정 규칙이 바뀔 때만** 업데이트한다. (단순 UI 색상·오타·버그 수정 시 불필요하게 건드리지 않는다.)
- 제품 정보는 `products.json` 또는 사용자 입력 원문만 근거로 삼고, 출처 없는 효능·수치·순위를 지어내지 않는다.

## 2. 디자인 & UX 라이팅 기준 (Toss Design & Writing)
- **컴포넌트 & 레이아웃**: 토스 디자인 시스템(TDS: `Top`, `ListHeader`, `ListRow`, `Badge`, `Border`, `Paragraph`, `Button`, `BottomCTA`)의 깔끔한 여백·시선 흐름·한 화면 한 목적 원칙을 따른다.
  - 참고: `https://developers-apps-in-toss.toss.im/design/components`
  - UI/UX 가이드: `https://developers-apps-in-toss.toss.im/design/consumer-ux-guid`
- **UX 라이팅 8원칙** (`https://toss.tech/article/8-writing-principles-of-toss`):
  1. 다음 화면 예상하기 (`Predictable hint`)
  2. 잡초 제거하기 (`Weed cutting` — 군더더기 수식어 삭제)
  3. 의미 없는 문장 제거하기 (`Remove empty sentences`)
  4. 핵심 메시지에 집중하기 (`Focus on key message` — 개발자 맥락을 다 설명하지 않기)
  5. 소리 내어 읽기 편한 문장 (`Easy to speak` — 능동형, 짧은 호흡, 번역투·수동형 금지)
  6. 강요하지 않고 제안하기 (`Suggest than force`)
  7. 모두가 이해하는 보편적 단어 (`Universal words` — 화면에 개발자 용어·변수명·파일명 0건)
  8. 숨겨진 감정에 공감하기 (`Find hidden emotion`)
- **안티-AI 슬롭 & 비주얼 톤 원칙**:
  - **타이포그래피**: `Pretendard Variable` 웹폰트 + 자간 `-0.02em` + 숫자 `tabular-nums`를 사용해 폰트 크기·굵기·여백으로 정보 위계를 잡는다.
  - **절제된 컬러**: 보라색 그라데이션·과한 알록달록 배지를 금지하고, 모던 K-뷰티 에디토리얼 톤(`#FAF9F6` 배경, `#18181B` 차콜 잉크, `#BE185D` 포인트 1색)을 유지한다.
  - **이모지 도배 금지**: 버튼·탭·리스트 메타에 이모지 대신 단색 라인 SVG 아이콘과 깔끔한 텍스트를 사용한다.
- **다크패턴·가짜 상태 금지**: 사용자가 실행하기 전에 가짜/예시 결과를 미리 띄워두거나 조회수를 부풀리지 않는다.

## 3. 작업 구조 (2+1: 만들기 + 독립 검수)
- 직군을 불필요하게 4개로 쪼개 릴레이하지 않는다.
- **만들기(`.agents/skills/product-build/SKILL.md`)**로 기획·디자인·구현을 맥락 손실 없이 한 번에 처리한다.
- 구현이 끝나면 반드시 **별도 독립 검수(`.agents/skills/product-qa/SKILL.md`)**를 실행한다. 만든 쪽이 스스로 통과 선언을 하지 않는다.
- **최종 관문**: 모든 검수의 마지막은 반드시 **"사람 사용자 기준 검수(UI/UX 유려함 + 직관적 이해 + 실제 문제 해결 여부)"**를 통과해야 한다.

## 4. 보안 및 실행 안전장치
- `.env`와 `local_keys.js`는 `.gitignore`로 영구 차단하며, 코드·문서·보고서에 API 키를 절대 노출하지 않는다.
- 네트워크가 필요 없는 검사(`py_compile`, 로컬 테스트)는 샌드박스 안에서 실행한다.
