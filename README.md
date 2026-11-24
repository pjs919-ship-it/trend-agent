# 💄 K-Beauty TrendSetter Pro (B2B Edition v2)

> **화장품 브랜드사 인하우스 마케터의 매일 1~2시간 유튜브 쇼츠 탐색을 10분으로 줄여주는 B2B 트렌드 의사결정 & 캠페인 브리프 에이전트**

- **🎯 냉정한 Go / Pivot / Drop 판정**: 색조·무관 영상과의 억지 연결을 코드 가드레일로 강제 차단 (`Drop` 정확도 100%, 골든셋 15건 검증).
- **🔀 제품 3종 교차 매칭 매트릭스**: 한 번의 클리핑(추가 YouTube 쿼터 0)으로 주력 3종(딥 토너 / 그린 2.5 패드 / 워터리 마스크) 중 오늘 가장 잘 맞는 주력 제품을 한눈에 추천.
- **🛡️ 화장품법 제13조 자동 감사**: 의약품 오인 표현(`완치`, `아토피`, `피부과 시술` 등)과 출처 없는 과대광고 수치를 코드로 사전 적발·격리하고, 실제 자막 원문 인용 100% 대조.
- **📋 원클릭 2종 복사**: `[팀장/슬랙 보고용 1페이지 요약]` + `[인플루언서 DM 발송용 깨끗한 촬영 가이드]` 즉시 복사.
- **📈 시계열 변화 감지 & 신제품 온보딩**: 직전 스냅샷 대비 `🆕 NEW` / `+Δ회 ↑` 상승 추적 + 공식 상세페이지 문구 붙여넣기로 신뢰도 `high` 승격.

---

## ⚡ 3분 시작 가이드

### 방법 1. 가장 쉬운 10초 체험 (설치 불필요)
1. 폴더 안의 **`TrendSetter_KBeauty_Pro.html`** 파일을 더블클릭해 Chrome/Edge 브라우저로 엽니다.
2. 별도 API 키 없이도 기본 로드되는 **샘플 리허설 대시보드**에서 5단 B2B 위계, 3종 교차 매칭, 원클릭 복사를 바로 체험할 수 있습니다.
3. 상단에 YouTube API Key와 무료 Gemini API Key를 입력하면 2-Stage 실시간 분석도 브라우저에서 바로 실행됩니다.

### 방법 2. 로컬 Streamlit 웹 대시보드 실행
터미널(PowerShell)을 열고 아래 두 줄을 복사해 실행합니다.
*(처음 실행하는 PC라면 먼저 `pip install -r requirements.txt`를 설치하고, 프로젝트 폴더에 `YOUTUBE_API_KEY=...` / `GOOGLE_API_KEY=...`가 담긴 `.env` 파일을 준비하세요.)*
```powershell
cd "c:\test\ai-class-final project"
python -m streamlit run app.py
```
- 브라우저가 자동으로 열리면 왼쪽 사이드바에서 **`🧪 스냅샷/리허설 보기 (쿼터 0)`** 또는 **`🚀 실시간 트렌드 분석 실행`**을 누릅니다.
- 사이드바 하단의 **`➕ 자사 제품 추가 / 상세페이지 원문으로 신뢰도 승격`**에서 공식 상세페이지 문구를 등록하면 `confidence=high`로 승격됩니다.

### 방법 3. 기상 후 1줄 라이브 E2E 실측 (7/14/30일 비교 + 리포트 자동 생성)
`.env`에 `YOUTUBE_API_KEY`와 `GOOGLE_API_KEY`가 설정되어 있다면 아래 명령어 **1줄**로 기간 벤치마크(`7/14/30일 + mostPopular`) → 최적 기간 재사용 E2E 분석 → 요약 리포트 생성까지 한 번에 완료됩니다.
```powershell
python qa/run_live_all.py
```
- 생성 결과:
  - `qa/benchmark_result.json` (7/14/30일 + `mostPopular` 비교 실측)
  - `qa/run_latest.json` (`app.py`와 `TrendSetter_KBeauty_Pro.html`에서 즉시 열 수 있는 최신 스냅샷)
  - `qa/LIVE_E2E_SUMMARY.md` (팀장 보고서 + 인플루언서 DM + 기간 비교표 통합 요약)
- 네트워크 없이 예산(904/1,500유닛)과 로직만 먼저 확인하려면:
  ```powershell
  python qa/run_live_all.py --dry-run
  ```
- 이미 `qa/benchmark_result.json`이 있고 추가 YouTube 쿼터 0으로 파이프라인만 재실행하려면:
  ```powershell
  python qa/run_live_all.py --skip-benchmark
  ```

### 방법 4. GitHub 푸시 & Streamlit Community Cloud 무료 배포
1. GitHub에 코드 푸시:
   ```powershell
   git push -u origin main
   ```
2. [Streamlit Community Cloud](https://share.streamlit.io/) 접속 → `New app` → 저장소 선택 → Main file path에 `app.py` 입력.
3. **Advanced settings → Secrets**에 아래 2줄을 입력 후 `Deploy`:
   ```toml
   YOUTUBE_API_KEY = "여기에_유튜브_API_키"
   GOOGLE_API_KEY = "여기에_제미나이_API_키"
   ```

---

## 🧪 오프라인 자동 회귀 테스트
네트워크·API 쿼터 없이 핵심 가드레일(화장품법 감사, 억지 연결 Drop 100%, 3종 교차 매칭, 시계열 변화 감지, 온보딩 격리)을 즉시 검증할 수 있습니다.
```powershell
python qa/eval_golden.py
```

---

## 📚 주요 프로젝트 문서
- 📄 [제품 요구사항 정의서 (docs/PRD.md)](docs/PRD.md)
- 🎨 [B2B v2 디자인 시스템 (docs/DESIGN_SYSTEM.md)](docs/DESIGN_SYSTEM.md)
- 🛡️ [독립 QA 감사 리포트 (docs/QA_REPORT.md)](docs/QA_REPORT.md)
- 📘 [엔지니어링 플레이북 (docs/PLAYBOOK.md)](docs/PLAYBOOK.md)
- 🚀 [릴리즈 노트 (docs/RELEASE_NOTES.md)](docs/RELEASE_NOTES.md)
- 🧭 [PM 헌장 (docs/PM_CHARTER.md)](docs/PM_CHARTER.md)
