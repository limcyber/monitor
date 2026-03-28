# Korea Market Monitor

한국시장 모니터 전용 문서입니다.

- 한국 페이지: `docs/kr.html`
- 한국 데이터: `docs/data/latest_kr.json`
- 한국 워크플로: `.github/workflows/discord-korea-market-summary.yml`

## 1. 개요

한국 페이지는 미국 페이지보다 더 단순하게 구성한 실전형 보조 화면입니다.

- 핵심 축: `KOSPI`, `KOSDAQ`, `KOSPI200`, `USD/KRW`, `VIX`, `KODEX 반도체`
- 목적: 대표주와 고정 관심종목을 같은 시점으로 점검해 `추천 행동`을 빠르게 읽기
- 성격: 실시간 초단타 시스템이 아니라, 장 시작 전/마감 후 판단 보조용

## 2. 현재 워치리스트

현재 한국 워치리스트는 총 8종목입니다.

- 삼성전자
- SK하이닉스
- NAVER
- 현대차
- 아이티센글로벌
- 클로봇
- 한화에어로스페이스
- LIG넥스원

설정 파일:
- [config/watchlist_kr.yml](./config/watchlist_kr.yml)

## 3. 화면 구성

### 3.1 상단바
- 한국 주식 모니터 제목
- 생성 시각
- 데이터 기준 시각
- 미국/한국 전환 버튼
- 밝은/어두운 테마 전환

### 3.2 한국 시장 상태 카드
- 점수
- 신뢰도
- 매매 여건
- 추천 행동
- 핵심 시세
  - `KOSPI`
  - `KOSDAQ`
  - `KOSPI200`
  - `USD/KRW`
  - `VIX`
  - `KODEX 반도체`
- 크로스 신호
- 쉽게 설명하면
- 이렇게 본 이유
- 세부 정보 접힘

### 3.3 한국 시장 차트
- `KOSPI / KOSDAQ 추세`
- 체감 지표 4개
  - `KOSPI200`
  - `USD/KRW`
  - `VIX`
  - `KODEX 반도체` 또는 `코스닥 참여도`

### 3.4 관심종목 요약
- 종목
- 현재가
- 점수
- 상태
- 추천 행동
- 메모

### 3.5 종목별 상세
- 상태
- 점수
- 추천 행동
- 현재가
- 시장구분
- 크로스 신호
- 설명과 세부 정보 접힘
- 가격/이동평균선/거래량 통합 차트

## 4. 한국 시장 지표

한국 페이지는 아래 지표를 봅니다.

- `^KS11` : KOSPI 지수
- `^KQ11` : KOSDAQ 지수
- `^KS200` : KOSPI200 지수
- `KRW=X` : USD/KRW 환율
- `^VIX` : 해외 변동성 참고
- `091160.KS` : KODEX 반도체

특징:
- 미국 페이지처럼 breadth를 무겁게 계산하지 않습니다.
- 대신 `코스닥이 코스피에 밀리지 않는지`, `원달러 부담`, `반도체 주도력`을 더 직접적으로 봅니다.

## 5. 한국 시장 점수 구조

한국 페이지도 100점 만점입니다.

### 추세
- KOSPI가 200일선 위인지
- KOSPI 20일선이 상승 중인지
- KOSDAQ이 200일선 위인지
- KOSDAQ 20일선이 상승 중인지
- KOSPI200이 50일선/200일선 위인지

### 참여도 / 체감 온도
- 코스닥이 코스피 대비 밀리지 않는지
- 최근 코스닥 참여가 살아나는지
- 반도체가 코스피보다 강한지

### 스트레스
- 원달러 20일 z-score
- VIX percentile
- 코스닥 변동성 과열 여부

### 네거티브 필터
- KOSPI와 KOSDAQ이 모두 200일선 아래면 점수 상한
- 지수 반등인데 코스닥 참여가 약하면 감점
- 원달러와 해외 변동성이 동시에 높으면 감점

## 6. 종목 점수 구조

미국 페이지와 비슷하게 아래를 봅니다.

- 현재가 > 20일선
- 현재가 > 50일선
- 20일선 > 50일선
- 20일선 상승 여부
- 시장 대비 상대 흐름
- 최근 20일 수익률 비교
- 거래량 강도
- ATR 기반 흔들림
- 최근 과열 여부

현재 한국 페이지는 실적 일정 품질 문제를 줄이기 위해, 실적 캘린더를 화면 핵심 요소에서 제외했습니다.

## 7. 장중 / 마감 후 동작

한국 페이지도 리포트 생성 자체는 현재 동일 프로젝트 안에서 같이 관리하지만, 데이터 표시는 한국장에 맞는 종가 기준으로 읽는 편이 자연스럽습니다.

현재 `market_data_as_of`는 한국 종가 기준이면 보통 아래처럼 찍힙니다.
- `YYYY-MM-DD 15:30 KST (Close)`

## 8. Discord 한국장 알림

#### [discord-korea-market-summary.yml](./.github/workflows/discord-korea-market-summary.yml)
한국장 기본 시장 상태 요약을 Discord로 보내는 워크플로입니다.

- 평일 기준 하루 2번
- `08:30 KST`
- `16:00 KST`
- `docs/data/latest_kr.json` 기준으로 전송

전송 내용:
- 한국 시장 상태
- 점수 / 추천 행동
- 핵심 이유 1개
- 상위 관심종목 3개

## 9. 관련 파일

- [docs/kr.html](./docs/kr.html)
- [docs/kr-app.js](./docs/kr-app.js)
- [scripts/generate_kr_report.py](./scripts/generate_kr_report.py)
- [docs/data/latest_kr.json](./docs/data/latest_kr.json)
- [docs/data/history_kr.json](./docs/data/history_kr.json)
- [config/watchlist_kr.yml](./config/watchlist_kr.yml)

## 10. 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_kr_report.py
python -m http.server 4173 --directory docs
```

브라우저:
- `http://localhost:4173/kr.html`
