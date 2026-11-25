---
name: product-build
description: >-
  K-Beauty TrendSetter의 기획·디자인·구현을 맥락 손실 없이 한 번에 수행하는 빌더 스킬.
  docs/POLICY.md 기준과 토스 디자인 시스템(TDS)·UX 라이팅 8원칙을 적용해 기능을 설계·수정·테스트한다.
---

# Product Build 스킬 (기획 + 디자인 + 구현 통합)

## 1. 시작 전 필수 확인
1. `docs/POLICY.md`에서 현재 합격 기준(수집·정렬·S/A/B/C 등급·Go/Pivot/Drop·화장품법 금지어·보안)을 읽는다.
2. `docs/DESIGN_SYSTEM.md`와 `AGENTS.md`의 토스 디자인/UX 라이팅 8원칙을 확인한다.
3. 이번 변경이 "정책(숫자·판정 규칙) 변경"인지 "단순 구현/버그 수정"인지 구분한다. 정책 변경이면 구현과 함께 `docs/POLICY.md`도 현행화한다.

## 2. 설계 및 UX 체크 (코드 쓰기 전 3가지 질문)
1. **문제 해결**: 이 변경이 마케터의 시간(스크린타임)을 실제로 줄여주고 캠페인 결정을 돕는가?
2. **토스 TDS 위계**: 한 화면에 불필요한 입력창·경고창·장식 박스가 쌓이지 않았는가? 핵심 행동 버튼은 1개로 명확한가?
3. **토스 UX 라이팅**: 화면에 개발자 용어(`2-Stage`, `velocity`, `json`, `localStorage`, `confidence` 등), 번역투, 수동형, 군더더기 문장이 없는가?

## 3. 구현 및 자체 검증
1. 백엔드(`agent_core.py`, `pipeline.py`)와 듀얼 UI(`TrendSetter_KBeauty_Pro.html`, `app.py`)의 기준이 어긋나지 않게 함께 반영한다.
2. 수정 후 샌드박스에서 `python -m py_compile`과 `python qa/eval_golden.py`를 실행해 회귀 에러 0건을 확인한다.
3. HTML을 수정했다면, 처음 열었을 때 가짜 결과가 자동 로드되지 않는지, 디버그 로그 패널이 정상 기록되는지 확인한다.

## 4. 종료 조건 (독립 검수 이관)
- 빌더는 스스로 "완료"를 선언하지 않는다.
- 변경 요약과 테스트 결과를 정리해 반드시 **`product-qa` 스킬 기반 독립 검수**로 넘긴다.
