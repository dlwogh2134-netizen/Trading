ALTER TABLE public.kis_stock_master
    DROP CONSTRAINT IF EXISTS kis_stock_master_market_segment_check;

ALTER TABLE public.kis_stock_master
    ADD CONSTRAINT kis_stock_master_market_segment_check
    CHECK (market_segment IN ('KOSPI', 'KOSDAQ', 'KONEX', 'NASDAQ', 'NYSE', 'AMEX', 'US', 'OTHER'));

ALTER TABLE public.kis_stock_turnover_latest
    DROP CONSTRAINT IF EXISTS kis_stock_turnover_latest_market_segment_check;

ALTER TABLE public.kis_stock_turnover_latest
    ADD CONSTRAINT kis_stock_turnover_latest_market_segment_check
    CHECK (market_segment IN ('KOSPI', 'KOSDAQ', 'KONEX', 'NASDAQ', 'NYSE', 'AMEX', 'US', 'OTHER'));
