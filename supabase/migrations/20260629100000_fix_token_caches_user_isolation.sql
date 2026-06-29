-- token_caches 테이블에 user_id 컬럼 추가 (profiles.id 외래키)
ALTER TABLE public.token_caches 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE;

-- 기존 (exchange, broker_env) 고유 제약 조건 제거
ALTER TABLE public.token_caches 
DROP CONSTRAINT IF EXISTS token_caches_exchange_broker_env_key;

-- 유효한 user_id가 있는 경우에 대한 부분 고유 인덱스 생성 (사용자별 격리)
CREATE UNIQUE INDEX IF NOT EXISTS token_caches_user_id_exchange_broker_env_idx 
ON public.token_caches (user_id, exchange, broker_env) 
WHERE user_id IS NOT NULL;

-- user_id가 NULL인 경우에 대한 부분 고유 인덱스 생성 (시스템 공용 캐시)
CREATE UNIQUE INDEX IF NOT EXISTS token_caches_null_user_id_exchange_broker_env_idx 
ON public.token_caches (exchange, broker_env) 
WHERE user_id IS NULL;
