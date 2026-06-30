ALTER TABLE public.kis_stock_master
    DROP CONSTRAINT IF EXISTS kis_stock_master_market_country_check;

ALTER TABLE public.kis_stock_master
    ADD CONSTRAINT kis_stock_master_market_country_check
    CHECK (market_country IN ('KR', 'US'));

ALTER TABLE public.kis_stock_turnover_latest
    DROP CONSTRAINT IF EXISTS kis_stock_turnover_latest_market_country_check;

ALTER TABLE public.kis_stock_turnover_latest
    ADD CONSTRAINT kis_stock_turnover_latest_market_country_check
    CHECK (market_country IN ('KR', 'US'));

CREATE INDEX IF NOT EXISTS idx_kis_stock_turnover_latest_country_rank
    ON public.kis_stock_turnover_latest (market_country, trading_volume DESC, change_rate DESC, symbol);
