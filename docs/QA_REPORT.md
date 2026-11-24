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
