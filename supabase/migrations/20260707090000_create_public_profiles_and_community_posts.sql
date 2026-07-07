-- 커뮤니티 공개 프로필과 종목별 커뮤니티 글 테이블 생성

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'USER'
CHECK (role IN ('USER', 'ADMIN'));

REVOKE INSERT, UPDATE, DELETE ON public.profiles FROM authenticated;
GRANT SELECT ON public.profiles TO authenticated;
GRANT UPDATE (nickname, phone, invest_score, invest_type, survey_answers, updated_at)
    ON public.profiles TO authenticated;

CREATE TABLE IF NOT EXISTS public.public_profiles (
    id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    nickname TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN')),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

INSERT INTO public.public_profiles (id, nickname, role, updated_at)
SELECT
    id,
    COALESCE(NULLIF(TRIM(nickname), ''), '익명 사용자') AS nickname,
    COALESCE(role, 'USER') AS role,
    updated_at
FROM public.profiles
ON CONFLICT (id) DO UPDATE SET
    nickname = EXCLUDED.nickname,
    role = EXCLUDED.role,
    updated_at = EXCLUDED.updated_at;

CREATE OR REPLACE FUNCTION public.sync_public_profile()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.public_profiles (id, nickname, role, updated_at)
    VALUES (
        NEW.id,
        COALESCE(NULLIF(TRIM(NEW.nickname), ''), '익명 사용자'),
        COALESCE(NEW.role, 'USER'),
        timezone('utc'::text, now())
    )
    ON CONFLICT (id) DO UPDATE SET
        nickname = EXCLUDED.nickname,
        role = EXCLUDED.role,
        updated_at = EXCLUDED.updated_at;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.sync_public_profile() FROM PUBLIC;

DROP TRIGGER IF EXISTS sync_public_profile_on_profiles ON public.profiles;
CREATE TRIGGER sync_public_profile_on_profiles
    AFTER INSERT OR UPDATE OF nickname, role ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.sync_public_profile();

ALTER TABLE public.public_profiles ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;

REVOKE ALL ON public.public_profiles FROM anon;
REVOKE ALL ON public.public_profiles FROM authenticated;
GRANT SELECT ON public.public_profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.public_profiles TO service_role;

DROP POLICY IF EXISTS authenticated_can_read_public_profiles ON public.public_profiles;
CREATE POLICY authenticated_can_read_public_profiles ON public.public_profiles
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS service_role_can_manage_public_profiles ON public.public_profiles;
CREATE POLICY service_role_can_manage_public_profiles ON public.public_profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE TABLE IF NOT EXISTS public.community_posts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('STOCK', 'CRYPTO')),
    symbol TEXT NOT NULL,
    exchange TEXT,
    content TEXT NOT NULL CHECK (char_length(TRIM(content)) BETWEEN 1 AND 500),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED', 'HIDDEN')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS community_posts_symbol_created_idx
    ON public.community_posts (asset_type, symbol, created_at DESC)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS community_posts_user_created_idx
    ON public.community_posts (user_id, created_at DESC);

DROP TRIGGER IF EXISTS set_community_posts_updated_at ON public.community_posts;
CREATE TRIGGER set_community_posts_updated_at
    BEFORE UPDATE ON public.community_posts
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.community_posts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.community_posts FROM anon;
REVOKE ALL ON public.community_posts FROM authenticated;
GRANT SELECT ON public.community_posts TO authenticated;
GRANT INSERT (user_id, asset_type, symbol, exchange, content, status)
    ON public.community_posts TO authenticated;
GRANT UPDATE (status, updated_at)
    ON public.community_posts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.community_posts TO service_role;

DROP POLICY IF EXISTS authenticated_can_read_active_community_posts ON public.community_posts;
CREATE POLICY authenticated_can_read_active_community_posts ON public.community_posts
    FOR SELECT
    TO authenticated
    USING (
        status = 'ACTIVE'
        OR (SELECT auth.uid()) = user_id
        OR EXISTS (
            SELECT 1
            FROM public.profiles admin_profile
            WHERE admin_profile.id = (SELECT auth.uid())
              AND admin_profile.role = 'ADMIN'
        )
    );

DROP POLICY IF EXISTS users_can_insert_own_active_community_posts ON public.community_posts;
CREATE POLICY users_can_insert_own_active_community_posts ON public.community_posts
    FOR INSERT
    TO authenticated
    WITH CHECK (
        (SELECT auth.uid()) = user_id
        AND status = 'ACTIVE'
        AND char_length(TRIM(content)) BETWEEN 1 AND 500
    );

DROP POLICY IF EXISTS users_can_soft_delete_own_community_posts ON public.community_posts;
CREATE POLICY users_can_soft_delete_own_community_posts ON public.community_posts
    FOR UPDATE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id AND status = 'ACTIVE')
    WITH CHECK ((SELECT auth.uid()) = user_id AND status IN ('ACTIVE', 'DELETED'));

DROP POLICY IF EXISTS admins_can_moderate_community_posts ON public.community_posts;
CREATE POLICY admins_can_moderate_community_posts ON public.community_posts
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.profiles admin_profile
            WHERE admin_profile.id = (SELECT auth.uid())
              AND admin_profile.role = 'ADMIN'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.profiles admin_profile
            WHERE admin_profile.id = (SELECT auth.uid())
              AND admin_profile.role = 'ADMIN'
        )
        AND status IN ('ACTIVE', 'DELETED', 'HIDDEN')
    );

DROP POLICY IF EXISTS service_role_can_manage_community_posts ON public.community_posts;
CREATE POLICY service_role_can_manage_community_posts ON public.community_posts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.community_posts;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
