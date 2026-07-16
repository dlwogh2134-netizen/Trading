# 코인 종목 마스터 및 관리자 관리 계획

## 목적

코인원, 바이낸스처럼 거래소마다 상장 종목과 심볼 표기가 다른 상황에서도 상세 페이지, 자동완성, 챗봇, 주문 진입 화면이 같은 기준으로 종목을 판단하도록 만든다.

현재 문제의 핵심은 이름 비교가 아니라 `H`, `ALICE`, `BTC` 같은 기본 심볼만 보고 화면이 거래소를 추론한다는 점이다. 그래서 코인원에만 있는 `H`는 표시명이 없으면 그대로 `H`로 보이고, 바이낸스에만 있는 종목도 상세 페이지에서 코인원으로 열릴 수 있다.

완성 기준에서는 DB 없이 API만 매번 조합하기보다, 코인 종목 마스터 테이블 하나를 두고 코인원/바이낸스 상태 컬럼을 같은 행에 저장한다. 화면과 챗봇은 이 테이블에서 필요한 컬럼만 가져다 쓴다.

## 현재 프로젝트 이해

- 코인 랭킹은 `backend/services/home_service.py`에서 코인원 공개 ticker를 호출해 실시간 가격, 등락률, 거래대금 중심으로 만든다.
- 코인 검색은 `backend/services/symbol_metadata.py`의 정적/실시간 메타데이터 조합에 의존한다.
- `/api/symbol/search`, `/api/symbol/lookup`은 검색 결과를 주지만, 상세 페이지가 선택해야 할 거래소를 확정해 주지는 않는다.
- `frontend/src/components/SymbolSearch.jsx`는 검색 결과에서 거래소 정보를 충분히 유지하지 않고 `/asset/CRYPTO/{symbol}` 형태로 이동한다.
- 상세 페이지는 심볼 suffix를 보고 `USDT`면 바이낸스, 아니면 코인원으로 추론한다.
- 관리자 페이지에는 이미 `AdminSymbolReconciliation` 탭이 있으므로, 새 관리자 기능은 이 영역을 확장하는 방식이 가장 자연스럽다.

## 결정 방향

초기 구현은 테이블을 둘로 나누지 않는다. `crypto_assets` 단일 테이블을 만든다.

이유:

- 현재 필요한 거래소는 코인원과 바이낸스 중심이다.
- DB가 이미 많으므로 코인 마스터를 과도하게 정규화하면 관리 부담이 커진다.
- 상세 페이지, 챗봇, 랭킹, 주문 진입 화면은 대부분 “이 종목이 어느 거래소에 있고 거래 가능한가”만 빠르게 알면 된다.
- 나중에 업비트, 빗썸, 바이낸스 선물, 다중 quote market이 크게 늘어나면 그때 거래소별 상태 테이블로 분리해도 늦지 않다.

## 대상 테이블

### `crypto_assets`

코인 기본 정보와 거래소별 상태를 한 행에 저장한다.

권장 컬럼:

```sql
id uuid primary key default gen_random_uuid(),
base_symbol text not null unique,
display_name_ko text,
display_name_en text,
aliases text[] default '{}',

default_exchange text not null default 'COINONE',
is_visible boolean not null default true,
admin_trading_blocked boolean not null default false,
admin_block_reason text,
admin_note text,

coinone_listed boolean not null default false,
coinone_symbol text,
coinone_tradable boolean not null default false,
coinone_exchange_status text,
coinone_deposit_status text,
coinone_withdraw_status text,
coinone_raw_status jsonb,
coinone_last_synced_at timestamptz,

binance_listed boolean not null default false,
binance_symbol text,
binance_tradable boolean not null default false,
binance_status text,
binance_raw_status jsonb,
binance_last_synced_at timestamptz,

source text not null default 'API_SYNC',
last_synced_at timestamptz,
created_at timestamptz not null default now(),
updated_at timestamptz not null default now()
```

초기에는 바이낸스 spot 기준으로만 넣는다. 바이낸스 선물은 실제 화면에서 필요해지는 시점에 `binance_futures_listed`, `binance_futures_symbol`, `binance_futures_tradable`, `binance_futures_status` 컬럼을 추가한다.

## 데이터 적재 방식

### 코인원 동기화

코인원 currencies API에서 다음 정보를 가져온다.

- `symbol`: 기본 심볼, 예: `H`
- `name`: 영문 표시명, 예: `Humanity`
- `deposit_status`
- `withdraw_status`
- 거래 지원 여부 또는 거래 중지 여부를 알 수 있는 상태값

동기화 시 `base_symbol = symbol` 기준으로 upsert한다.

예: 코인원 `Humanity`

- `base_symbol = H`
- `display_name_en = Humanity`
- `coinone_listed = true`
- `coinone_symbol = H`
- `coinone_tradable = API 상태 기준`
- `coinone_deposit_status = suspended`
- `coinone_withdraw_status = normal`
- `default_exchange = COINONE`

### 바이낸스 동기화

바이낸스 exchangeInfo에서 spot 마켓을 가져온다.

- `baseAsset`: 기본 심볼
- `symbol`: 거래 심볼, 예: `ALICEUSDT`
- `status`: `TRADING` 등

동기화 시 `base_symbol = baseAsset` 기준으로 upsert한다.

예: 바이낸스 전용 종목 `ALICE`

- `base_symbol = ALICE`
- `binance_listed = true`
- `binance_symbol = ALICEUSDT`
- `binance_tradable = true`
- `binance_status = TRADING`
- `default_exchange = BINANCE`, 단 코인원에도 있으면 운영 정책에 따라 유지

## 거래소 선택 규칙

상세 페이지, 챗봇, 주문 진입 화면은 더 이상 심볼 문자열만 보고 거래소를 추론하지 않는다.

1. 사용자가 명시적으로 거래소를 선택했으면 그 거래소를 우선한다.
2. 선택 거래소가 해당 종목에 상장되어 있고 거래 가능하면 그대로 사용한다.
3. 선택 거래소가 상장되어 있지 않거나 거래 중지 상태면 사용 가능한 다른 거래소를 제안한다.
4. 거래소 선택이 없으면 `default_exchange`를 사용한다.
5. `admin_trading_blocked = true`면 거래소 API 상태와 무관하게 주문 제안과 실행을 막는다.

예상 결과:

- `H`: 코인원에만 있으므로 코인원으로 열린다. 바이낸스 선택은 막거나 “바이낸스 미상장”으로 안내한다.
- `ALICE`: 바이낸스에만 있으면 바이낸스로 열린다. 코인원 선택은 막거나 “코인원 미상장”으로 안내한다.
- `BTC`: 둘 다 있으면 기본 거래소 또는 사용자 선택 거래소를 사용한다.

## 백엔드 API 설계

### 관리자 API

`GET /api/admin/crypto-symbols`

- 코인 종목 마스터 목록을 반환한다.
- 검색, 거래소 필터, 거래 가능 여부 필터, 관리자 차단 필터를 지원한다.

`POST /api/admin/crypto-symbols/sync`

- 코인원/바이낸스 공개 API를 호출해 `crypto_assets`를 갱신한다.
- 전체 동기화와 거래소별 동기화를 모두 지원한다.

`PATCH /api/admin/crypto-symbols/<base_symbol>`

- 표시명, 별칭, 기본 거래소, 노출 여부, 관리자 거래 차단, 관리자 메모를 수정한다.
- 거래소별 심볼 보정이 필요하면 같은 요청에서 `coinone_symbol`, `binance_symbol`도 수정할 수 있게 한다.

### 공용 검색 API

`GET /api/symbol/search`

코인 결과에 다음 값을 포함한다.

```json
{
  "symbol": "H",
  "name": "Humanity",
  "asset_type": "CRYPTO",
  "default_exchange": "COINONE",
  "exchange_options": ["COINONE"],
  "coinone_listed": true,
  "coinone_tradable": true,
  "binance_listed": false,
  "binance_tradable": false
}
```

`GET /api/symbol/lookup`

- 챗봇과 상세 페이지가 종목명을 코드로 바꿀 때 같은 마스터를 사용한다.
- `H`, `Humanity`, 관리자 별칭 모두 `base_symbol = H`로 해석한다.

### 주문 진입 검색 API

`GET /api/trade/order-entry/symbols`

- `exchange=COINONE`이면 `coinone_listed = true`이고 `coinone_tradable = true`인 종목만 반환한다.
- `exchange=BINANCE`이면 `binance_listed = true`이고 `binance_tradable = true`인 종목만 반환한다.
- `admin_trading_blocked = true`인 종목은 주문 가능 목록에서 제외하거나 차단 사유를 함께 반환한다.

## 프론트엔드 설계

### 공통 검색

`SymbolSearch.jsx`는 검색 결과의 `default_exchange`와 `exchange_options`를 유지한다.

이동 시 가능한 형태:

```text
/asset/CRYPTO/H?exchange=COINONE
/asset/CRYPTO/ALICE?exchange=BINANCE
```

또는 상세 페이지 상태로 `exchange`를 함께 전달한다.

### 상세 페이지

상세 페이지는 다음 순서로 종목을 확정한다.

1. URL 또는 state의 `exchange` 확인
2. `/api/symbol/lookup`으로 마스터 확인
3. 선택 거래소가 유효한지 확인
4. 유효하면 해당 거래소 클라이언트로 가격, 차트, 호가, 체결 조회
5. 유효하지 않으면 거래소 변경 제안 또는 비활성 상태 안내

### 관리자 페이지

기존 관리자 종목 탭에 `crypto_assets` 관리 UI를 추가한다.

목록에서 바로 보여줄 컬럼:

- 기본 심볼
- 한글명/영문명
- 기본 거래소
- 코인원 상장/거래 가능/입출금 상태
- 바이낸스 상장/거래 가능 상태
- 관리자 차단 여부
- 마지막 동기화 시간

수정 모달에서 관리할 값:

- 표시명
- 별칭
- 기본 거래소
- 노출 여부
- 관리자 거래 차단
- 차단 사유
- 관리자 메모
- 필요한 경우 거래소별 심볼 보정

## 챗봇 적용

챗봇은 사용자가 “휴머니티”, “H”, “ALICE”처럼 입력했을 때 먼저 `crypto_assets` 기준으로 종목을 찾는다.

챗봇 응답 원칙:

- 상장 거래소가 하나면 그 거래소를 명확히 말한다.
- 사용자가 요청한 거래소에 없으면 “해당 거래소에는 상장되어 있지 않습니다”라고 안내한다.
- 거래 중지 또는 관리자 차단 상태면 매수/매도 제안으로 이어가지 않는다.
- 둘 이상의 거래소에 있으면 기본 거래소를 사용하되, 다른 거래소 선택 가능성을 함께 안내한다.

## 구현 작업 순서

### 1. DB 마이그레이션 추가

`supabase/migrations`에 `crypto_assets` 테이블을 추가한다.

완료 기준:

- 기본 심볼 unique 제약이 있다.
- 코인원/바이낸스 상태 컬럼이 있다.
- 관리자 차단/메모 컬럼이 있다.
- RLS 또는 관리자 API 접근 정책이 기존 관리자 테이블 방식과 맞는다.

### 2. 백엔드 저장소와 동기화 서비스 추가

`backend/services/crypto_asset_repository.py`

- 목록 조회
- 단건 조회
- upsert
- 관리자 수정

`backend/services/crypto_asset_sync_service.py`

- 코인원 공개 API 수집
- 바이낸스 exchangeInfo 수집
- `base_symbol` 기준 병합
- 거래 가능 상태 계산

완료 기준:

- `H`는 코인원 전용 종목으로 저장된다.
- 바이낸스 전용 종목은 `binance_listed = true`, `coinone_listed = false`로 저장된다.
- 공통 종목은 같은 행에 코인원/바이낸스 상태가 같이 들어간다.

### 3. 관리자 API 추가

`backend/routes/admin_symbols.py`에 코인 마스터 API를 추가한다.

완료 기준:

- 관리자 화면에서 목록 조회가 가능하다.
- 수동 동기화 버튼을 누르면 DB가 갱신된다.
- 표시명, 별칭, 기본 거래소, 차단 상태를 수정할 수 있다.

### 4. 검색/상세/주문 API 연결

`symbol_metadata.py` 또는 새 서비스에서 `crypto_assets`를 우선 조회한다.

완료 기준:

- `/api/symbol/search`가 코인 결과에 `default_exchange`와 `exchange_options`를 포함한다.
- `/api/symbol/lookup`이 별칭과 표시명을 인식한다.
- `/api/trade/order-entry/symbols`가 선택 거래소 컬럼으로 필터링한다.
- 상세 페이지가 바이낸스 전용 종목을 코인원으로 열지 않는다.

### 5. 프론트엔드 수정

`SymbolSearch.jsx`, 데스크톱/모바일 상세 페이지, 관리자 종목 탭을 수정한다.

완료 기준:

- 검색 결과 선택 시 거래소 정보가 유지된다.
- 상세 페이지에서 잘못된 거래소 자동 선택이 사라진다.
- 관리자 페이지에서 코인 마스터를 확인하고 수정할 수 있다.

### 6. 챗봇 도구 연결

챗봇의 종목 해석 흐름에서 `crypto_assets`를 우선 사용한다.

완료 기준:

- “휴머니티”는 `H`, 코인원 전용으로 해석된다.
- “바이낸스에서 H” 요청은 미상장 안내를 한다.
- “ALICE”는 바이낸스 전용이면 바이낸스 기준으로 해석된다.
- 거래 중지/관리자 차단 종목은 주문 제안으로 이어지지 않는다.

### 7. 문서와 테스트 업데이트

`database_specification.md`, `project_structure.md` 등 관련 문서를 갱신한다.

테스트 후보:

- 코인원 전용 종목 검색
- 바이낸스 전용 종목 검색
- 공통 종목 검색
- 거래 중지 종목 필터
- 관리자 차단 종목 필터
- 상세 페이지 거래소 선택 유지
- 챗봇 종목 해석

## 검증 시나리오

### H / Humanity

1. 동기화 후 `crypto_assets`에 `base_symbol = H`가 있어야 한다.
2. `coinone_listed = true`, `binance_listed = false`여야 한다.
3. 검색 결과는 `Humanity` 또는 관리자 한글명 `휴머니티`로 표시될 수 있어야 한다.
4. 상세 페이지는 코인원으로 열려야 한다.
5. 바이낸스 선택 시 미상장 안내가 나와야 한다.

### Binance-only 종목

1. 예: `ALICE`
2. `binance_listed = true`, `coinone_listed = false`여야 한다.
3. 검색 결과 선택 시 바이낸스로 열려야 한다.
4. 코인원 주문 진입 검색에는 나오면 안 된다.

### 공통 종목

1. 예: `BTC`
2. 코인원/바이낸스 상태가 같은 행에 저장되어야 한다.
3. 사용자가 선택한 거래소가 유지되어야 한다.
4. 선택이 없으면 `default_exchange`를 따른다.

## 리스크와 후속 분리 기준

단일 테이블은 지금 규모에서는 관리가 쉽지만, 아래 조건이 생기면 거래소별 상태 테이블 분리를 검토한다.

- 거래소가 4개 이상으로 늘어난다.
- 한 기본 심볼에 quote market이 여러 개 붙는다.
- 바이낸스 spot/futures/options 상태를 모두 세밀하게 관리해야 한다.
- 거래소별 수수료, 최소 주문 수량, 주문 단위, 입출금 네트워크 상태까지 관리해야 한다.

그 전까지는 `crypto_assets` 단일 테이블을 기준으로 구현하는 것이 현재 프로젝트에는 더 현실적이다.

## 최종 완료 기준

- 관리자 페이지에서 코인 종목 마스터를 조회, 동기화, 수정할 수 있다.
- 코인원 전용 종목이 바이낸스로 잘못 열리지 않는다.
- 바이낸스 전용 종목이 코인원으로 잘못 열리지 않는다.
- 거래 중지 또는 관리자 차단 종목은 주문 제안과 주문 실행에서 차단된다.
- 랭킹은 기존처럼 가격/거래대금 데이터로 쓰되, 종목 표시명과 거래 가능 여부는 `crypto_assets`를 참조한다.
- 챗봇은 종목명, 별칭, 거래소 상태를 같은 기준으로 해석한다.
