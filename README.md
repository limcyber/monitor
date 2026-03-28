# Market Monitor

시장 전체 흐름과 고정 관심종목 8개의 상태를 같은 시점 기준으로 함께 점검하는 정적 대시보드 프로젝트입니다.

- Repository: `limcyber/monitor`
- Live site: `https://limcyber.github.io/monitor/`
- 목적: `시장 환경`과 `관심종목 상태`를 분리해서 보고, 마지막에 둘을 결합해 `추천 행동`을 제시

이 프로젝트는 실시간 트레이딩 시스템이 아니라, `시장 점검 + 종목 우선순위 정리 + 매매 판단 보조`에 초점을 둡니다.

## 1. 핵심 기능

### 1.1 시장 상태 점검
- 시장 점수를 `0~100`으로 계산합니다.
- 시장 상태를 `레벨 1~6`으로 변환합니다.
- `점수`, `신뢰도`, `매매 여건`, `추천 행동`을 함께 보여줍니다.
- 시장의 `크로스 신호`, `핵심 이유`, `세부 정보`를 같이 제공합니다.

### 1.2 고정 8종목 모니터링
- 사용자가 미리 정한 8개 종목만 매일 같은 기준 시점으로 계산합니다.
- 각 종목에 대해 `점수`, `상태`, `추천 행동`, `실적발표일`, `크로스 신호`, `차트`를 보여줍니다.
- 종목별 상세 카드 안에서 `이유`, `점수를 올린 항목`, `불리한 항목`, `운용/주의 태그`를 펼쳐볼 수 있습니다.

### 1.3 시장 + 종목 결합 판단
- 시장이 상위 필터 역할을 합니다.
- 같은 종목 점수라도 시장이 약하면 더 보수적으로 행동하도록 조정합니다.
- 예를 들어 종목이 좋아도 시장 레벨이 낮으면 `선별 매수`가 아니라 `관찰` 또는 `회피`로 낮아질 수 있습니다.

### 1.4 장중 5분 업데이트
- 장중에는 핵심 가격과 관심종목 가격이 5분 단위로 갱신됩니다.
- 장 마감 후에는 종가 기준 스냅샷으로 정리됩니다.
- 단, breadth 같은 넓은 시장 폭 지표는 무거운 계산을 피하기 위해 일봉 기준을 유지합니다.

### 1.5 GitHub Pages 자동 배포
- GitHub Actions가 데이터를 생성합니다.
- 생성된 JSON을 `docs/data/latest.json`에 저장합니다.
- Pages가 정적 HTML/CSS/JS로 렌더링합니다.

## 2. 화면 구성

현재 대시보드는 크게 5개 영역으로 구성됩니다.

### 2.1 상단바
- 프로젝트 제목
- 생성 시각
- 데이터 기준 시각
- 밝은/어두운 테마 전환

### 2.2 시장 상태 카드
- 시장 상태 배지
- 점수 / 신뢰도 / 매매 여건 / 추천 행동
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
  - 점수를 올린 항목
  - 점수를 깎았거나 불리한 항목
  - 변화
  - 운용 가이드
  - 알림
  - 신뢰도 경고
  - 섹터 강도
  - 최근 30일
  - 주의할 점

### 2.3 관심종목 요약 표
- 종목
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
시장 상태 계산에 사용하는 대표 축은 아래와 같습니다.

- `^GSPC` : S&P 500 지수
- `^IXIC` : Nasdaq Composite 지수
- `^RUT` : Russell 2000 지수
- `^VIX` : 변동성 지수
- `^TNX` : 미국 10년물 금리

보조 지표도 함께 사용합니다.

- `SPY` : S&P500 거래량 프록시
- `QQQ` : Nasdaq 거래량 프록시
- `RSP` : 동일가중 S&P500 분위기 확인
- `HYG` : 위험자산/크레딧 분위기 확인
- `DX-Y.NYB` 또는 `UUP` : 달러 강도 확인
- `SOXX`, `XLK`, `XLF`, `XLY` : 섹터 강도 확인

### 3.2 시장 폭
시장 폭은 ETF가 아니라 `S&P500 구성종목 집합`을 기준으로 계산합니다.

- `20일선 위 종목 비율`
- `50일선 위 종목 비율`
- `A/D Line 5일 방향`
- `RSP / SPX 상대 비교`

구성종목 목록은 위키피디아의 S&P500 리스트를 우선 사용하고, 실패 시 코드 안의 대표 종목 목록으로 대체합니다.

### 3.3 종목 지표
각 관심종목은 아래 지표를 봅니다.

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

## 4.1 시장 점수
시장 점수는 100점 만점입니다.

### 추세
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

### 참여도
- 20일선 위 종목 비율
- 50일선 위 종목 비율
- A/D Line 최근 5일 방향
- 동일가중 시장 참여도

### 긴장도
- VIX percentile
- HYG 50일선 위치
- 달러 z-score
- 10년물 금리 z-score

### 거래량 / 실행 보조
- SPY 거래량 프록시
- QQQ 거래량 프록시
- 주요 매크로 이벤트 근접 여부

### 시장 네거티브 필터
다음 필터가 걸리면 점수를 더 깎거나 상한을 둡니다.

- 지수 반등인데 breadth가 약한 경우
- 대형주만 버티는 경우
- VIX가 매우 높은 경우
- FOMC / CPI / NFP / OpEx 직전

### 시장 레벨
- `85~100` : 레벨 6
- `70~84` : 레벨 5
- `55~69` : 레벨 4
- `40~54` : 레벨 3
- `25~39` : 레벨 2
- `0~24` : 레벨 1

## 4.2 종목 점수
종목 점수도 100점 만점입니다.

### 추세
- 현재가 > 20일선
- 현재가 > 50일선
- 20일선 > 50일선
- 20일선 상승 여부

### 상대강도
- 종목 / 시장 비율이 20일 전보다 강한지
- 최근 20일 수익률이 시장보다 강한지

### 거래량
- 상승 시 거래량이 평균보다 강한지
- 최근 상승일 거래량이 더 우세한지

### 리스크
- ATR 기반 흔들림이 과도하지 않은지
- 최근 5일 과열 급등이 아닌지

### 이벤트
- 실적이 가까운지
- 실적 일정이 확인되는지

### 종목 상태
- `80~100` : 강함
- `65~79` : 양호
- `50~64` : 애매
- `35~49` : 약함
- `0~34` : 회피

## 4.3 크로스 신호
크로스 신호는 점수와 별도로 상단 하이라이트로 보여줍니다.

- 단기 크로스: `5일선 vs 20일선`, 최근 `5거래일`
- 중기 크로스: `20일선 vs 50일선`, 최근 `10거래일`

## 5. 장중 / 마감 후 데이터 동작

### 장중
- 기준 시간: `08:30~16:00 ET`
- 핵심 지수/ETF/관심종목 가격은 `5분봉` 기준으로 최신 바를 덮어써서 반영합니다.
- 따라서 `현재가`, `등락률`, `거래량`은 장중에 5분 단위로 움직입니다.

### 장 마감 후
- 마감 후 `16:05~16:15 ET`에 close snapshot을 다시 만듭니다.
- 이 시점에는 종가 기준 일봉 스냅샷으로 정리됩니다.

### 계속 일봉 기준인 항목
- S&P500 breadth
- A/D Line
- 20일선 / 50일선 / 200일선 같은 중장기 이동평균

즉, 이 프로젝트는 완전한 초단타 장중 시스템이 아니라 `일봉 추세 위에 장중 현재값을 얹는 구조`입니다.

## 6. 실적 일정 처리 방식

현재 실적 일정은 두 층으로 처리합니다.

### 6.1 수동 캘린더
`config/earnings_calendar.yml`에 워치리스트 종목의 실적 날짜를 직접 기록합니다.

이 방식의 장점:
- 표시가 안정적입니다.
- 종목 카드에 `실적발표일`을 확실하게 넣을 수 있습니다.
- 외부 API 불안정에 덜 흔들립니다.

### 6.2 보조 조회
수동 캘린더에 없는 경우 `yfinance`의 earnings calendar를 보조적으로 시도합니다.

단, 네트워크/소스 제한 때문에 이 부분은 항상 안정적이지 않을 수 있습니다. 그래서 현재는 수동 캘린더가 주력입니다.

### 6.3 ETF 처리
ETF 또는 실적 개념이 애매한 종목은 `미확인`으로 처리될 수 있습니다.

## 7. 자동화와 배포

GitHub Actions 워크플로는 [daily-monitor.yml](./.github/workflows/daily-monitor.yml)에서 관리합니다.

### 트리거
- `push` to `main`
- `workflow_dispatch`
- 평일 5분 cron: `*/5 * * * 1-5`

### 실제 실행 시간 제한
cron은 5분마다 돌지만, 실제 리포트 생성은 아래 구간에서만 실행합니다.

- 장중: `08:30~16:00 ET`
- 마감 후: `16:05~16:15 ET`

### Actions가 하는 일
1. 리포지토리 체크아웃
2. Python 설치
3. 지금이 실행 가능 시간인지 판단
4. 의존성 설치
5. `scripts/generate_report.py` 실행
6. `docs/`를 Pages artifact로 업로드
7. `docs/data/latest.json`, `docs/data/history.json` 커밋
8. GitHub Pages 배포

## 8. 파일별 설명

### 루트

#### [README.md](./README.md)
프로젝트 설명 문서입니다.

#### [requirements.txt](./requirements.txt)
Python 의존성 목록입니다.

### config/

#### [config/watchlist.yml](./config/watchlist.yml)
고정 관심종목 8개를 관리합니다.

현재 예시:
- NVDA
- TSLA
- META
- AMD
- TEM
- SOXX
- SERV
- KORU

#### [config/economic_calendar.yml](./config/economic_calendar.yml)
시장 매크로 이벤트 일정을 수동 관리합니다.

- FOMC
- CPI
- NFP

`OpEx`는 여기에 기록하지 않고 스크립트에서 매달 세 번째 금요일로 계산합니다.

#### [config/earnings_calendar.yml](./config/earnings_calendar.yml)
워치리스트 종목의 실적발표일을 수동 관리합니다.

### scripts/

#### [scripts/generate_report.py](./scripts/generate_report.py)
이 프로젝트의 핵심 엔진입니다.

주요 역할:
- 가격 다운로드
- 장중 5분봉 덮어쓰기
- 시장 폭 계산
- 시장 점수 계산
- 종목 점수 계산
- 크로스 신호 계산
- 변화 태그 / 운용 태그 / 경고 태그 생성
- 차트용 시계열 생성
- `latest.json`, `history.json` 저장

### docs/

#### [docs/index.html](./docs/index.html)
대시보드 정적 구조입니다.

주요 역할:
- 시장 카드 레이아웃
- 관심종목 요약표
- 시장 차트 영역
- 종목 카드 컨테이너
- 사용설명서 섹션

#### [docs/app.js](./docs/app.js)
프론트엔드 렌더링 로직입니다.

주요 역할:
- `latest.json` 로딩
- 시장 정보 바인딩
- 요약표 렌더링
- 시장 차트 / 종목 차트 렌더링
- 태그 출력
- 접힘 동기화
- 테마 전환

#### [docs/styles.css](./docs/styles.css)
전체 디자인과 반응형 스타일을 담당합니다.

주요 역할:
- 라이트/다크 테마
- 표 / 카드 / 태그 / 차트 스타일
- 모바일 카드형 테이블
- 접힘 버튼 스타일

#### [docs/data/latest.json](./docs/data/latest.json)
현재 화면이 읽는 최신 스냅샷입니다.

#### [docs/data/history.json](./docs/data/history.json)
최근 30일 시장/종목 점수 이력을 저장합니다.

### .github/workflows/

#### [daily-monitor.yml](./.github/workflows/daily-monitor.yml)
데이터 생성과 Pages 배포를 자동화하는 워크플로입니다.
- `DISCORD_WEBHOOK_URL` GitHub Secret이 있으면 중요 알림도 함께 전송합니다.

## 9. 출력 JSON 구조

`docs/data/latest.json`은 대략 아래 구조를 가집니다.

```json
{
  "generated_at_et": "...",
  "market_data_as_of": "...",
  "market": {
    "state": "...",
    "score": 0,
    "confidence": "...",
    "execution_strength": "...",
    "action": "...",
    "top_reasons": [],
    "cross_highlights": [],
    "positive_factors": [],
    "negative_factors": [],
    "metrics": {}
  },
  "watchlist_summary": [],
  "stocks": [],
  "notifications": {
    "count": 0,
    "items": []
  },
  "charts": {
    "market": {}
  },
  "history": {}
}
```

### market
- 시장 카드 전체를 렌더하는 데이터

### watchlist_summary
- 요약 표용 간단한 데이터

### stocks
- 종목별 상세 카드용 데이터

### notifications
- Discord 전송에 사용할 중요 알림 목록
- 시장 레벨 변화, 고스트레스 진입, 일정 임박, 종목 약화, 실적 임박 같은 핵심 변화만 포함

### charts.market
- 시장 차트 시계열

### history
- 최근 점수 이력

## 10. 로컬 실행 방법

### 10.1 환경 준비
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 10.2 리포트 생성
```bash
python scripts/generate_report.py
```

생성 결과:
- `docs/data/latest.json`
- `docs/data/history.json`

### 10.3 로컬 서버 실행
```bash
python -m http.server 4173 --directory docs
```

브라우저:
- `http://localhost:4173`

주의:
- `docs/index.html`을 `file://`로 직접 열면 `fetch("./data/latest.json")` 때문에 정상 동작하지 않을 수 있습니다.

## 11. 유지보수 포인트

### 워치리스트 변경
- [config/watchlist.yml](./config/watchlist.yml) 수정
- 현재 코드는 `정확히 8개 종목`을 기대합니다

### 매크로 일정 변경
- [config/economic_calendar.yml](./config/economic_calendar.yml) 수정

### 실적 일정 변경
- [config/earnings_calendar.yml](./config/earnings_calendar.yml) 수정

### 점수 로직 튜닝
- [scripts/generate_report.py](./scripts/generate_report.py)의
  - `score_market()`
  - `score_stock()`
  - `market_position_tags()`
  - `stock_position_tags()`
를 중심으로 조정

### UI 구조 변경
- 구조: [docs/index.html](./docs/index.html)
- 데이터 바인딩: [docs/app.js](./docs/app.js)
- 스타일: [docs/styles.css](./docs/styles.css)

## 12. 한계와 주의사항

- breadth는 장중 완전 실시간이 아니라 일봉 기준입니다.
- 실적발표일은 현재 수동 캘린더 비중이 큽니다.
- 시장 점수는 해석 가능한 규칙 기반 점수이지, 수익을 보장하는 신호가 아닙니다.
- yfinance / 외부 데이터 소스 품질에 따라 일부 항목은 `확인 필요`로 나올 수 있습니다.
- 이 도구는 투자 조언이 아니라 모니터링과 판단 정리를 돕는 도구입니다.

## 13. 앞으로 확장하기 좋은 방향

- 실적발표일 자동 수집 안정화
- 실적 결과 요약 자동화
- 섹터 강도 확장
- 점수 모드 분리
  - 보수형
  - 균형형
  - 데모형
- UI 단순화 모드
  - 핵심 정보만 표시
  - 세부 정보 최소화

## 14. 요약

이 프로젝트는 `시장 먼저, 종목 나중`이라는 원칙으로 움직입니다.

- 시장은 `S&P500 / Nasdaq / RUT / VIX / 10Y / breadth / 이벤트 / 거래량 프록시`를 함께 봅니다.
- 종목은 `추세 / 상대강도 / 거래량 / 흔들림 / 실적 일정`을 함께 봅니다.
- 결과는 GitHub Actions가 생성하고, GitHub Pages가 가볍게 보여줍니다.

복잡한 스캔보다 `해석 가능한 규칙`, `고정 종목`, `같은 시점 기준 비교`에 초점을 둔 프로젝트입니다.
