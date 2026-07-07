-- 커뮤니티 글에 1단계 답글 구조 추가

ALTER TABLE public.community_posts
ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES public.community_posts(id) ON DELETE CASCADE;

DO $$
BEGIN
    ALTER TABLE public.community_posts
    ADD CONSTRAINT community_posts_parent_not_self
    CHECK (parent_id IS NULL OR parent_id <> id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS community_posts_parent_created_idx
    ON public.community_posts (parent_id, created_at ASC)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS community_posts_thread_symbol_created_idx
    ON public.community_posts (asset_type, symbol, parent_id, created_at DESC)
    WHERE status = 'ACTIVE';

REVOKE INSERT ON public.community_posts FROM authenticated;
GRANT INSERT (user_id, parent_id, asset_type, symbol, exchange, content, status)
    ON public.community_posts TO authenticated;
