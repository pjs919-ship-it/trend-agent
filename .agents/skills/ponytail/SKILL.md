---
name: ponytail
description: DietrichGebert/ponytail 기반의 미니멀 엔지니어링 원칙 ("The best code is the code you never wrote"). 불필요한 추상화·중복·오버엔지니어링을 차단하고 기존 코드·표준 라이브러리·최소 구현으로 문제를 끝낸다.
---

# Ponytail — Lazy Senior Developer Ruleset

> **"The best code is the code you never wrote."**

## The Ladder (코드를 쓰기 전 반드시 위에서 아래로 내려오며 첫 번째 해결책에서 멈춘다)
1. **YAGNI**: 이 기능·추상화가 지금 목표에 꼭 필요한가? 아니면 쓰지 않는다.
2. **Reuse**: 이미 코드베이스에 있는 함수·흐름·데이터를 그대로 재사용할 수 있는가?
3. **Standard Library**: 언어 표준 라이브러리만으로 해결되는가?
4. **Native Platform**: 브라우저(HTML/CSS/DOM)·OS·런타임 기본 기능으로 끝나는가?
5. **Installed Dependency**: 이미 설치된 도구/패키지로 처리되는가?
6. **One Line**: 한 줄 조건/필터로 끝나는가?
7. **Minimum Viable**: 위 모두가 안 될 때만 최소한의 새 코드를 작성한다.

## 절대 타협하지 않는 것
- 안전장치(보안·API 키 차단·데이터 손실 방지·신뢰 경계 입력 검증·법무/화장품법 감사)는 절대 줄이지 않는다. **부풀린 설계(fluff)만 자르고 엄격함(rigor)은 유지한다.**
- 버그를 새 레이어로 덮지 말고, 기존 코드의 원인을 지워 고친다.
