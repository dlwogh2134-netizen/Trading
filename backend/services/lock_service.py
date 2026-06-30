import os
import uuid
from contextlib import contextmanager

from backend.services.supabase_client import query_supabase_as_service_role


# 현재 백엔드 프로세스의 고유 소유자 ID입니다.
PROCESS_OWNER_ID = f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"


@contextmanager
def distributed_lock(lock_key: str, duration_seconds: int = 1800):
    """
    Supabase DB 기반 active_locks 테이블을 사용하는 분산 락 컨텍스트 매니저입니다.
    락 획득 실패는 False로 알려주지만, 락 안에서 발생한 예외는 호출자가 처리하도록 전파합니다.
    """
    acquired = False
    try:
        payload = {
            "p_lock_key": lock_key,
            "p_owner_id": PROCESS_OWNER_ID,
            "p_duration_seconds": duration_seconds,
        }
        res = query_supabase_as_service_role("rpc/acquire_lock", "POST", json_data=payload)
        acquired = bool(res)
    except Exception:
        # 락 서비스 장애가 전체 워커를 멈추지 않도록 획득 실패로 처리합니다.
        yield False
        return

    try:
        yield acquired
    finally:
        if acquired:
            try:
                payload = {
                    "p_lock_key": lock_key,
                    "p_owner_id": PROCESS_OWNER_ID,
                }
                query_supabase_as_service_role("rpc/release_lock", "POST", json_data=payload)
            except Exception:
                pass
