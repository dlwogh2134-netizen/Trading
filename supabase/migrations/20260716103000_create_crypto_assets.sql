CREATE TABLE IF NOT EXISTS public.crypto_assets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    base_symbol TEXT NOT NULL UNIQUE,
    display_name_ko TEXT,
    display_name_en TEXT,
    aliases TEXT[] NOT NULL DEFAULT '{}',
    default_exchange TEXT NOT NULL DEFAULT 'COINONE'
        CHECK (default_exchange IN ('COINONE', 'BINANCE', 'BINANCE_UM_FUTURES')),
    is_visible BOOLEAN NOT NULL DEFAULT true,
    admin_trading_blocked BOOLEAN NOT NULL DEFAULT false,
    admin_block_reason TEXT,
    admin_note TEXT,
    coinone_listed BOOLEAN NOT NULL DEFAULT false,
    coinone_symbol TEXT,
    coinone_tradable BOOLEAN NOT NULL DEFAULT false,
    coinone_exchange_status TEXT,
    coinone_deposit_status TEXT,
    coinone_withdraw_status TEXT,
    coinone_raw_status JSONB,
    coinone_last_synced_at TIMESTAMPTZ,
    binance_listed BOOLEAN NOT NULL DEFAULT false,
    binance_symbol TEXT,
    binance_tradable BOOLEAN NOT NULL DEFAULT false,
    binance_status TEXT,
    binance_raw_status JSONB,
    binance_last_synced_at TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'API_SYNC',
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_crypto_assets_visible_symbol
    ON public.crypto_assets (is_visible, base_symbol);

CREATE INDEX IF NOT EXISTS idx_crypto_assets_coinone_status
    ON public.crypto_assets (coinone_listed, coinone_tradable, base_symbol);

CREATE INDEX IF NOT EXISTS idx_crypto_assets_binance_status
    ON public.crypto_assets (binance_listed, binance_tradable, base_symbol);

CREATE INDEX IF NOT EXISTS idx_crypto_assets_default_exchange
    ON public.crypto_assets (default_exchange, base_symbol);

ALTER TABLE public.crypto_assets ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'crypto_assets'
          AND policyname = 'service_role_can_manage_crypto_assets'
    ) THEN
        CREATE POLICY service_role_can_manage_crypto_assets
            ON public.crypto_assets
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.crypto_assets TO service_role;
