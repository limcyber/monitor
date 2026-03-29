# Market Monitor

미국시장 모니터를 중심으로 운영하는 정적 대시보드 프로젝트입니다.

- Repository: `limcyber/monitor`
- Live site: `https://limcyber.github.io/monitor/`
- 미국 페이지: `docs/index.html`
- 한국 페이지 문서: [README_KR.md](./README_KR.md)

이 프로젝트는 실시간 트레이딩 시스템이 아니라, `시장 점검 + 종목 우선순위 정리 + 매매 판단 보조`에 초점을 둡니다.

## 1. 핵심 기능

### 1.1 시장 상태 점검
- 시장 점수를 `0~100`으로 계산합니다.
- 시장 상태를 `레벨 1~6`으로 변환합니다.
- `점수`, `매매 여건`, `추천 행동`을 함께 보여줍니다.
- 시장의 `크로스 신호`, `핵심 이유`, `세부 정보`를 같이 제공합니다.

### 1.2 고정 8종목 모니터링
- 사용자가 미리 정한 8개 종목만 같은 기준 시점으로 계산합니다.
- 각 종목에 대해 `점수`, `상태`, `추천 행동`, `실적발표일`, `크로스 신호`, `차트`를 보여줍니다.
- 종목별 상세 카드 안에서 `이유`, `점수를 올린 항목`, `불리한 항목`, `운용/주의 태그`를 펼쳐볼 수 있습니다.

### 1.3 시장 + 종목 결합 판단
- 시장이 상위 필터 역할을 합니다.
- 같은 종목 점수라도 시장이 약하면 더 보수적으로 행동하도록 조정합니다.

### 1.4 장중 5분 업데이트
- 장중에는 핵심 가격과 관심종목 가격이 5분 단위로 갱신됩니다.
- 장 마감 후에는 종가 기준 스냅샷으로 정리됩니다.
- breadth 같은 넓은 시장 폭 지표는 일봉 기준을 유지합니다.

### 1.5 GitHub Pages 자동 배포
- GitHub Actions가 데이터를 생성합니다.
- 생성된 JSON을 `docs/data/latest.json`에 저장합니다.
- Pages가 정적 HTML/CSS/JS로 렌더링합니다.

## 2. 화면 구성

### 2.1 상단바
- 프로젝트 제목
- 생성 시각
- 데이터 기준 시각
- 미국/한국 페이지 전환
- 밝은/어두운 테마 전환

### 2.2 시장 상태 카드
- 시장 상태 배지
- 점수 / 매매 여건 / 추천 행동
- 핵심 시세
  - `S&P500`
  - `NASDAQ`
  - `RUT`
  - `VIX`
  - `10Y`
- 크로스 신호
- 쉽게 설명하면
- 이렇게 본 이유
- 세부 정보 접힘

### 2.3 관심종목 요약 표
- 종목
- 현재가
- 점수
- 상태
- 추천 행동
- 메모

### 2.4 시장 차트
- `S&P500 / Nasdaq 추세`
- `시장 폭`
- `시장 긴장도`

### 2.5 종목별 상세
- 상태
- 점수
- 추천 행동
- 실적발표일
- 현재가
- 크로스 신호
- 설명과 세부 정보 접힘
- 가격/이동평균선/거래량 통합 차트

## 3. 데이터 기준과 사용 지표

### 3.1 시장 지표
- `^GSPC` : S&P 500 지수
- `^IXIC` : Nasdaq Composite 지수
- `^RUT` : Russell 2000 지수
- `^VIX` : 변동성 지수
- `^TNX` : 미국 10년물 금리

보조 지표:
- `SPY` : S&P500 거래량 프록시
- `QQQ` : Nasdaq 거래량 프록시
- `RSP` : 동일가중 S&P500 분위기 확인
- `HYG` : 위험자산/크레딧 분위기 확인
- `DX-Y.NYB` 또는 `UUP` : 달러 강도 확인
- `SOXX`, `XLK`, `XLF`, `XLY` : 섹터 강도 확인

### 3.2 시장 폭
시장 폭은 `S&P500 구성종목 집합`을 기준으로 계산합니다.

- `20일선 위 종목 비율`
- `50일선 위 종목 비율`
- `A/D Line 5일 방향`
- `RSP / SPX 상대 비교`

### 3.3 종목 지표
- 현재가
- 5일선
- 20일선
- 50일선
- 20일선 기울기
- 시장 대비 상대 흐름
- 최근 20일 수익률 비교
- 거래량 강도
- ATR 기반 흔들림
- 최근 과열 여부
- 실적 일정

## 4. 점수 계산 구조

### 4.1 시장 점수
시장 점수는 100점 만점입니다.

추세:
- S&P500이 200일선 위인지
- S&P500의 50일선이 200일선 위인지
- S&P500의 20일선이 상승 중인지
- S&P500이 20일선 위인지
- Nasdaq이 200일선 위인지
- Nasdaq의 50일선이 200일선 위인지
- Nasdaq의 20일선이 상승 중인지
- Nasdaq이 20일선 위인지
- RUT가 200일선 위인지
- RUT가 20일선 위인지
- 소형주가 대형주에 밀리지 않는지

참여도:
- 20일선 위 종목 비율
- 50일선 위 종목 비율
- A/D Line 최근 5일 방향
- 동일가중 시장 참여도

긴장도:
- VIX percentile
- HYG 50일선 위치
- 달러 z-score
- 10년물 금리 z-score

거래량 / 실행 보조:
- SPY 거래량 프록시
- QQQ 거래량 프록시
- 주요 매크로 이벤트 근접 여부

시장 네거티브 필터:
- 지수 반등인데 breadth가 약한 경우
- 대형주만 버티는 경우
- VIX가 매우 높은 경우
- FOMC / CPI / NFP / OpEx 직전

시장 레벨:
- `85~100` : 레벨 6
- `70~84` : 레벨 5
- `55~69` : 레벨 4
- `40~54` : 레벨 3
- `25~39` : 레벨 2
- `0~24` : 레벨 1

### 4.2 종목 점수
종목 점수도 100점 만점입니다.

추세:
- 현재가 > 20일선
- 현재가 > 50일선
- 20일선 > 50일선
- 20일선 상승 여부

상대강도:
- 종목 / 시장 비율이 20일 전보다 강한지
- 최근 20일 수익률이 시장보다 강한지

거래량:
- 상승 시 거래량이 평균보다 강한지
- 최근 상승일 거래량이 더 우세한지

리스크:
- ATR 기반 흔들림이 과도하지 않은지
- 최근 5일 과열 급등이 아닌지

이벤트:
- 실적이 가까운지
- 실적 일정이 확인되는지

종목 상태:
- `80~100` : 강함
- `65~79` : 양호
- `50~64` : 애매
- `35~49` : 약함
- `0~34` : 회피

### 4.3 크로스 신호
- 단기 크로스: `5일선 vs 20일선`, 최근 `5거래일`
- 중기 크로스: `20일선 vs 50일선`, 최근 `10거래일`

## 5. 장중 / 마감 후 데이터 동작

### 장중
- 기준 시간: `08:30~16:00 ET`
- 핵심 지수/ETF/관심종목 가격은 `5분봉` 기준으로 최신 바를 덮어써서 반영합니다.

### 장 마감 후
- 마감 후 `16:05~16:15 ET`에 close snapshot을 다시 만듭니다.
- 이 시점에는 종가 기준 일봉 스냅샷으로 정리됩니다.

### 계속 일봉 기준인 항목
- S&P500 breadth
- A/D Line

## Discord 테스트 전송

`send_discord_alerts.py`는 샘플 메시지도 바로 보낼 수 있습니다.

- 중요 알림 테스트
  - `DISCORD_TEST_KIND=important python3 scripts/send_discord_alerts.py`
- 기본 요약 테스트
  - `DISCORD_MARKET_SUMMARY=true DISCORD_TEST_KIND=summary python3 scripts/send_discord_alerts.py`
- AI 알림 테스트
  - `DISCORD_AI_ALERTS=true DISCORD_TEST_KIND=ai python3 scripts/send_discord_alerts.py`

공통:
- `DISCORD_WEBHOOK_URL`이 필요합니다.
- 한국장 기본 요약을 테스트하려면 `DISCORD_PAYLOAD_PATH=kr`를 같이 주면 됩니다.
- 20일선 / 50일선 / 200일선 같은 중장기 이동평균

## 6. 자동화와 배포

GitHub Actions 워크플로는 [daily-monitor.yml](./.github/workflows/daily-monitor.yml)에서 관리합니다.

트리거:
- `push` to `main`
- `workflow_dispatch`
- 평일 5분 cron: `*/5 * * * 1-5`

실제 실행 시간 제한:
- 장중: `08:30~16:00 ET`
- 마감 후: `16:05~16:15 ET`

### Discord 요약

#### [discord-market-summary.yml](./.github/workflows/discord-market-summary.yml)
기본 시장 상태 요약을 Discord로 보내는 워크플로입니다.
- 평일 기준 하루 2번, `09:00 ET`와 `16:30 ET`

### AI 분석 리프레시

#### [market-ai-refresh.yml](./.github/workflows/market-ai-refresh.yml)
미국 시장 `AI 분석`과 관심종목 `AI 요약`, 그리고 AI 전용 Discord 알림을 갱신하는 워크플로입니다.
- `AI_ANALYSIS_TEST_MODE=true`면 매일 5분마다 실행합니다
- `AI_ANALYSIS_TEST_MODE=false`면 매 30분마다 실행합니다 (`:00`, `:30`)
- `AI_ANALYSIS_TEST_MODE`가 없으면 기본값은 `false`입니다
- `GOOGLE_API_KEY` secret이 필요합니다
- 시장 AI는 `gemini-2.5-flash-lite`, 종목 AI는 `gemini-2.5-flash-lite`를 사용합니다

## 7. 파일별 설명

### config/
- [config/watchlist.yml](./config/watchlist.yml): 미국 워치리스트 8개
- [config/economic_calendar.yml](./config/economic_calendar.yml): 매크로 일정
- [config/earnings_calendar.yml](./config/earnings_calendar.yml): 실적발표일

### scripts/
- [scripts/generate_report.py](./scripts/generate_report.py): 미국 시장/종목 리포트 생성
- [scripts/send_discord_alerts.py](./scripts/send_discord_alerts.py): Discord 알림 전송

### docs/
- [docs/index.html](./docs/index.html): 미국 페이지 구조
- [docs/app.js](./docs/app.js): 미국 페이지 렌더링
- [docs/styles.css](./docs/styles.css): 공통 스타일
- [docs/data/latest.json](./docs/data/latest.json): 미국 최신 스냅샷
- [docs/data/history.json](./docs/data/history.json): 미국 최근 이력

## 8. 로컬 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_report.py
python -m http.server 4173 --directory docs
```

브라우저:
- `http://localhost:4173`

## 9. 한국장 문서

한국 페이지 구조, 지표, 워치리스트, 알림은 [README_KR.md](./README_KR.md)에서 따로 관리합니다.
