-- trade_proposals 테이블 컬럼 확장
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS symbol TEXT;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS order_amount NUMERIC;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS time_in_force TEXT DEFAULT 'DAY';
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS market_country TEXT;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS currency TEXT;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS client_order_id TEXT;
ALTER TABLE public.trade_proposals ADD COLUMN IF NOT EXISTS external_order_id TEXT;

-- CHECK 제약조건 추가
ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_time_in_force_check;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_time_in_force_check CHECK (time_in_force IN ('DAY', 'CLS'));

ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_market_country_check;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_market_country_check CHECK (market_country IN ('KR', 'US'));

ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_currency_check;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_currency_check CHECK (currency IN ('KRW', 'USD'));

-- client_order_id UNIQUE 제약조건 추가
ALTER TABLE public.trade_proposals DROP CONSTRAINT IF EXISTS trade_proposals_client_order_id_key;
ALTER TABLE public.trade_proposals ADD CONSTRAINT trade_proposals_client_order_id_key UNIQUE (client_order_id);
