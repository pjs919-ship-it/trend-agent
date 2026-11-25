# 🛡️ 독립 QA 감사 리포트 (QA_REPORT.md)

> **감사관 페르소나**: 7년차 K-뷰티 인하우스 브랜드 마케터(더랩바이블랑두 담당) 겸 독립 QA 감사관  
> **판정 기준 (No-Mercy)**: "이 결과물을 보고 회사 법인카드로 구독료를 내고 고용할 것인가, 아니면 헛소리라고 닫아버릴 것인가"

---

## Sprint 1 독립 QA 검수 — B2B 마케터 관점 코드·파이프라인 감사

- **검수 일시**: 2026-11-25
- **검수 대상**: `agent_core.py`, `pipeline.py`, `products.json`, `qa/run_once.py` (로컬 `cache_store` 14건 및 결정론적 단위 재현 테스트 병행)
- **최종 판정**: **❌ FAIL (반려)**

> **마케터 총평 (WTP 판정)**: 파이프라인 4단계 골격(Step 1 브랜드 분리 → Step 2 규칙+LLM 판정 → Step 3 브리프 → Step 4 코드 감사)과 YouTube API 유닛 가드레일은 올바른 방향이다. 그러나 **실제 더랩바이블랑두 마케터가 법인카드를 긁고 내일 아침 팀장 슬랙과 인플루언서 DM에 바로 복붙해 쓰기에는 치명적 버그와 실무 결함이 6건** 존재한다. 특히 화장품법 위반 과대광고("1등", "3초 만에 즉각 진정", "24시간")를 감사 로직이 0건으로 통과시키면서, 정작 금지 표현 주의사항을 적은 정상 `creator_note`를 위반으로 오탐하는 **자기모순 버그**가 확인되어 즉시 반려한다.

---

### 1. 5대 관점별 냉혹 감사 요약

| 관점 | 판정 | 핵심 발견 사항 |
|---|---|---|
| **(A) P0 클리핑** | ❌ FAIL | `KBEAUTY_MEGA_KEYWORDS[:4][:3]` 이중 슬라이싱으로 기초 핵심 키워드 5개가 죽은 코드화 + 색조 키워드(`메이크업 꿀팁`)에 쿼터 33% 낭비. `min_views` 데드 파라미터. `views` 단독 정렬로 급상승 쇼츠 배제. |
| **(B) Step 1 팩트 & 자막** | ❌ FAIL | 자막 없는 영상(`text_source="meta"`)이 `Go` 및 촬영 가이드까지 무사 통과. `audit_facts`의 `_norm` 매칭이 최소 길이 검증 부재(2글자 통과)와 자동자막 `[음악]`/오타 오탐 위험을 동시에 보유. |
| **(C) Step 2 브랜드 판정** | ❌ FAIL | `기초/스킨케어` 내부의 `non_fit_territory`(모공/각질/미백/클렌징) 코드 가드레일 전무. 반대로 "화잘먹 기초"가 `색조/메이크업` 분류 시 강제 Drop 역효과. `linked_claim` 2글자 부분문자열 우회 가능. |
| **(D) Step 3 2종 브리프** | ❌ FAIL | 인플루언서 DM용 `creator_guide_md`에 개발자 파일명(`products.json`) 노출, `confidence="medium"` 법무 확인 경고 누락, `text_source` 누락, 보고서 기준일/수집기간/업로드일 누락. |
| **(E) Step 4 감사 & 예외** | ❌ FAIL | `_brief_violations`가 `creator_note`까지 검사해 정상 금지안내를 오탐하는 자기모순 버그. `NUM_TOKEN`이 "1위/1등/24시간/10배/즉각 완화" 등 화장품법 과대광고 100% 미탐. `needs_review=True` 시 `internal_report_md` 무경고 노출. |

---

### 2. 구체적 약점 (증거 포함) 및 개선 제안

#### [결함 1 — Critical] Step 4 감사 로직의 자기모순 오탐 + 화장품법 과대광고 100% 미탐
- **위치**: `pipeline.py` L265 (`NUM_TOKEN`), L268-278 (`_brief_violations`)
- **근거 및 재현 증거**:
  1. **자기모순 오탐**: `Storyboard.creator_note`(L116)에 "쓰면 안 되는 표현 포함"을 지시해놓고, `_brief_violations`(L269)는 `b.creator_note`까지 합쳐서 금지 문구 포함 여부를 검사한다.
     - *실제 재현 결과*: `creator_note="주의: 올리브영 1위 토너, 7스킨 레이어링 같은 미확인 표현은 절대 사용 금지"` 입력 시 → `['확인되지 않은 문구 사용: 7스킨 레이어링', '확인되지 않은 문구 사용: 올리브영 1위 토너', '출처 없는 수치 표현: 7스킨']` **3건 위반으로 오탐**되어 불필요한 LLM 재시도 및 `needs_review=True` 오염 발생.
  2. **화장품법 과대광고 미탐**: `NUM_TOKEN`이 `%|ppm|mm|ml|배속|스킨|겹|중`만 감지하여 순위(`1위/1등`), 시간(`3초/24시간`), 배수(`10배`), 판매량(`100만개`), 화장품법 금지 효능(`즉각 완화/완벽 차단/피부과 치료/재생/미백`)을 전혀 못 잡는다.
     - *실제 재현 결과*: `hook="올리브영 1등 수분 토너! 3초 만에 즉각 진정"`, `before="24시간 속건조 고민"`, `product_moment="10배 수분 흡수되는 기적의 토너"`, `cta="지금 1위 제품 구매"` 입력 시 → **`[]` (위반 0건 통과!)**.
- **개선 제안**:
  - `_brief_violations`의 검사 대상을 **시청자 노출 스크립트 4개 필드(`[b.hook, b.before, b.product_moment, b.cta]`)로 한정**하고 `creator_note`는 제외.
  - `NUM_TOKEN`에 `위|등|배|시간|초|분|일|만|억|개` 단위 추가(단, `"첫 3초"`, `"10~20분"`, `"5~10분"`, `"1일 1팩"` 등 연출/사용법 허용 패턴은 화이트리스트 처리).
  - 공통 화장품법 금지 표현 리스트(`1위`, `1등`, `최고`, `즉각`, `완벽`, `치료`, `재생`, `염증 완화`, `기적`, `100%`)를 상수로 두고 `verified_claims`에 명시적으로 없는 경우 무조건 위반 처리.

---

#### [결함 2 — Critical] P0 수집 키워드 이중 슬라이싱으로 기초 핵심 키워드 사망 + 색조 오염 + 저유입 통과
- **위치**: `agent_core.py` L116-125 (`KBEAUTY_MEGA_KEYWORDS`), L217 (`min_views`), L224 & L230, L294 (`days_since_published`), L318-328
- **근거**:
  1. `KBEAUTY_MEGA_KEYWORDS`에 8개를 정의했지만 L224 `[:4]` 후 L230 `[:3]`으로 잘라 실제 실행되는 키워드는 `["올리브영 추천템", "스킨케어 꿀조합", "메이크업 꿀팁"]` 3개뿐이다. 더랩바이블랑두 핵심 키워드인 `"피부 뒤집어졌을때"`, `"화잘먹 기초 루틴"`, `"올영 세일 쟁여템"`은 **영원히 실행되지 않는 죽은 코드**이며, 300유닛 중 100유닛(33%)을 대놓고 색조 키워드(`"메이크업 꿀팁"`)에 낭비한다.
  2. L217의 `min_views: int = 10000`은 함수 내에서 **단 한 번도 사용되지 않는 데드 파라미터**다. 대신 L318-320에서 `5000`을 하드코딩하고 `if len(high_impact) >= 5` 조건을 두어, 5건 미만이면 조회수 162회·1,009회짜리 저유입 영상도 그대로 Top 10에 통과된다(로컬 `cache_store`의 `히알루론산` 7일 데이터에서 실제 확인).
  3. L294 `max(1, (now_utc - pub_dt).days)`는 정수 내림이라 47시간 전 영상도 1일로 계산되어 `views_per_day`가 최대 2배 과대계상된다. 또한 L328이 총 `views` 단독 정렬이라 30일 수집 시 어제 터진 급상승 쇼츠(일평균 8만)가 29일 전 정체 영상(누적 10만)에 밀려 탈락한다.
- **개선 제안**:
  - 제품 카테고리(기초 스킨케어) 맞춤 앵커 키워드 프리셋을 분리하고(`"올리브영 스킨케어 추천"`, `"피부 뒤집어졌을때"`, `"화잘먹 기초 루틴"` 등) 불필요한 `[:4]`/`[:3]` 이중 슬라이싱 제거.
  - `min_views` 파라미터를 실제로 적용하되, 기준 미달 영상이 포함될 경우 `low_views_fallback: True` 플래그를 기록해 마케터에게 투명하게 고지.
  - `days_since_published = max(1.0, (now_utc - pub_dt).total_seconds() / 86400)`로 정밀화하고, 정렬 기준을 `views_per_day` 우선 또는 `(views_per_day * 0.6 + views * 0.4)` 급상승 가중 정렬 옵션으로 개선.
  - `pipeline.py`에서 `views_per_day`, `like_rate`가 누락된 캐시 입력이 들어와도 `published_at` 기반으로 안전하게 재계산하도록 방어 로직 추가(현재 L373은 `views` 전체를 일평균으로, L431은 `0`으로 불일치 출력).

---

#### [결함 3 — Critical] 자막 없는 영상(`text_source="meta"`)의 Go 판정 및 촬영 가이드 무사 통과
- **위치**: `pipeline.py` L67-73, L174-200 (`audit_facts`), L210-217 (`judge_fit`), L419-448 (`creator_guide_md`)
- **근거**:
  1. 자막이 없는 영상(`text_source="meta"`)도 제목 한 줄만 인용하면 `audit_facts`에서 `evidence_ok=True`를 받는다.
  2. `judge_fit`(L210-217)은 `text_source`를 LLM 프롬프트에 아예 넘기지 않으며 코드 가드레일도 없다. 따라서 자막이 없어 실제 영상 내용을 모르는 쇼츠가 **5점 `Go` 판정 → 촬영 콘티 생성**까지 통과한다.
  3. `creator_guide_md`(L419-448)에는 `text_source` 표기가 아예 없어, 인플루언서에게 자막도 확인 안 된 레퍼런스가 검증된 것처럼 전달된다.
- **개선 제안**:
  - `judge_fit`에서 `f["text_source"] != "caption"`인 경우 **코드 가드레일로 최대 `Pivot`(3점) 상한 적용** (자막 미확인 영상은 자동 Go 금지, 마케터가 직접 시청 후 승격하는 구조).
  - 부득이하게 `meta` 영상을 노출할 경우 `internal_report_md`와 `creator_guide_md` 양쪽에 `⚠️ [자막 미확인 — 영상 직접 시청 필수]` 경고를 강제 삽입.

---

#### [결함 4 — High] Step 2 브랜드 판정의 `non_fit_territory` 미차단 및 `linked_claim` 우회 허점
- **위치**: `pipeline.py` L233, L244-254 (`judge_fit`), L210 (`usable` 필터링)
- **근거**:
  1. **기초 내부 부적합 영역 미차단**: 규칙 1(L244)은 `domain != "기초/스킨케어"`만 잡는다. `products.json`에 명시된 `non_fit_territory`(그린 패드: `"각질 제거"`, `"미백 광고성 표현"` / 워터리 마스크: `"모공/피지 집중 케어"`)에 해당하는 기초 영상(예: 블랙헤드 클렌징, 각질 필링 패드, 기미 미백 앰플)에 대한 코드 차단/강등 로직이 없어 경량 LLM(`gemini-2.5-flash-lite`)의 오판에 그대로 노출된다.
  2. **"화잘먹 기초" 역오탐 위험**: 쿠션/파운데이션이 후반에 등장하는 "메이크업 전 기초 루틴" 영상이 Step 1에서 `색조/메이크업`으로 분류되면, 더랩바이블랑두 핵심 `fit_territory`("메이크업 전 수분/진정 루틴")임에도 규칙 1에 의해 무조건 `Drop(1점)` 처리된다.
  3. **`linked_claim` 2글자 우회**: L250 `_norm(j.linked_claim) in claims_blob`은 최소 길이 검증이 없어 LLM이 `"토너"` 2글자만 반환해도 `linked_ok=True`로 Go 통과(단위 테스트로 `True` 재현 확인). 또한 모든 클레임을 하나로 합쳐 비교하므로 문구 경계 이어붙이기도 통과된다.
  4. **근거 불충분 영상의 조용한 증발**: L210 `usable = [f for f in facts if f["evidence_ok"]]`로 탈락한 영상이 `judgements`에서 누락되어, 보고서 상단 `총 10건`과 `Go+Pivot+Drop 합계`가 불일치한다.
- **개선 제안**:
  - `non_fit_territory` 핵심 키워드(예: `각질`, `필링`, `미백`, `기미`, `잡티`, `모공`, `블랙헤드`, `피지`, `클렌징`)가 `what_happens`/`product_types`에 등장하면 코드에서 `non_fit` 충돌 플래그를 세우고 `Go` 차단(최대 Pivot 또는 Drop).
  - Step 1 도메인에 `"기초+메이크업 연계(화잘먹)"` 구분 또는 `product_types`에 기초 제품군이 포함되고 `fit_territory`에 `"메이크업 전"`이 있는 경우 예외 허용 규칙 검토.
  - `linked_claim` 검증 시 `claims_blob` 단일 문자열 대신 **개별 `verified_claims` 항목별 매칭 + `_norm(linked_claim)` 최소 8자 이상** 조건 적용(또는 `C1`, `C2` ID 참조 방식 도입).
  - `evidence_ok=False` 영상은 `judgements`에 `decision="Drop"`, `score=1`, `reason="[자동 제외] 원문 자막/텍스트 근거 검증 실패"`로 명시 포함해 보고서 합계 정합성 100% 보장.

---

#### [결함 5 — High] 2종 즉시 복사 산출물(`internal_report_md`, `creator_guide_md`)의 실무 결함
- **위치**: `pipeline.py` L321-452 (`format_copyable_outputs`), L286-299 (`write_briefs`)
- **근거**:
  1. **개발자 용어 노출**: `creator_guide_md` L421에 ``확인된 제품 정보(`products.json`)``라는 내부 파일명이 그대로 들어가 있어 인플루언서/대행사 DM에 바로 복붙할 수 없다.
  2. **제품 정보 신뢰도(`confidence="medium"`) 및 임상 조건 경고 누락**: `products.json`에 명시된 `"웹 검색 요약 기반(confidence=medium)"` 및 워터리 마스크의 `"시험 조건 미확인 — 광고 사용 전 원문 확인 필요"` 경고가 2종 보고서 어디에도 출력되지 않는다.
  3. **`needs_review=True` 시 `internal_report_md` 무경고 노출**: L386-388에서 위반이 남은 브리프의 `hook`/`product_moment`를 경고 표시 없이 팀장 보고서에 그대로 노출한다. `creator_guide_md`도 맨 아래 한 줄 경고만 있어 실수 발송 위험이 높다.
  4. **실무 필수 메타데이터 누락**: `internal_report_md`에 **보고 기준일·수집 기간(`days`)·영상 업로드일(`published_at`)**이 빠져 있고, `creator_guide_md`에 **권장 길이/비율, 사용 가능 확인 소구점, 광고 표시 의무(`#광고/#협찬`)**가 빠져 있다.
  5. **`write_briefs` 입력 정보 부족**: L286-289에 `format_tag`와 `evidence_quote`가 누락되어 바이럴 포맷 구조를 살린 구체적 컷 연출이 나오기 어렵고, 추상적 콘티 금지 지시도 없다.
- **개선 제안**:
  - `creator_guide_md`에서 `products.json` 문구 제거 → `"공식 확인된 제품 정보 기준"`으로 순화.
  - `product_confidence != "high"`일 때 두 문서 상단에 `⚠️ [제품 정보 확인 필요] 현재 제품 문구는 요약 기반(medium)입니다. 최종 광고 집행 전 공식 상세페이지 원문 및 임상 조건을 확인하세요.` 배너 삽입.
  - `needs_review=True`인 브리프는 `internal_report_md`와 `creator_guide_md` 모두 해당 항목 최상단에 `🚨 [발송 보류 — 검수 필요]` 경고 표시.
  - 보고 기준일, 수집 기간, 영상 업로드일, `format_tag` 기반 촬영 체크리스트 추가. `write_briefs` 프롬프트에 `format_tag`와 `evidence_quote` 전달 및 "구체적 화면 구도·소품·대사/자막 텍스트 필수, 추상적 문구 금지" 명시.

---

#### [결함 6 — Medium] 코드 위생 및 부가 버그
- **위치**: `pipeline.py` L313-315, `agent_core.py` L22
- **근거**:
  1. `pipeline.py` L314 `if vid not in facts: continue` — LLM이 Go가 아닌 영상의 ID를 반환해도 `facts`에 있으면 브리프에 포함된다(`go_ids` 집합으로 검증해야 함).
  2. `agent_core.py` L22 `from langchain_community.document_loaders import YoutubeLoader` — 미사용 dead import.
- **개선 제안**: `go_ids = {g["video_id"] for g in go_items}`로 필터링 수정, 미사용 import 정리.

---

### 3. Sprint 2 PASS 통과 조건 (재검수 체크리스트)
1. [ ] `_brief_violations`에서 `creator_note` 제외 + 화장품법 과대광고 수치/표현(1위/1등/시간/배수/즉각/치료 등) 검출 단위 테스트 통과
2. [ ] `KBEAUTY_MEGA_KEYWORDS` 기초 스킨케어 중심 재편 및 `[:4][:3]` 이중 슬라이싱·`min_views` 데드 파라미터 수정
3. [ ] `text_source="meta"` 영상의 Go 자동 차단(Pivot 상한) 및 자막 미확인 경고 양쪽 산출물 표기
4. [ ] `non_fit_territory` 코드 가드레일 추가 + `linked_claim` 개별 매칭(최소 길이 8자) + `evidence_ok=False` 영상의 Drop 명시로 합계 정합성 100% 확보
5. [ ] `creator_guide_md`의 `products.json` 노출 제거, `confidence="medium"` 경고 배너, `needs_review=True` 상단 경고 배너, 기준일/수집기간/업로드일 추가
6. [ ] 실제 캐시 또는 신규 수집 데이터 1회 E2E 실행 결과(`qa/run_latest.json`)를 마케터 눈으로 직접 검수하여 색조(`jfsweQpxqsY` 포함) Drop ≥ 90%, 날조 인용 0건, 과대광고 0건 실증


---

## Sprint 2 독립 QA 재검수 — 회귀 검증 + 레드팀 감사 + 복사 산출물 전문 검수

- **검수 일시**: 2026-11-25
- **검수 대상**: `agent_core.py`, `pipeline.py`, `qa/golden_set.json`, `qa/eval_golden.py`
- **실행 검증**: 샌드박스(`BypassSandbox=false`)에서 `python qa/eval_golden.py` 직접 실행 + `format_copyable_outputs()` 전문 출력 검수 + 레드팀 4대 공격 테스트 실행
- **최종 판정**: **❌ FAIL (Sprint 1 6대 결함은 전부 해결되었으나, 레드팀 테스트 및 복사 산출물 전문 검수에서 월요일 아침 즉시 복붙 발송을 막는 4건의 잔여 결함 발견)**

> **마케터 총평 (월요일 아침 9시 법인카드 결제 테스트)**:  
> Sprint 1의 6대 결함이 전부 수정되었고 `qa/eval_golden.py` 회귀 테스트(`ALL TESTS PASSED!`, 적대적 LLM 대상 Drop 정확도 100%, `jfsweQpxqsY` 강제 Drop)가 깔끔하게 통과한 점은 높이 평가한다. 그러나 **실제 `creator_guide_md` 출력 전문을 읽어본 결과, 인플루언서 DM에 그대로 복붙하면 브랜드 신뢰도가 추락하는 내부 요약 주석(`(kurly, glowpick 요약)`, `(costco, glowpick 요약)`)이 노출**되고 있으며, 레드팀 테스트에서 **정상 숏폼 훅(`"첫 3초: ..."`)이 과대광고로 오탐**되고 반대로 **화장품법 제13조 의약품 오인 표현(`"여드름 완치"`, `"아토피"`, `"주름 개선"`, `"미백"`)이 0건으로 무사 통과**하는 구멍이 확인되었다. 이 4건을 해결하기 전까지는 법인카드 결제 기준 **FAIL**이다.

---

### 1. Sprint 1 6대 결함 회귀 검증 결과 (`python qa/eval_golden.py` 직접 실행)
- **실행 결과**: `Command exited with code 0` / `ALL TESTS PASSED!`
- **골든셋 15건 오프라인 채점**: `expected_drops=11`, `drop_hits=11` (**Drop 정확도 100.0%**), `jfsweQpxqsY_decision="Drop"`, `fabricated_quote_blocked=true`, `meta` 영상(`RdXhzcCVtsw`) `Pivot` 상한 적용 확인.
- **확인 완료**: `creator_note` 자기모순 제거, `KBEAUTY_MEGA_KEYWORDS` 기초 중심 개편, `47h` float `views_per_day`, 1,500유닛 상한 가드, `go_ids` 필터링, `evidence_ok=False` 증발 방지.

---

### 2. 레드팀 감사 및 복사 산출물 전문 검수에서 발견된 잔여 약점 (증거 포함)

#### [잔여 결함 1 — Critical] `creator_guide_md` 대외 발송 불가 문구 노출 (인플루언서 DM 복붙 불가)
- **위치**: `pipeline.py` L640-641, L672-676 (`format_copyable_outputs`)
- **근거 (실제 출력 전문 확인)**:
  - `creator_guide_md` 하단 `### [참고] 공식 확인된 제품 소구 포인트`에 `products.json`의 내부 리서치 출처 메모와 제3자 어투가 그대로 출력된다:
    - `- 저분자 히알루론산 워터 제형 토너 (blancdoux.com, kurly, glowpick 요약)`
    - `- 끈적임·겉도는 느낌이 적고 속건조 케어를 내세움 (kurly, glowpick 요약)`
    - `- 민감성 포함 모든 피부 타입 사용 가능으로 소개 (costco, glowpick 요약)`
  - 인하우스 마케터가 인플루언서/대행사 DM에 `"속건조 케어를 내세움 (kurly, glowpick 요약)"`이라고 보내면 **"본인 회사 제품을 컬리·코스트코 요약 보고 썼느냐"**는 비웃음을 산다.
  - 또한 상단 `conf_banner`도 마케터 내부 확인용 경고인데 크리에이터 가이드 본문 최상단에 그대로 들어가 있어, 실수로 함께 복붙 발송할 위험이 높다.
- **개선 제안**:
  - `creator_guide_md`에 소구 포인트를 출력할 때 괄호 출처 주석(`(blancdoux.com, ... 요약)` 등)을 정규식으로 제거하거나, `products.json`에 대외용 정제 문구(`public_claims` 또는 전처리 함수 `_clean_claim_for_creator()`)를 적용.
  - `conf_banner`가 `creator_guide_md`에 들어갈 경우 `[마케터 내부 확인 — 크리에이터 전달 전 본 박스 삭제 필수]` 문구를 명시적으로 표기.

---

#### [잔여 결함 2 — Critical] `_brief_violations`의 정상 숏폼 훅(`"첫 3초"`) 오탐 + 화장품법 제13조 의약품 오인 표현 미탐
- **위치**: `pipeline.py` L422-427 (`NUM_TOKEN`, `COSMETIC_LAW_BANNED_TERMS`), L430-442 (`_token_in_claims`)
- **근거 (레드팀 재현 증거)**:
  1. **정상 숏폼 연출 오탐 (`RT1`)**: `Storyboard.hook` 자체가 `"첫 3초: 화면/행동/자막"`을 요구하는데, 실제로 `hook="첫 3초: 화장솜에 토너를 듬뿍 적시는 클로즈업"`을 입력하면 **`['출처 없는 수치 표현: 3초']`로 위반 오탐**된다! 실제 LLM이 콘티를 쓸 때마다 불필요한 재시도와 `needs_review=True` 오염이 대량 발생할 치명적 버그.
  2. **의약품 오인·미인증 기능성 과대광고 미탐 (`RT2`)**: `hook="올영 랭킹 1등! 여드름 완치 수준으로 가라앉는 토너"`, `before="아토피 피부염으로 붉어진 얼굴"`, `product_moment="피부과 시술 없이 모공 축소, 주름 개선, 미백 효과 확실"`, `cta="품절 대란 베스트셀러 지금 구매"` 입력 시 → `1등`만 잡히고 **`여드름 완치`, `아토피`, `피부염`, `시술`, `모공 축소`, `주름 개선`, `미백`, `베스트셀러`가 전부 미탐 통과!**
- **개선 제안**:
  - 연출 지시어 화이트리스트 패턴(예: `첫\s*\d+\s*초`, `초반\s*\d+\s*초`, `\d+\s*초\s*컷`, `\d+\s*초\s*후` 등 영상 타임코드/연출 지시)은 `NUM_TOKEN` 수치 위반에서 제외(단 `"3초 만에 진정"` 같은 효능 시간 표현은 계속 차단).
  - `_token_in_claims`의 범위 표기 정규식을 시작값(`15~20분`의 `15분`)뿐 아니라 끝값(`20분`)도 대칭적으로 검증하도록 보강.
  - `COSMETIC_LAW_BANNED_TERMS`에 화장품법 제13조 핵심 위반어(`완치`, `아토피`, `피부염`, `시술`, `모공 축소`, `주름 개선`, `미백`, `여드름 치료`, `트러블 완치`, `베스트셀러`, `랭킹`, `품절 대란`) 추가.

---

#### [잔여 결함 3 — High] 자동자막 `[음악]` 태그 오탐(`audit_facts`) 및 `"각질 부각"` 문맥 오탐 Drop(`_find_non_fit_hits`)
- **위치**: `pipeline.py` L52-54 (`get_transcript`), L208-212 (`audit_facts`), L259 (`NON_FIT_KEYWORD_MAP`)
- **근거 (레드팀 재현 증거)**:
  1. **자막 노이즈 태그 오탐 (`RT3`)**: 실제 YouTube 자동자막에 빈번한 `[음악]`, `[박수]`가 문장 중간에 있을 때(`"오늘 피부가 [음악] 너무 당겨서 토너팩 해봤어요"`), LLM이 `[음악]`을 빼고 정상 인용하면 `audit_facts`가 **`evidence_ok=False`로 오탐 탈락**시킴(재현 확인: `False`).
  2. **정상 기초 영상 오탐 Drop (`RT4`)**: `그린 플라보노이드 2.5 패드`의 `non_fit_territory="각질 제거"` 때문에 `NON_FIT_KEYWORD_MAP`에 단일어 `"각질"`이 들어가 있어, `"화장 전 건조해서 각질 부각될 때 진정 패드로 5분 팩하기"` 같은 **최상급 Go(5점) 수분/진정 영상이 `non_fit` 충돌로 강제 Drop**됨(재현 확인: `Drop`).
- **개선 제안**:
  - `get_transcript` 및 `audit_facts` 정규화 전에 `re.sub(r"\[[^\]]{1,15}\]", " ", text)`로 `[음악]`/`[박수]` 등 비음성 태그를 제거.
  - `NON_FIT_KEYWORD_MAP["각질"]`에서 단일어 `"각질"`을 제거하고 `"각질제거"`, `"각질 제거"`, `"각질 케어"`, `"필링"`, `"스크럽"`, `"아하"`, `"바하"`, `"bha"`, `"aha"`처럼 각질 제거 행위/성분 키워드만 매칭하도록 정밀화.

---

#### [잔여 결함 4 — Medium / 다음 스프린트 과제] 실제 LLM & YouTube API E2E 실증 미완
- **근거**: `qa/eval_golden.py`는 사람이 작성한 `sample_fact`와 Mock LLM으로 결정론적 가드레일만 검증했다. 실제 `gemini-2.5-flash-lite`가 생성하는 콘티의 구체성(절대 기준 4: 뻔한 문장 금지)과 7/14/30일 실측 수집 품질(PRD 수용 기준 5)은 외부 API 권한 승인 후 반드시 E2E 1회 실행(`qa/run_once.py`)으로 실증해야 한다.

---

### 3. Sprint 3 PASS 통과 조건 (단기 수정 체크리스트)
1. [ ] `creator_guide_md`에서 `(blancdoux.com, kurly, glowpick 요약)` 등 내부 출처 주석 제거 + 마케터 발송 전 삭제 안내 문구 분리
2. [ ] `_brief_violations`에서 `"첫 3초"` 등 숏폼 연출 타임코드 오탐 방지 + 화장품법 제13조 의약품 오인/미인증 기능성 금지어(`완치/아토피/시술/주름 개선/미백/베스트셀러` 등) 검출 테스트 추가
3. [ ] 자막 `[음악]`/`[박수]` 태그 전처리 + `NON_FIT_KEYWORD_MAP["각질"]`에서 `"각질 부각"` 정상 영상 오탐 Drop 방지 테스트 추가
4. [ ] (외부 API 권한 확보 시) `qa/run_once.py` 라이브 E2E 1회 실행 및 결과물 마케터 검수


---

## Sprint 2-R 최종 QA 재검수 — 레드팀 결함 수정 검증 & 대외 DM 전문 최종 감사

- **검수 일시**: 2026-11-25
- **검수 대상**: `pipeline.py`, `qa/eval_golden.py`, `creator_dm_clean_md` (3개 제품 전체 출력 전문)
- **실행 검증**: 샌드박스(`BypassSandbox=false`)에서 `python qa/eval_golden.py` 직접 실행 + 3개 제품(`올리고 히알루론산 딥 토너`, `그린 플라보노이드 2.5 패드`, `올리고 히알루론산 워터리 스킨 마스크`)의 `creator_dm_clean_md` 출력 전문 직접 검수
- **최종 판정**: **✅ PASS — 오프라인 코어 게이트 PASS (단, 외부 API 권한 승인 후 라이브 E2E 실증 대기 조건부)**

> **마케터 총평 (월요일 아침 9시 복붙 테스트)**:  
> Sprint 1의 6대 결함과 Sprint 2 레드팀 4대 결함이 모두 코드와 자동 회귀 테스트(`qa/eval_golden.py`)로 완벽히 봉합되었다. 특히 `creator_guide_md`(마케터 내부 확인 블록 + 구분선)와 `creator_dm_clean_md`(순수 대외 복붙 본문)의 2단 분리, `(blancdoux.com, kurly, glowpick 요약)` 등 내부 출처 주석 및 제3자 어투(`~내세움`, `~소개`) 자동 정제 결과는 **실제 인플루언서 DM에 바로 붙여넣어도 창피하지 않은 실무 품질**에 도달했다. 오프라인 코어 엔진·가드레일·복사 산출물 게이트는 **PASS**로 승인하며, 이제 UI 통합(Sprint 3) 및 외부 API 권한 확보 후 라이브 E2E 1회 실증으로 넘어갈 준비가 완료되었다.

---

### 1. 검증 결과 요약
- **`python qa/eval_golden.py` 직접 실행**: `Command exited with code 0` / `ALL TESTS PASSED!`
  - `Defect 1~6` 전부 PASS (`clean=0`, `overclaim=14 violations caught`)
  - `Red-Team RT1~RT4` 전부 PASS (`RT1` 연출 타임코드/1초컷 구분, `RT2` 화장품법 제13조 9종 차단, `RT3` `[음악]` 태그 전처리, `RT4` `"각질 부각"` Go 유지)
  - 골든셋 15건 오프라인 자동 채점: `expected_drops=11`, `drop_hits=11` (**Drop 정확도 100.0%**), `jfsweQpxqsY=Drop`, `fabricated_quote_blocked=true`, `meta→Pivot` 상한 유지.
- **3개 제품 `creator_dm_clean_md` 출력 전문 검수**:
  - 내부 출처 괄호 주석(`blancdoux.com`, `kurly`, `glowpick`, `costco`, `hwahae` 등) 0건 노출 확인.
  - 개발자 파일명(`products.json`) 0건 노출 확인.
  - 권장 규격(9:16, 20~45초), 필수 광고 표기(`#광고`/`#협찬`), 금지 문구, 공식 확인 소구 포인트가 자연스러운 한국어 실무 톤으로 정리됨.

---

### 2. 다음 스프린트(UI 통합 & 라이브 E2E)를 위한 잔여 개선 포인트 3가지
*(오프라인 코어 PASS를 막는 치명적 결함은 아니나, B2B 구독 전환율과 법무 안전성을 100%로 끌어올리기 위한 백로그)*

1. **[법무 디테일] `워터리 스킨 마스크` 미확인 임상 조건 문구 처리 (`pipeline.py` L532-544)**
   - `products.json` 원문의 `"1회 사용 직후 깊은 수분 개선율 111.25% 임상 (blancdoux.com 요약, 시험 조건은 미확인이므로 광고 문구 사용 전 원문 확인 필요)"`에서 `_INTERNAL_SOURCE_PAREN_RE`가 괄호를 통째로 제거하면서 `creator_dm_clean_md`에 `- 1회 사용 직후 깊은 수분 개선율 111.25% 임상`이 조건 경고 없이 노출된다.
   - **제안**: 화장품 표시광고법상 임상 수치 인용 시 시험 조건 병기가 필수이므로, `"시험 조건은 미확인"`이 포함된 클레임은 `creator_dm_clean_md`에서 제외하거나 `(공식 상세페이지 임상 조건 확인 후 사용)` 주석을 유지할 것.
2. **[문구 정제] `절대 사용 금지 문구` 내 v1 정정 메모 괄호 정리 (`products.json` / `pipeline.py` L709-710)**
   - `creator_dm_clean_md`의 금지 문구 줄에 `식물성 초밀착 시트(대나무 유래로 정정)`, `열감 내리는 효과(단정 표현)` 등 내부 v1 정정 메모가 괄호로 남아 있다.
   - **제안**: 대외 DM 출력 시 `(대나무 유래로 정정)` 같은 내부 수정 이력 괄호를 제거해 인플루언서 가독성을 높일 것.
3. **[UI 안전장치 & 라이브 E2E 필수]**
   - **UI 안전장치**: `needs_review=True`인 브리프가 포함되었을 때, Streamlit UI에서 `creator_dm_clean_md` 원클릭 복사 버튼을 비활성화하거나 빨간 경고 배너를 띄워 실수 발송을 원천 차단할 것.
   - **라이브 E2E 실증 (최종 출고 필수 조건)**: 외부 API 권한 확보 후 `qa/run_once.py`로 실제 YouTube 수집(7/14/30일 비교) + 실제 `gemini-2.5-flash-lite` E2E 1회 실행 결과를 검수해 **실제 생성 콘티의 구체성(절대 기준 4)**과 **수집 품질(PRD 기준 5)**을 최종 확정할 것.


---

## Sprint 5 통합 레드팀 QA 검수 — 블랑두 3개 제품 전체 + Streamlit/HTML UI + DM 디테일

- **검수 일시**: 2026-11-25
- **검수 대상**: `pipeline.py`, `app.py`, `TrendSetter_KBeauty_Pro.html`, `qa/eval_golden.py`, `qa/benchmark_days.py`, `products.json` (3개 제품 전체)
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`**
  - `python qa/benchmark_days.py --dry-run` → `exit code 0` / **`DRY-RUN PASS!`** (예상 904 / 1,500유닛 예산 내)
  - 블랑두 3개 제품(`올리고 히알루론산 딥 토너`, `그린 플라보노이드 2.5 패드`, `올리고 히알루론산 워터리 스킨 마스크`) 전체 `creator_dm_clean_md` 생성 및 전수 육안 검수
- **최종 판정**: **✅ PASS — 오프라인 통합 게이트 PASS (라이브 E2E & 7/14/30일 실측 벤치마크 대기 조건부)**

> **마케터 총평**:  
> 블랑두 3개 제품 전체의 `creator_dm_clean_md`에서 미확인 임상 수치(`111.25%`)와 내부 괄호 메모(`대나무 유래로 정정`, `단정 표현`, `요약`)가 **완벽히 0건**으로 정리되었다. `app.py`는 모든 동적 필드에 `html.escape` XSS 방어와 `needs_review` DM 복사 `confirm()` 가드를 갖췄으며, `TrendSetter_KBeauty_Pro.html`도 근거 없는 문구(7스킨·올리브영 1위·2.5mm)를 제품 소구점에서 완전 제거하고 2-Stage 분리 호출과 클라이언트 강제 Drop을 구현했다. 오프라인 제품 통합 게이트는 **PASS**로 승인한다. 단, 아래 레드팀 발견 약점 3건(특히 HTML 샘플 조회수 실측치 통일 및 HTML LIVE 수치 감사 패리티)은 다음 패치에 반영하고, 대외 출고 전 라이브 E2E 1회 실증을 완료해야 한다.

---

### 1. 블랑두 3개 제품 실사용 DM 리허설 검수 결과

| 제품명 | 미확인 임상(`111.25%`) | 내부 괄호(`정정`/`단정 표현`/`요약`) | 금지 문구 정제 | DM 복붙 적합성 |
|---|---|---|---|---|
| **올리고 히알루론산 딥 토너** | 0건 | 0건 | 4종 깔끔 표기 | ✅ 즉시 발송 가능 |
| **그린 플라보노이드 2.5 패드** | 0건 | 0건 | `3중 레이어 거즈 패드, 붉은기 즉각 완화` | ✅ 즉시 발송 가능 |
| **올리고 히알루론산 워터리 스킨 마스크** | **0건 (제외 완료)** | 0건 | `식물성 초밀착 시트, 열감 내리는 효과` | ✅ 즉시 발송 가능 |

---

### 2. 레드팀 통합 감사에서 발견된 잔여 약점 3가지 (증거 포함) 및 개선 제안

#### [약점 1 — Medium] `TrendSetter_KBeauty_Pro.html` LIVE 모드의 감사 패리티 부족 (`NUM_TOKEN` 누락 & `meta` 표기 부정확)
- **위치**: `TrendSetter_KBeauty_Pro.html` L396-408 (`checkBriefViolations`), L504 & L536-550 (`runLive2Stage`), L705
- **근거**:
  1. `checkBriefViolations`(L396-408)가 `prod.banned`와 `COSMETIC_BANNED`만 검사하고, `pipeline.py`에 있는 `NUM_TOKEN` 출처 없는 수치 검사(`24시간 보습`, `10배 흡수`, `3초 만에 진정` 등)가 빠져 있다.
  2. 브라우저 LIVE 모드는 CORS 제약상 모든 영상이 `text_source: "meta"`로 수집되는데(L504), `evidence_ok=False` 강제 Drop이 없고 L705에는 `meta` 영상에도 `"💬 실제 영상 원문 인용 / 100% 원문 대조 통과"`가 고정 출력된다.
- **개선 제안**: `checkBriefViolations`에 `NUM_TOKEN` + `DIRECTION_TIME_RE` 로직을 동일 이식하고, `evidence_ok=False` 강제 Drop 및 LIVE 모드 상단에 `"브라우저 모드는 제목·설명(meta) 기반입니다. 자막 정밀 검증은 Streamlit 또는 JSON 로드를 사용하세요"` 안내 배너 추가.

#### [약점 2 — Medium] `TrendSetter_KBeauty_Pro.html` 샘플 리허설 데이터의 조회수 임의 부풀림
- **위치**: `TrendSetter_KBeauty_Pro.html` L600-602 (`loadSampleRehearsal`)
- **근거**:
  - 실제 `qa/golden_set.json`(로컬 캐시 실측)에서 `brKNpouibqo`=1,187회, `Zl5CPQxmWFE`=162회, `RdXhzcCVtsw`=1,009회인데, HTML 샘플에서는 각각 `118,700회`(100배), `84,200회`(520배), `62,400회`(62배)로 부풀려져 있다.
  - `app.py`는 실측치를 정직하게 표시하는 반면 HTML 샘플만 부풀려져 있어, 마케터가 `쇼츠 보기 ↗` 링크를 클릭했을 때 실제 조회수와 100배 차이가 나면 신뢰도가 훼손된다.
- **개선 제안**: `loadSampleRehearsal()`의 조회수·좋아요를 `qa/golden_set.json`의 실측치로 통일(또는 실제 고조회수 캐시 확보 후 교체).

#### [약점 3 — Low/UX] `app.py` 사이드바 제품 변경 시 리허설 화면 미자동갱신 및 죽은 줄
- **위치**: `app.py` L292, L405-409
- **근거**:
  - 사이드바에서 대상 제품을 변경해도 `🧪 스냅샷/리허설 보기` 버튼을 다시 누르기 전까지 이전 제품 결과가 그대로 유지된다.
  - L292 `videos = [pipeline._ensure_video_metrics(it) for it in gs_items[:10]]`가 L297에서 즉시 덮어씌워지는 죽은 코드다.
- **개선 제안**: `_mode != "live"` 상태에서 `selected_product`가 변경되면 리허설 결과를 자동 갱신하고 L292 제거.

---

### 3. 최종 출고 전 남은 필수 검증 (외부 API 권한 확보 후)
1. [ ] `python qa/benchmark_days.py` 실측 실행 → 7/14/30일 + `mostPopular` 데이터로 최적 기본 기간 확정 (PRD 수용 기준 5)
2. [ ] `python qa/run_once.py` 라이브 E2E 1회 실행 → 실제 `gemini-2.5-flash-lite`가 생성한 콘티의 구체성(절대 기준 4) 최종 육안 검수


---

## Sprint 6 레드팀 QA 검수 — B2B-08 제품 3종 교차 매칭 매트릭스

- **검수 일시**: 2026-11-25
- **검수 대상**: `pipeline.py` (`build_multi_product_matrix`, `_deterministic_judgements_for_product`, `format_copyable_outputs`), `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`** (`B2B-08 Multi-Product Matrix` 포함)
  - 골든셋 15건 기준 `build_multi_product_matrix()` 실행 + `internal_report_md`의 `### 🔀 제품 3종 교차 매칭 요약` 전문 출력 및 모순 점검
- **최종 판정**: **✅ PASS**

> **마케터 총평**:  
> 추가 YouTube 쿼터 0·추가 LLM 비용 0으로 더랩바이블랑두 3개 시그니처 제품 중 **"오늘 어떤 제품을 주력으로 밀어야 하는지"**를 한눈에 보여주는 B2B 핵심 차별화 기능이다. 1차 분석(`primary_judgements`)과 매트릭스 집계가 100% 일치하고, `jfsweQpxqsY`(색조)가 3종 전부 `Drop(1점)`, `RdXhzcCVtsw`(자막 미확인 `meta`)가 3종 전부 `Go` 차단되는 등 하드 가드레일 모순이 0건으로 확인되어 **PASS** 판정한다. 다만 아래 3가지 변별력·보고서 가독성 개선 포인트를 후속 백로그로 제안한다.

---

### 1. 핵심 무결성 검증 결과
- **1차 분석 vs 매트릭스 정합성**: `primary_product`에 `primary_judgements`를 직접 재사용(`pipeline.py` L548-549) → **불일치 0건**.
- **색조/무관 전 제품 차단**: `jfsweQpxqsY` → 딥 토너 `Drop(1)` · 그린 패드 `Drop(1)` · 워터리 마스크 `Drop(1)`, `best_product=None`.
- **자막 미확인(`meta`) 전 제품 Go 차단**: `RdXhzcCVtsw` → 딥 토너 `Pivot(3)` · 그린 패드 `Drop(2)` · 워터리 마스크 `Pivot(3)`, `best_product=None`.
- **전 제품 Go 0건 방어**: `"오늘은 억지 집행 금지 — 전원 보류/테스트 권장 (전 제품 Go 0건)"` 정직 출력 확인(`pipeline.py` L609).

---

### 2. 발견된 개선 포인트 / 약점 3가지 (증거 포함)

1. **[Medium] `워터리 스킨 마스크`의 제형 미일치 영상 고득점 경향 (`pipeline.py` L435-436, L496-503)**
   - **증거**: 시트팩과 무관한 세럼/수분크림 영상(`Zl5CPQxmWFE` 수지 세럼 3%, `rFgfkV4GZRQ` 수분크림 보습 3대장)이 `히알루론산`/`수분`/`건조` 일반 키워드만으로 `워터리 스킨 마스크`에서 `Go 4점`, `Go 5점`을 받는다.
   - **개선 제안**: 시트팩/패드처럼 제형 특성이 뚜렷한 제품은 `form_hits == 0`일 때 점수를 최대 4점(또는 3점)으로 캡핑해 **토너 vs 마스크의 주력 제품 변별력**을 높일 것.
2. **[Medium] 동점 시 `products.json` 키 순서 편향 (`pipeline.py` L572, L597-601)**
   - **증거**: `brKNpouibqo`·`rFgfkV4GZRQ`에서 딥 토너(5점)와 워터리 마스크(5점)가 동점일 때 L572 조건상 항상 첫 번째 키인 `딥 토너`가 `best_product`로 선정된다.
   - **개선 제안**: 동점 타이브레이커에 `form_hits`(제형 직접 일치 수) 및 Go 영상의 `views_per_day` 합계를 반영.
3. **[Low] `internal_report_md` 교차 매칭 요약에서 동률 Go 건수 시 추천 근거 불명확 (`pipeline.py` L876-886)**
   - **증거**: 실제 출력에서 `딥 토너`와 `워터리 마스크` 모두 `Go 3건 · Pivot 1건 · Drop 11건`으로 동일하게 표시되는데, 추천 사유에도 `(Go 3건 · Pivot 1건 · Drop 11건)`만 표기되어 팀장이 "둘 다 3건인데 왜 토너가 1등이지?"라고 되물을 수 있음(실제는 `total_go_score` 15 vs 14 차이).
   - **개선 제안**: 각 제품 요약 줄과 추천 사유에 `Go 총점` (예: `Go 3건(15점)`)을 함께 표기해 의사결정 투명성 확보.


---

## Sprint 7 레드팀 QA 검수 — B2B-10 스냅샷 시계열 변화 감지 + 자사 제품 온보딩

- **검수 일시**: 2026-11-25
- **검수 대상**: `history_store.py`, `pipeline.py` (`upsert_product_from_text`, `_brief_violations`), `app.py`, `TrendSetter_KBeauty_Pro.html`, `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / `ALL TESTS PASSED!`
  - 임시 디렉토리(`tempfile`) 기반 레드팀 3대 공격 테스트 실행 (깨진 `history.json` 복구, 기존 금지 목록 보존, 화장품법 금지어 온보딩을 통한 Step 4 감사 우회)
- **최종 판정**: **❌ FAIL (반려 — 자사 제품 온보딩 경로를 통한 Step 4 화장품법 감사 100% 우회 취약점 및 경고 증발 버그 확인)**

> **마케터 총평**:  
> 스냅샷 오염 방지(리허설 모드가 `history.json`/`localStorage`를 건드리지 않음), 깨진 `history.json` 안전 복구, 기존 제품 승격 시 `unverified_removed_from_v1` 보존은 모두 잘 구현되었다. 그러나 **자사 제품 온보딩에서 화장품법 제13조 위반 문구(`아토피 피부염 완치`, `여드름 3초 만에 즉각 치료`, `올리브영 1위`)를 붙여넣으면 경고만 반환한 채 `confidence="high"`로 그대로 저장되어 Step 4 과대광고 감사(`_brief_violations`)가 0건으로 완전히 무력화되는 치명적 우회 구멍**이 실증되었고, `app.py`에서는 `st.rerun()` 때문에 그 경고마저 화면에서 즉시 증발한다. 이는 절대 기준 3(과대광고 0건) 위반이므로 **FAIL** 판정한다.

---

### 1. 통과 확인 항목
- **스냅샷 오염 없음**: `app.py`의 `build_offline_rehearsal_result()`는 `history_store`를 호출하지 않고, `TrendSetter_KBeauty_Pro.html`의 `loadSampleRehearsal()`도 `annotateHistoryLocal()`을 호출하지 않아 라이브 스냅샷을 오염시키지 않음.
- **깨진 `history.json` 복구**: `"{broken json!!!"` 입력 시 예외 없이 `has_prev_snapshot=False, is_new=False`로 안전 복구 확인.
- **기존 금지 목록 보존**: `올리고 히알루론산 딥 토너` 승격 시 기존 `unverified_removed_from_v1` 4종(`7스킨 레이어링`, `올리브영 1위 토너`, `피부 속 2.5mm 보습 개선`, `100% 흡수`)이 100% 보존됨 확인.

---

### 2. 발견된 결함 3가지 (재현 증거 포함) 및 개선 제안

#### [결함 1 — Critical] 온보딩 금지어 저장 시 `confidence="high"` 승격 + Step 4 화장품법 감사 100% 우회
- **위치**: `pipeline.py` L69-93 (`upsert_product_from_text`), L667-670 (`_brief_violations`), `TrendSetter_KBeauty_Pro.html` L608-622 (`saveCustomProduct`)
- **재현 증거 (샌드박스 `tempfile` 단위 테스트)**:
  - 입력: `raw_claims_text = "아토피 피부염 완치 효과\n여드름 3초 만에 즉각 치료\n올리브영 1위 베스트셀러"`
  - 결과 1: `warnings: 7`이 감지되었음에도 `entry["confidence"] == "high"`로 그대로 저장됨.
  - 결과 2: 해당 제품으로 `"아토피 피부염 완치 효과! 올리브영 1위 베스트셀러 / 여드름 3초 만에 즉각 치료되는 세럼"` 콘티를 `_brief_violations()`에 통과시킨 결과 → **`violations = []` (위반 0건 완전 통과!)**.
  - 원인: `_brief_violations` L669가 `if nt and nt in norm_text and nt not in norm_claims:`로 되어 있어, 금지어가 `verified_claims`에 들어가는 순간 Step 4 감사가 영구 무력화되고, `creator_dm_clean_md` 소구 포인트에도 그대로 인플루언서에게 발송됨.
- **개선 제안 (이중 방어)**:
  1. `upsert_product_from_text()` (및 HTML `saveCustomProduct`)에서 화장품법 제13조 금지어가 포함된 줄은 `verified_claims`에서 **자동 제외(`rejected_claims`로 분리)**하고, 제외 후 남은 유효 문구가 없으면 저장을 거부(`ValueError`). 또한 `warnings`가 발생한 경우 `confidence`를 `"high"`로 승격하지 않거나(최대 `"medium"`), 금지어가 0건일 때만 `"high"` 허용.
  2. `_brief_violations()`(L669)에서 `COSMETIC_LAW_BANNED_TERMS` 중 의약품 오인·순위·과대광고 핵심어(`완치`, `아토피`, `피부염`, `치료`, `시술`, `1위`, `1등`, `즉각`, `기적`)는 `norm_claims` 존재 여부와 무관하게 **무조건 위반 처리**하도록 하드 가드.

#### [결함 2 — High] `app.py` 온보딩 저장 직후 `st.rerun()`으로 화장품법 경고 메시지 증발
- **위치**: `app.py` L443-449
- **근거**: `st.warning("화장품법 제13조 주의 표현 감지...")`와 `st.success(...)`를 호출한 직후 L449에서 `st.rerun()`을 실행하므로, 사용자가 경고 문구를 읽을 틈도 없이 0.01초 만에 화면에서 사라진다.
- **개선 제안**: 경고·성공 메시지를 `st.session_state["ob_flash"]`에 저장한 뒤 `st.rerun()`하고, 사이드바/상단 렌더링 시 1회 pop해서 표시하도록 수정.

#### [결함 3 — Low] `history_store.py`의 `save_history` 전체 덮어쓰기로 인한 `NEW` 오탐 가능성
- **위치**: `history_store.py` L27-45 (`save_history`)
- **근거**: `save_history`가 기존 `history.json`의 `videos` dict를 통째로 덮어쓰므로, 마케터가 다른 추가 키워드로 1회 검색하면 직전 메인 배치의 영상 이력이 전부 사라져 다음 메인 실행 시 기존 영상이 모두 `🆕 NEW`로 오탐된다.
- **개선 제안**: `save_history`에서 기존 `videos` dict를 로드해 병합(merge)하고 최근 200건까지만 유지하도록 개선.


---

## Sprint 7-R 최종 QA 재검수 — B2B-10 법무 우회 봉합·Flash 경고·History 병합 검증

- **검수 일시**: 2026-11-25
- **검수 대상**: `pipeline.py`, `history_store.py`, `app.py`, `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`** (`overclaim=18 violations caught`, `B2B-10` 통과)
  - 샌드박스 `tempfile` 기반 4대 레드팀 공격 재검증 → **`ALL SPRINT 7-R RED-TEAM CHECKS PASSED!`**
- **최종 판정**: **✅ PASS**

### 검증 상세 결과
1. **전부 금지어 입력 거부 (`RT1`)**: `아토피 피부염 완치 / 여드름 즉각 치료 / 올리브영 1위`만 입력 시 `ValueError("화장품법 금지 표현이 포함되어 저장할 수 없습니다.")`로 저장 원천 차단 확인.
2. **정상+금지어 혼합 시 격리 & `high` 승격 차단 (`RT2`)**: 금지어 문구만 `rejected_claims`로 자동 격리되고 `verified_claims`에는 정상 문구만 남으며 `confidence="medium"` 유지 확인.
3. **의약품 오인 절대 금지 하드 가드 (`RT3`)**: 강제로 `verified_claims`에 `아토피/완치/피부염/치료`를 주입해도 `_brief_violations()`가 4건 전부 무조건 위반으로 적발 확인.
4. **`app.py` Flash 메시지 유지 (`L456-467`)**: `st.session_state["onboarding_flash"]`로 `st.rerun()` 이후에도 경고·성공 메시지가 유실되지 않도록 수정 확인.
5. **`history_store.py` 병합(Merge) 보존 (`RT4`)**: 서로 다른 배치(`A`, `B`) 연속 저장 시 기존 `A`가 소실되지 않고 `['A', 'B']`로 안전 병합 확인.

> **총괄 결론**: Sprint 1~7-R에 걸친 오프라인 B2B 코어·법무 가드레일·3개 제품 DM·제품 3종 교차 매트릭스·스냅샷 시계열 변화·자사 제품 온보딩 전 기능이 독립 QA 게이트를 **PASS**했다. 남은 유일한 최종 출고 단계는 외부 API 권한 확보 후 `qa/benchmark_days.py` 및 `qa/run_once.py` 라이브 E2E 1회 실증이다.


---

## Sprint 8 QA 검수 — B2B-11 `qa/run_live_all.py` & `README.md`

- **검수 일시**: 2026-11-25
- **검수 대상**: `qa/run_live_all.py`, `README.md`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/run_live_all.py --dry-run` → `exit code 0` / **`DRY-RUN PASS!`** (904/1,500유닛 예산 내, `search_30d` 선정, 요약 4,328 chars 생성)
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`**
  - `--dry-run` 실행 전후 오염 점검: `qa/run_latest.json` (`False → False`), `cache_store/history.json` (`False → False`), `qa/LIVE_E2E_SUMMARY.md` (`False → False`) — **오염 0건 확인**.
  - `README.md` 링크 파일 10종 실존 여부 전수 확인: 10/10 전부 `True`.
- **최종 판정**: **✅ PASS**

### 1. 핵심 검수 결과
- **`qa/run_live_all.py`**: `--dry-run` / `--skip-benchmark` / 라이브 1클릭 실행 구조가 명확하며, Step B가 Step A 벤치마크 결과를 그대로 재사용해 추가 YouTube 쿼터 0을 달성. `--dry-run` 시 어떤 결과 파일이나 히스토리도 오염시키지 않음.
- **`README.md`**: v1.0 과장 표현(`7스킨`, `올리브영 1위`, `2.5mm 보습`, `PMF 100점`) **0건**. 비개발자 기준 10초 HTML 체험 → 로컬 Streamlit → 1줄 라이브 E2E → Cloud 배포 순으로 단계별 안내가 깔끔하게 구성됨.

### 2. 잔여 개선 포인트 2가지 (Low / 추후 보강 권장)
1. **[`qa/run_live_all.py` L217-222]** `selected_vids`가 빈 리스트(`[]`)일 때 `pipeline.run_pipeline()`을 호출하기 전에 `if not selected_vids:` 가드로 조기 종료·안내하면 불필요한 빈 LLM 호출을 방지할 수 있음.
2. **[`README.md` L22-25]** 다른 PC에서 처음 실행하는 비개발자를 위해 `pip install -r requirements.txt` 설치 안내 1줄과 `.env` 키 설정 예시를 보강하면 온보딩 완성도가 더욱 높아짐.


---

## Sprint 9 QA 검수 — B2B-12 팀장/임원 결재용 1페이지 독립 HTML 보고서

- **검수 일시**: 2026-11-25
- **검수 대상**: `pipeline.py` (`export_shareable_html_report`), `qa/run_live_all.py`, `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`** (`B2B-12 Shareable HTML Report: PASS`)
  - `python qa/run_live_all.py --dry-run` → `exit code 0` / **`DRY-RUN PASS!`** (1페이지 HTML 보고서 15,662 chars)
  - `--dry-run` 전후 `qa/LIVE_E2E_REPORT.html` 존재 여부: `False → False` (**오염 0건 확인**)
  - XSS 페이로드(`<script>alert(1)</script>`) + `AIza` 더미 키 주입 레드팀 테스트 실행
- **최종 판정**: **✅ PASS**

### 1. 보안·정결성·임원 보고 품격 검증 결과
- **원시 `<script>` 태그**: **0건** (XSS 페이로드 `&lt;script&gt;alert(1)&lt;/script&gt;`로 100% HTML 이스케이프 확인 — 사내 이메일 첨부 시 보안 필터 차단 위험도 원천 제거).
- **API 키 노출(`AIza`)**: **0건**.
- **내부 출처 주석(`products.json`, `kurly`, `glowpick`, `costco`, `요약)`)**: **0건**.
- **인쇄/PDF 최적화**: `@media print` 포함, KPI 4열 + 시장 패턴 + 3종 교차 매칭 추천 + Go 카드(4단 콘티 2×2 + 금지 표현 + `needs_review` 배너) 구성으로 팀장/임원 이메일 첨부 결재용으로 손색없는 품질.

### 2. 미세 개선 제안 (Optional)
- 순수 무스크립트 정적 HTML5 설계는 이메일 보안 관점에서 우수함. 헤더 우측에 `인쇄 / PDF 저장: Ctrl+P` 작은 안내 칩을 추가하면 비개발자 임원이 PDF로 변환하기 더욱 직관적임.


---

## 한국(KR) 2단계 탐색 구조 개편 최종 QA 검수

- **검수 일시**: 2026-11-25
- **검수 대상**: `agent_core.py`, `pipeline.py`, `app.py`, `TrendSetter_KBeauty_Pro.html`, `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`):
  - `python qa/eval_golden.py` → `exit code 0` / **`ALL TESTS PASSED!`** (9종 테스트 + 골든셋 15건 Drop 100%)
  - UI 개발자 용어 전수 스캔 + 색조 제품(`촉촉한 립틴트`) 양방향 도메인 & `copy_ideas` 3종 화장품법 제13조 감사 직접 실행
- **최종 판정**: **✅ PASS**

### 1. 검증 결과
1. **초기 샘플 미자동로드**: `app.py`(L456-467 대기 화면) 및 `TrendSetter_KBeauty_Pro.html`(L905 `renderExplorerNav()`만 호출) 모두 첫 화면에서 샘플 자동 로드 0건.
2. **화면 텍스트 개발자 용어 0건**: `2-Stage`, `products.json`, `velocity`, `localStorage`, `confidence=high`, `Stage 1`, `pipeline JSON` 화면 노출 0건 확인.
3. **양방향 도메인 & 카피 3종 감사**: 색조 제품(`촉촉한 립틴트`, `expected_domain="색조/메이크업"`) 기준 색조 `lip1=Go(5점)` / 기초 `ton1=Drop(1점)` 정상 판정, `copy_ideas` 3종에 주입한 화장품법 금지 표현 14건 전부 적발 확인.
4. **XSS & 복사/HTML 저장**: `app.py` (`_esc`)·HTML (`esc`) 전 동적 필드 이스케이프, `needs_review` DM 복사 경고 가드, 1페이지 HTML 보고서 저장(`@media print`, 0 `<script>`) 정상 확인.

### 2. 주의할 점 (Minor / 후속 다듬기 권장)
- `app.py` L659 및 `TrendSetter_KBeauty_Pro.html` L877의 보류(Pivot) 카드에 `⚠️ 자막 미확인 (직접 시청 필요)` 뱃지가 `text_source` 분기 없이 고정 출력됨 (`caption` Pivot일 때 분기 권장).
- `TrendSetter_KBeauty_Pro.html` L794 `downloadStep2Html()`에 `needs_review=True` 경고 배너 추가 시 `pipeline.export_shareable_html_report()`와 완전 패리티 달성.


---

## 숏폼레이더 3가지 UX 피드백 반영 최종 QA 검수

- **검수 일시**: 2026-11-25
- **검수 대상**: `TrendSetter_KBeauty_Pro.html`, `app.py`, `agent_core.py`, `docs/POLICY.md`, `qa/eval_golden.py`
- **실행 검증** (`BypassSandbox=false`): `python qa/eval_golden.py` (`ALL TESTS PASSED!`) + `git diff` 전수 확인 + 잔재 키워드 스캔
- **최종 판정**: **✅ PASS**

### 1. 핵심 검증 결과
1. **빠른 칩 전면 제거**: 4개 구현·문서 파일에서 `quickChips` / `KR_BEAUTY_QUICK_CHIPS` / `유통·피부고민` 잔재 0건 확인, 계층 탐색 단일 흐름으로 정리 완료.
2. **정렬 4종 툴팁 & 토스 UX 라이팅**: HTML(`data-tip`, `:last-child` 우측 정렬, `:focus-visible`) + Streamlit(`help=`) 모두 마케터가 즉시 이해하는 쉬운 능동형 한국어로 작성됨.
3. **YouTube API 오류 & 30일 0건 분기 수정**: 403 쿼터 초과 / 400 키 오류 / 403 API 미사용을 원인별 쉬운 한국어 안내로 변환 + 400/403 즉시 중단. 0건 시 7일일 때만 30일 전환 안내, 30일일 때는 상위 카테고리 안내로 정확히 분기.

### 2. 미세 UX 지적사항 (Minor, PASS 미차단)
- `TrendSetter_KBeauty_Pro.html` L257-268: `data-tip`과 네이티브 `title`이 함께 걸려 있어 마우스를 1초 이상 올리면 이중 툴팁이 겹칠 수 있음 (`title` 제거 권장).
- 기타 미분류 API 오류 폴백 시 영문 원문(`raw`)이 노출될 수 있으므로 추후 상세 로그 영역으로 분리 권장.
