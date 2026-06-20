# Feed Creator

BOBP 포트폴리오 수익률 조회 및 주요 종목 뉴스 요약 자동 생성 도구.  
Core Sixteen 내부용. FastAPI 백엔드 + React/TypeScript 프론트엔드.

---

## 목차

1. [프로젝트 구조](#프로젝트-구조)
2. [사전 요구사항](#사전-요구사항)
3. [초기 세팅](#초기-세팅)
4. [실행 방법](#실행-방법)
5. [기능 설명](#기능-설명)
6. [파이프라인 단독 실행](#파이프라인-단독-실행)
7. [API 엔드포인트](#api-엔드포인트)

---

## 프로젝트 구조

```
feed-creator/
├── server.py               # FastAPI 백엔드 (포트 5000)
├── pipeline/
│   ├── pipeline.py         # 뉴스 수집 → 필터링 → 요약 파이프라인
│   └── ticker_name.py      # Gemma AI 기반 종목 검색 키워드 추출
├── client/                 # React + TypeScript 프론트엔드 (포트 5173)
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── PortfolioTable.tsx   # 수익률 테이블
│           ├── PipelinePanel.tsx    # 파이프라인 실행 패널 (슬라이드)
│           ├── ResultCard.tsx       # 요약 결과 카드
│           ├── SettingsModal.tsx    # 설정 모달
│           └── AlertModal.tsx       # 경고 모달
├── xlsx/                   # 포트폴리오 엑셀 파일 (Portfolio Source: Excel 선택 시 사용)
├── .env                    # API 키 및 설정 (git 제외)
├── requirements.txt        # Python 패키지
└── *_news.json             # 파이프라인 결과 파일 (git 제외)
```

---

## 사전 요구사항

- Python 3.11 이상
- Node.js 18 이상
- Gemini API 키 ([Google AI Studio](https://aistudio.google.com)에서 발급)

---

## 초기 세팅

### 1. Python 가상환경 구성

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\playwright install chromium
```

> macOS/Linux의 경우 `venv\Scripts\` 대신 `venv/bin/` 사용

### 2. `.env` 파일 생성

프로젝트 루트에 `.env` 파일을 만들고 아래 내용을 작성합니다.

```env
GEMINI_API_KEY=your_gemini_api_key_here
NAME_SOURCE=api
```

| 변수 | 설명 |
|------|------|
| `GEMINI_API_KEY` | Gemini API 키. 파이프라인 요약 생성에 필요. |
| `NAME_SOURCE` | 포트폴리오 데이터 소스. `api` (기본값) 또는 `excel`. 웹 UI의 Settings에서도 변경 가능. |

### 3. 프론트엔드 패키지 설치

```bash
cd client
npm install
```

---

## 실행 방법

백엔드와 프론트엔드를 **각각 별도 터미널**에서 실행합니다.

### 백엔드 (터미널 1)

```bash
venv\Scripts\uvicorn server:app --host 0.0.0.0 --port 5000 --reload
```

### 프론트엔드 (터미널 2)

```bash
cd client
npm run dev
```

브라우저에서 `http://localhost:5173` 접속.

> 프론트엔드의 `/api` 요청은 Vite 프록시를 통해 `http://localhost:5000`으로 자동 전달됩니다.

---

## 기능 설명

### 포트폴리오 테이블

BOBP 포트폴리오 전 종목의 수익률을 두 가지 기준으로 표시합니다.

| 컬럼 | 설명 |
|------|------|
| 1D Return | 해당 거래일의 일간 수익률 |
| 5D Return | 직전 5 거래일 누적 수익률 |

**날짜 선택**
- 헤더 우측의 날짜 입력으로 과거 날짜 조회 가능
- 비거래일(주말·공휴일) 선택 시 직전 거래일로 자동 스냅
- 최신 거래일 이후 미래 날짜 선택 시 경고 모달 표시

**하이라이트 종목**

다음 조건 중 하나를 충족하는 종목을 파이프라인 대상으로 자동 선정합니다.

1. 1일 수익률 **+8% 이상** → 해당 종목 중 수익률 최상위
2. 5일 수익률 **+20% 이상** & 당일 수익률 **양수** → 해당 종목 중 1일 수익률 최상위

조건을 만족하는 종목이 없으면 **Run Pipeline** 버튼이 비활성화됩니다.

---

### Run Pipeline

하이라이트 종목에 대해 아래 5단계를 순차 실행합니다.

```
[1/5] 거래일 및 티커 확인
[2/5] 당일 수익률 계산
[3/5] Gemma AI로 종목 검색 키워드 추출
[4/5] Yahoo Finance 뉴스 스크래핑 → 제목 필터링 → 시간대 필터링 → 본문 파싱
[5/5] Gemma AI로 X / LinkedIn 요약 생성
```

**단계별 상세**

| 단계 | 내용 |
|------|------|
| 키워드 추출 | ticker의 yfinance 종목명을 바탕으로 Gemma가 실제 검색 키워드 배열 생성 (예: `GOOGL` → `["Google", "Alphabet"]`) |
| 뉴스 스크래핑 | Yahoo Finance 종목 뉴스 페이지에서 최대 50건 수집 (Playwright headless Chrome) |
| 제목 필터링 | 수집된 기사 중 ticker 또는 키워드가 제목에 포함된 기사만 선별 |
| 시간대 필터링 | 정규장 마감 후 당일 16:00–21:00 ET 사이에 발행된 기사만 통과 |
| 본문 파싱 | 각 기사 URL에 접속해 본문 텍스트 추출 (Barron's 기사는 AI에게 제공 시 제외) |
| 요약 생성 | Gemma 4 모델로 X(Twitter)용 / LinkedIn용 두 가지 포맷 생성 |

**X 요약 포맷**
- 1문장: 주가 상승의 실질적 원인 (헤드라인 요약이 아닌 재평가 근거)
- 1문장: 이 움직임이 남긴 가장 날카로운 미해결 긴장감 또는 전망 질문 (100자 이내, 매수·매도 신호 없음)

**LinkedIn 요약 포맷**
- 2–3문장: 핵심 원인과 구조적 의미
- 1–2문장: 독자가 생각해볼 전망적 시사점 (매수·매도 신호 없음)

**결과 저장 및 자동 표시**

파이프라인 완료 시 프로젝트 루트에 `{ticker}_{YYYY-MM-DD}_news.json`으로 저장됩니다.  
이후 해당 날짜로 포트폴리오를 조회하면 테이블 하단에 결과 카드가 자동 표시됩니다.

실행 로그는 파이프라인 패널(우측 슬라이드)에 실시간으로 스트리밍됩니다.

---

### Settings

헤더 우측 **⚙ Settings** 버튼으로 접근.

**Gemini API Key**

현재 등록된 키의 마스킹된 값이 표시됩니다. 새 키를 입력하면 `.env` 파일에 즉시 반영됩니다.

**Portfolio Source**

포트폴리오 종목 목록과 종목명을 어디서 가져올지 선택합니다.

| 옵션 | 티커 소스 | 종목명 소스 |
|------|-----------|-------------|
| Core16 API | Core16 REST API | Yahoo Finance |
| Excel (xlsx 폴더) | `xlsx/` 폴더 내 엑셀 파일 | 동일 엑셀 파일 |

엑셀 파일 형식: 15행부터 시작, B열 = ticker, C열 = 종목명.

---

## 파이프라인 단독 실행

서버 없이 CLI에서 직접 실행할 수 있습니다.

```bash
venv\Scripts\python pipeline\pipeline.py TICKER [YYYY-MM-DD]
```

```bash
# 최근 거래일 기준으로 MU 실행
venv\Scripts\python pipeline\pipeline.py MU

# 특정 날짜 지정
venv\Scripts\python pipeline\pipeline.py MU 2026-06-16
```

결과 JSON은 실행 위치(프로젝트 루트)에 저장됩니다.

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/portfolio` | 최신 거래일 포트폴리오 수익률 조회 |
| `GET` | `/api/portfolio?date=YYYY-MM-DD` | 특정 날짜 포트폴리오 수익률 조회 |
| `GET` | `/api/env` | 현재 환경변수 조회 (API 키 마스킹 포함) |
| `POST` | `/api/env` | 환경변수 업데이트 (`GEMINI_API_KEY`, `NAME_SOURCE`) |
| `POST` | `/api/pipeline/run` | 파이프라인 실행 — SSE 스트리밍으로 로그 반환 |
| `GET` | `/api/pipeline/result?file=filename.json` | 결과 JSON 파일 조회 |
| `GET` | `/api/pipeline/result/by-date?date=YYYY-MM-DD` | 날짜로 결과 조회 |
