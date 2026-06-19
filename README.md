# Feed Creator

BOBP 포트폴리오 수익률 조회 및 주요 종목 뉴스 요약 생성 도구.

## 구조

```
feed-creator/
├── server.py          # FastAPI 백엔드 (포트 5000)
├── pipeline/
│   ├── pipeline.py    # 뉴스 수집 + 요약 파이프라인
│   └── ticker_name.py # Gemma 기반 검색 키워드 추출
├── client/            # React + TypeScript 프론트엔드 (포트 5173)
├── xlsx/              # 포트폴리오 엑셀 파일 (선택사항)
├── .env               # API 키 및 설정
└── requirements.txt   # Python 패키지
```

## 시작하기

### 1. Python 환경 설정

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
playwright install chromium
```

### 2. `.env` 파일 생성

```
GEMINI_API_KEY=your_key_here
NAME_SOURCE=api
```

### 3. 백엔드 실행

```bash
venv\Scripts\uvicorn server:app --host 0.0.0.0 --port 5000 --reload
```

### 4. 프론트엔드 실행

```bash
cd client
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속.

---

## 주요 기능

### 포트폴리오 테이블

- BOBP 포트폴리오 종목의 **1일 / 5일 수익률** 표시
- 날짜 선택으로 과거 날짜 조회 가능 (비거래일 선택 시 직전 거래일로 자동 스냅)
- 수익률 기준 하이라이트 종목 자동 선정 (1일 +8% 이상, 또는 5일 +20% 이상 & 당일 양수)

### Run Pipeline

하이라이트 종목에 대해 아래를 자동 실행:

1. 당일 수익률 계산
2. Gemma AI로 종목 검색 키워드 추출
3. Yahoo Finance에서 뉴스 스크래핑 (최대 50건)
4. 제목 키워드 필터링 → 정규장 마감 후(16:00–21:00 ET) 발행 기사만 선별
5. 기사 본문 파싱
6. Gemma AI로 X / LinkedIn 요약 생성

결과는 프로젝트 루트에 `{ticker}_{date}_news.json`으로 저장되며,  
해당 날짜 재방문 시 자동으로 불러와 테이블 하단에 표시됨.

### Settings

- **Gemini API Key**: 키 변경 (`.env`에 저장됨)
- **Portfolio Source**:
  - `Core16 API` — Core16 API에서 티커 목록 조회, 종목명은 Yahoo Finance에서 가져옴
  - `Excel (xlsx 폴더)` — `xlsx/` 폴더의 엑셀 파일에서 티커 목록과 종목명 모두 가져옴

---

## 파이프라인 단독 실행

```bash
venv\Scripts\python pipeline\pipeline.py TICKER [YYYY-MM-DD]

# 예시
venv\Scripts\python pipeline\pipeline.py MU 2026-06-16
```

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/portfolio?date=YYYY-MM-DD` | 포트폴리오 수익률 조회 |
| GET | `/api/env` | 현재 환경변수 조회 |
| POST | `/api/env` | 환경변수 업데이트 |
| POST | `/api/pipeline/run` | 파이프라인 실행 (SSE 스트리밍) |
| GET | `/api/pipeline/result?file=...` | 결과 JSON 조회 |
| GET | `/api/pipeline/result/by-date?date=YYYY-MM-DD` | 날짜로 결과 조회 |
