# Career Sniper

외국계 빅테크(Anthropic, Google, Salesforce, Palantir, OpenAI) 채용 페이지를 크롤링하여 채용공고(JD)를 분석하고, 내 이력서와 비교해 수정 포인트를 추천해주는 LangGraph 기반 멀티 에이전트 시스템입니다.

## 아키텍처

LangGraph로 구성된 4단계 에이전트 파이프라인으로 동작합니다.

```
[Crawler Agent] → [JD Analyzer Agent] → [Resume Matcher Agent] → [Recommender Agent]
      │                    │                       │                      │
  Playwright /        Anthropic API           이력서 vs JD           수정 포인트
  BeautifulSoup       (구조화 추출)              갭 분석                생성
      │                    │                       │                      │
      └──────────────────────── SQLite (JD / 분석 결과 저장) ──────────────────┘
```

| 에이전트 | 역할 |
|---|---|
| Crawler Agent | 각 회사 채용 페이지를 Playwright + BeautifulSoup으로 크롤링하여 원문 JD를 SQLite에 저장 |
| JD Analyzer Agent | Anthropic API로 JD에서 필요 스킬/자격요건/키워드를 구조화하여 추출 |
| Resume Matcher Agent | 구조화된 JD 요건과 내 이력서를 비교해 일치/누락 항목을 도출 |
| Recommender Agent | 갭 분석 결과를 바탕으로 이력서에 반영할 구체적인 수정 포인트를 제안 |

결과는 Streamlit UI에서 회사/직무별로 조회하고, 크롤링·분석 실행도 UI에서 트리거할 수 있습니다.

## 프로젝트 구조

```
career-sniper/
├── agents/                 # LangGraph 노드(에이전트) 구현
│   ├── crawler_agent.py
│   ├── jd_analyzer_agent.py
│   ├── resume_matcher_agent.py
│   └── recommender_agent.py
├── graph/                  # LangGraph 상태(State) 정의 및 워크플로우 조립
│   ├── state.py
│   └── workflow.py
├── crawlers/                # 회사별 크롤러 (Playwright + BeautifulSoup)
│   ├── base_crawler.py
│   ├── anthropic_crawler.py
│   ├── google_crawler.py
│   ├── salesforce_crawler.py
│   ├── palantir_crawler.py
│   └── openai_crawler.py
├── db/                      # SQLite 모델 및 연결 관리
│   ├── models.py
│   └── database.py
├── ui/
│   └── app.py               # Streamlit UI
├── config/
│   └── settings.py          # 환경변수 로딩 및 앱 설정
├── resume/                  # 내 이력서 파일 저장 위치 (git에 포함되지 않음)
├── data/                    # SQLite DB 파일 저장 위치 (git에 포함되지 않음)
├── tests/
├── main.py                  # CLI 진입점 (전체 파이프라인 실행)
├── requirements.txt
├── .env.example
└── README.md
```

## 설치 방법

### 1. 저장소 클론 및 가상환경 생성

```bash
git clone <repo-url>
cd career-sniper
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. 환경변수 설정

`.env.example`을 복사해 `.env` 파일을 만들고 값을 채웁니다.

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

`.env`에 최소한 아래 값을 채워야 합니다.

- `ANTHROPIC_API_KEY` — JD 분석/이력서 매칭에 사용할 Anthropic API 키
- `RESUME_FILE_PATH` — 분석할 내 이력서 파일 경로 (PDF/DOCX)

### 4. 이력서 파일 준비

`resume/` 폴더에 본인의 이력서 파일(PDF 또는 DOCX)을 넣고, `.env`의 `RESUME_FILE_PATH`를 해당 경로로 지정합니다. 이 폴더는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

## 사용법

### CLI로 전체 파이프라인 실행

```bash
python main.py
```

지정된 회사들의 채용 페이지를 크롤링하고, JD를 분석한 뒤, 이력서와 비교하여 추천 결과를 SQLite에 저장합니다.

### Streamlit UI 실행

```bash
streamlit run ui/app.py
```

브라우저에서 다음 작업을 수행할 수 있습니다.

- 회사/직무별 크롤링 및 분석 실행
- 저장된 JD 목록 및 상세 내용 조회
- 이력서 대비 갭 분석 리포트 확인
- 추천 수정 포인트 확인

## 기술 스택

- **Python** — 전체 구현 언어
- **LangGraph** — 크롤러/분석/매칭/추천 에이전트를 연결하는 멀티 에이전트 워크플로우
- **BeautifulSoup + Playwright** — 정적/동적 채용 페이지 크롤링
- **Anthropic API** — JD 구조화 분석 및 이력서 매칭·추천 생성
- **SQLite** — 크롤링한 JD 원문 및 분석 결과 저장
- **Streamlit** — 크롤링 실행, JD 조회, 추천 리포트 확인을 위한 UI

## 주의사항

- 각 회사 채용 페이지의 이용약관(robots.txt 등)을 준수하여 과도한 요청 없이 크롤링하세요. `.env`의 `CRAWL_DELAY_SECONDS`로 요청 간 지연을 조절할 수 있습니다.
- 이력서 파일과 `.env`(API 키 포함)는 git에 커밋되지 않도록 `.gitignore`에 이미 설정되어 있습니다.
