CREATE OR REPLACE FUNCTION public.cleanup_expired_disclosures(
    p_cutoff_date DATE,
    p_batch_size INTEGER DEFAULT 5000
)
RETURNS TABLE (
    deleted_disclosures INTEGER,
    deleted_analyses INTEGER,
    deleted_chunks INTEGER,
    has_more BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    selected_count INTEGER;
BEGIN
    IF p_batch_size < 1 OR p_batch_size > 10000 THEN
        RAISE EXCEPTION 'p_batch_size must be between 1 and 10000';
    END IF;

    CREATE TEMP TABLE _expired_disclosure_keys ON COMMIT DROP AS
    SELECT rcept_no
    FROM public.dart_disclosures
    WHERE rcept_dt < p_cutoff_date
    ORDER BY rcept_dt, rcept_no
    LIMIT p_batch_size;

    GET DIAGNOSTICS selected_count = ROW_COUNT;
    IF selected_count = 0 THEN
        RETURN QUERY SELECT 0, 0, 0, FALSE;
        RETURN;
    END IF;

    DELETE FROM public.knowledge_chunks AS chunks
    USING _expired_disclosure_keys AS expired
    WHERE chunks.source_type = 'DISCLOSURE'
      AND chunks.source_id = expired.rcept_no;
    GET DIAGNOSTICS deleted_chunks = ROW_COUNT;

    DELETE FROM public.dart_disclosure_analyses AS analyses
    USING _expired_disclosure_keys AS expired
    WHERE analyses.rcept_no = expired.rcept_no;
    GET DIAGNOSTICS deleted_analyses = ROW_COUNT;

    DELETE FROM public.dart_disclosures AS disclosures
    USING _expired_disclosure_keys AS expired
    WHERE disclosures.rcept_no = expired.rcept_no;
    GET DIAGNOSTICS deleted_disclosures = ROW_COUNT;

    SELECT EXISTS (
        SELECT 1
        FROM public.dart_disclosures
        WHERE rcept_dt < p_cutoff_date
    ) INTO has_more;

    RETURN NEXT;
END;
$$;

REVOKE ALL ON FUNCTION public.cleanup_expired_disclosures(DATE, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.cleanup_expired_disclosures(DATE, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.cleanup_expired_disclosures(DATE, INTEGER) TO service_role;
