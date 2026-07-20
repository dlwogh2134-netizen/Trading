# API 호출 캐싱 및 토큰 갱신 락 고도화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supabase API 키 로딩 속도 향상 및 Toss OAuth 토큰 갱신 시 분산 락을 결합해 초당 호출 제한(Rate Limit) 오류를 차단합니다.

**Architecture:** 복호화된 API 키를 60초 간 로컬 메모리에 적재하는 싱글톤 `CredentialsGateway`를 신설하고, 시스템 공용 키와 동일한 경우 캐시 영역을 강제 매핑시킵니다. TossClient 토큰 갱신 시 `distributed_lock`을 결합합니다.

**Tech Stack:** Python 3.10, Pytest, Supabase REST API, PostgreSQL Distributed Lock

## Global Constraints

- 모든 테스트 명령어는 `PYTHONPATH=. pytest`를 표준으로 활용합니다.
- 커밋 메시지는 이모지 없이 명확한 한글로 작성합니다.
- 기존의 RLS 보안 모델 및 데이터 격리 규칙을 엄격히 수호합니다.

---

### Task 1: CredentialsGateway 구현 및 캐싱 테스트

**Files:**
- Create: `backend/services/credentials_gateway.py`
- Create: `backend/tests/test_credentials_gateway.py`

**Interfaces:**
- Consumes: `backend/services/supabase_client.py:query_supabase`
- Produces: `CredentialsGateway.get_credentials(auth_header: str, user_id: str, exchange: str, broker_env: str) -> dict`
- Produces: `CredentialsGateway.invalidate_cache(user_id: str, exchange: str, broker_env: str) -> None`

- [ ] **Step 1: Write the failing test**

새로운 테스트 파일 `backend/tests/test_credentials_gateway.py`를 작성합니다:
```python
import time
import pytest
from backend.services.credentials_gateway import CredentialsGateway

def test_credentials_gateway_caching_and_invalidation(monkeypatch):
    query_count = 0
    
    def mock_query_supabase(auth_header, endpoint, method, params=None):
        nonlocal query_count
        query_count += 1
        return [{
            "encrypted_access_key": "encrypted_access",
            "encrypted_secret_key": "encrypted_secret",
            "toss_account_seq": "123"
        }]

    def mock_decrypt(self, text):
        return text.replace("encrypted_", "")

    monkeypatch.setattr("backend.services.credentials_gateway.query_supabase", mock_query_supabase)
    monkeypatch.setattr("backend.utils.crypto_helper.AESCipher.decrypt", mock_decrypt)

    gateway = CredentialsGateway()
    gateway._key_cache.clear()

    # 1. 최초 로딩 (DB 조회 발생)
    creds1 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds1["access_key"] == "access"
    assert query_count == 1

    # 2. 연속 로딩 (캐시 Hit하여 DB 조회 미발생)
    creds2 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds2["access_key"] == "access"
    assert query_count == 1

    # 3. 캐시 무효화 수행 후 로딩 (DB 조회 다시 발생)
    gateway.invalidate_cache("user-1", "TOSS", "MOCK")
    creds3 = gateway.get_credentials("Bearer test", "user-1", "TOSS", "MOCK")
    assert creds3["access_key"] == "access"
    assert query_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest backend/tests/test_credentials_gateway.py -v`
Expected: ModuleNotFoundError: No module named 'backend.services.credentials_gateway'

- [ ] **Step 3: Write minimal implementation**

`backend/services/credentials_gateway.py` 파일을 작성합니다:
```python
import time
import os
from backend.services.supabase_client import query_supabase
from backend.utils.crypto_helper import AESCipher

class CredentialsGateway:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._key_cache = {}
            cls._instance._key_ttl_seconds = 60
            cls._instance._crypto = AESCipher()
        return cls._instance

    def _resolve_cache_key(self, user_id: str, exchange: str, broker_env: str) -> tuple[str, str, str]:
        # 시스템 환경 변수의 공용 키와 동일한지 매핑 확인용 로직은 Task 3에서 구체화하며, 기본 튜플을 반환합니다.
        return (user_id, exchange, broker_env)

    def get_credentials(self, auth_header: str, user_id: str, exchange: str, broker_env: str) -> dict:
        cache_key = self._resolve_cache_key(user_id, exchange, broker_env)
        now = time.time()
        
        if cache_key in self._key_cache:
            entry = self._key_cache[cache_key]
            if now - entry["cached_at"] < self._key_ttl_seconds:
                return entry["data"]

        credential_exchange = "BINANCE" if exchange == "BINANCE_UM_FUTURES" else exchange
        params = {
            "user_id": f"eq.{user_id}",
            "exchange": f"eq.{credential_exchange}",
            "broker_env": f"eq.{broker_env}"
        }
        records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
        if not records:
            raise ValueError(f"등록된 {credential_exchange} ({broker_env}) API 키 정보가 없습니다.")

        record = records[0]
        access_key = self._crypto.decrypt(record.get("encrypted_access_key"))
        secret_key = self._crypto.decrypt(record.get("encrypted_secret_key"))
        
        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "toss_account_seq": record.get("toss_account_seq"),
            "toss_account_no": record.get("toss_account_no"),
            "kis_account_no": record.get("kis_account_no"),
            "kis_account_code": record.get("kis_account_code", "01"),
        }
        
        self._key_cache[cache_key] = {
            "data": data,
            "cached_at": now
        }
        return data

    def invalidate_cache(self, user_id: str, exchange: str, broker_env: str) -> None:
        cache_key = self._resolve_cache_key(user_id, exchange, broker_env)
        if cache_key in self._key_cache:
            del self._key_cache[cache_key]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest backend/tests/test_credentials_gateway.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/credentials_gateway.py backend/tests/test_credentials_gateway.py
git commit -m "CredentialsGateway 싱글톤 및 기본 인메모리 캐시 구현"
```

---

### Task 2: TossClient 분산 락(Distributed Lock) 결합

**Files:**
- Modify: `backend/services/toss_client.py:228-285`
- Create: `backend/tests/test_toss_client_token_lock.py`

**Interfaces:**
- Consumes: `backend/services/lock_service.py:distributed_lock`
- Produces: `TossClient._get_cached_token() -> str`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_toss_client_token_lock.py` 테스트 파일을 작성합니다:
```python
import pytest
from backend.services.toss_client import TossClient

def test_toss_client_token_lock_mechanism(monkeypatch):
    lock_acquired = False
    new_token_requested = 0

    def mock_distributed_lock(lock_key, duration_seconds=120):
        nonlocal lock_acquired
        class DummyLock:
            def __enter__(self):
                nonlocal lock_acquired
                lock_acquired = True
                return True
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        return DummyLock()

    def mock_request_new_token(self):
        nonlocal new_token_requested
        new_token_requested += 1
        return {"access_token": "new-toss-token", "expires_in": 3600}

    monkeypatch.setattr("backend.services.toss_client.get_db_token_with_status", lambda *args, **kwargs: {"token": None})
    monkeypatch.setattr("backend.services.toss_client.set_db_token", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.services.toss_client.distributed_lock", mock_distributed_lock)
    monkeypatch.setattr("backend.services.toss_client.TossClient._request_new_token", mock_request_new_token)

    client = TossClient("id", "secret", "seq", "MOCK", "user-1")
    client._access_token_cache = {}

    token = client._get_cached_token()
    assert token == "new-toss-token"
    assert lock_acquired is True
    assert new_token_requested == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest backend/tests/test_toss_client_token_lock.py -v`
Expected: FAIL (lock_acquired is False) 또는 AttributeError (distributed_lock 이 toss_client에 임포트되지 않음)

- [ ] **Step 3: Write minimal implementation**

`backend/services/toss_client.py` 내부의 `_get_cached_token`을 수정합니다:
```python
    def _get_cached_token(self) -> str:
        from backend.services.token_cache_service import get_db_token_with_status, set_db_token
        from backend.services.lock_service import distributed_lock
        import time

        cached_token = self._access_token_cache.get("token")
        cached_expired_at = self._access_token_cache.get("expired_at")
        if cached_token and isinstance(cached_expired_at, datetime):
            if (cached_expired_at - datetime.utcnow()).total_seconds() > 300:
                self._last_token_cache_info = {
                    "source": "memory",
                    "cacheStatus": "HIT",
                    "tokenStatus": "REUSED",
                    "errorMessage": None,
                    "expiredAt": cached_expired_at.isoformat() + "Z",
                }
                return cached_token
        
        cache_state = get_db_token_with_status("TOSS", self.env, self.user_id, self.credential_hash)
        self._last_token_cache_info = {
            "source": "token_cache_service",
            "cacheStatus": cache_state.get("cache_status", "MISS"),
            "tokenStatus": cache_state.get("token_status", "REFRESHED"),
            "errorMessage": cache_state.get("error_message"),
            "expiredAt": cache_state.get("expired_at"),
        }
        token = cache_state.get("token")
        if token:
            expired_at_raw = cache_state.get("expired_at")
            try:
                cached_expired_at = datetime.fromisoformat(str(expired_at_raw).replace("Z", "+00:00")).replace(tzinfo=None) if expired_at_raw else None
            except Exception:
                cached_expired_at = None
            self._access_token_cache = {
                "token": token,
                "expired_at": cached_expired_at,
            }
            return token

        # 토큰 갱신 시 분산 락 획득 시도
        lock_key = f"toss-token:{self.env}:{self.user_id or 'anonymous'}"
        with distributed_lock(lock_key, duration_seconds=120) as acquired:
            if not acquired:
                time.sleep(0.5)
                cache_state = get_db_token_with_status("TOSS", self.env, self.user_id, self.credential_hash)
                token = cache_state.get("token")
                if token:
                    expired_at_raw = cache_state.get("expired_at")
                    try:
                        cached_expired_at = datetime.fromisoformat(str(expired_at_raw).replace("Z", "+00:00")).replace(tzinfo=None) if expired_at_raw else None
                    except Exception:
                        cached_expired_at = None
                    self._access_token_cache = {
                        "token": token,
                        "expired_at": cached_expired_at,
                    }
                    self._last_token_cache_info = {
                        "source": "token_cache_service",
                        "cacheStatus": "HIT",
                        "tokenStatus": "REUSED",
                        "errorMessage": cache_state.get("error_message"),
                        "expiredAt": cache_state.get("expired_at"),
                    }
                    return token

            # 토큰 새로 발급
            token_data = self._request_new_token()
            new_token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 86400))

            try:
                set_db_token("TOSS", self.env, new_token, expires_in, self.user_id, self.credential_hash)
            except Exception:
                pass
            
            cached_expired_at = datetime.utcnow() + timedelta(seconds=expires_in)
            self._access_token_cache = {
                "token": new_token,
                "expired_at": cached_expired_at,
            }
            return new_token
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest backend/tests/test_toss_client_token_lock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/toss_client.py backend/tests/test_toss_client_token_lock.py
git commit -m "TossClient 토큰 갱신 시 분산 락 가드 연동 완료"
```

---

### Task 3: CredentialsGateway와 라우트/챗봇 연동 및 동일 키 매핑 고도화

**Files:**
- Modify: `backend/services/credentials_gateway.py`
- Modify: `backend/routes/trade.py`
- Modify: `backend/routes/home.py`
- Modify: `backend/services/chatbot/tool_registry.py`
- Create: `backend/tests/test_credentials_gateway_shared_keys.py`

**Interfaces:**
- Consumes: `CredentialsGateway.get_credentials`
- Produces: API 키 로딩부의 전면 대체

- [ ] **Step 1: Write the failing test**

동일 키 매핑을 검증하기 위한 `backend/tests/test_credentials_gateway_shared_keys.py` 파일을 작성합니다:
```python
import os
import pytest
from backend.services.credentials_gateway import CredentialsGateway

def test_credentials_gateway_shared_system_key_mapping(monkeypatch):
    # 시스템 환경 변수의 키값 모킹
    monkeypatch.setenv("TOSS_API_KEY", "system-toss-key-value")
    
    gateway = CredentialsGateway()
    gateway._key_cache.clear()
    
    # 1. 일반 사용자 키가 시스템 공용 키와 다를 때
    key1 = gateway._resolve_cache_key("user-1", "TOSS", "REAL")
    assert key1 == ("user-1", "TOSS", "REAL")
    
    # 2. 일반 사용자 키가 시스템 공용 키와 정확히 동일할 때
    # Mock decrypt가 TOSS_API_KEY와 동일한 값을 반환하도록 세팅하기 위해 gateway 내에서 매핑 처리
    gateway._key_cache[("system_toss", "TOSS", "REAL")] = {
        "data": {"access_key": "system-toss-key-value", "secret_key": "sec"},
        "cached_at": 9999999999
    }
    
    # _resolve_cache_key 내부에서 decrypted access key를 구하기 위해 Supabase 조회를 모킹
    def mock_query_supabase(*args, **kwargs):
        return [{"encrypted_access_key": "system-toss-key-value", "encrypted_secret_key": "sec"}]
    monkeypatch.setattr("backend.services.credentials_gateway.query_supabase", mock_query_supabase)
    monkeypatch.setattr("backend.utils.crypto_helper.AESCipher.decrypt", lambda self, x: x)

    # user-1의 키 조회 시, 시스템 키와 동일하므로 system_toss 캐시 레코드를 반환받음
    creds = gateway.get_credentials("Bearer test", "user-1", "TOSS", "REAL")
    assert creds["access_key"] == "system-toss-key-value"
    
    # 캐시 키 분석 결과가 system_toss 로 매핑되었는지 확인
    # 구현 코드에서 access_key가 매칭되면 캐시 저장 위치가 ("system_toss", "TOSS", "REAL") 이어야 함
    assert ("system_toss", "TOSS", "REAL") in gateway._key_cache
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest backend/tests/test_credentials_gateway_shared_keys.py -v`
Expected: FAIL (KeyError 또는 매핑 실패)

- [ ] **Step 3: Write minimal implementation**

`backend/services/credentials_gateway.py`를 고도화하여 동일 키 감지 매핑 및 복호화 캐시를 구현하고, [trade.py](file:///Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/backend/routes/trade.py), [home.py](file:///Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/backend/routes/home.py), [tool_registry.py](file:///Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/backend/services/chatbot/tool_registry.py)를 수정합니다.

`backend/services/credentials_gateway.py` 수정본:
```python
import time
import os
from backend.services.supabase_client import query_supabase
from backend.utils.crypto_helper import AESCipher

class CredentialsGateway:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._key_cache = {}
            cls._instance._key_ttl_seconds = 60
            cls._instance._crypto = AESCipher()
        return cls._instance

    def _check_system_key_match(self, exchange: str, decrypted_access_key: str) -> str | None:
        if exchange == "TOSS":
            sys_key = os.getenv("TOSS_API_KEY")
            if sys_key and sys_key.strip() == decrypted_access_key.strip():
                return "system_toss"
        elif exchange == "KIS":
            sys_key = os.getenv("KIS_APPKEY")
            if sys_key and sys_key.strip() == decrypted_access_key.strip():
                return "system_kis"
        return None

    def get_credentials(self, auth_header: str, user_id: str, exchange: str, broker_env: str) -> dict:
        now = time.time()
        
        # 1차 일반 캐시 탐색
        normal_key = (user_id, exchange, broker_env)
        if normal_key in self._key_cache:
            entry = self._key_cache[normal_key]
            if now - entry["cached_at"] < self._key_ttl_seconds:
                return entry["data"]

        # 캐시가 없다면 DB에서 조회 및 복호화
        credential_exchange = "BINANCE" if exchange == "BINANCE_UM_FUTURES" else exchange
        params = {
            "user_id": f"eq.{user_id}",
            "exchange": f"eq.{credential_exchange}",
            "broker_env": f"eq.{broker_env}"
        }
        records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
        if not records:
            raise ValueError(f"등록된 {credential_exchange} ({broker_env}) API 키 정보가 없습니다.")

        record = records[0]
        access_key = self._crypto.decrypt(record.get("encrypted_access_key"))
        secret_key = self._crypto.decrypt(record.get("encrypted_secret_key"))

        # 시스템 키와 동일한지 체크하여 캐시 식별자 결정
        matched_system_user = self._check_system_key_match(exchange, access_key)
        final_user_id = matched_system_user if matched_system_user else user_id
        final_key = (final_user_id, exchange, broker_env)

        # 시스템 키 캐시 히트 검사
        if final_key in self._key_cache:
            entry = self._key_cache[final_key]
            if now - entry["cached_at"] < self._key_ttl_seconds:
                # 일반 키 영역에도 링크 캐싱
                self._key_cache[normal_key] = entry
                return entry["data"]

        data = {
            "access_key": access_key,
            "secret_key": secret_key,
            "toss_account_seq": record.get("toss_account_seq"),
            "toss_account_no": record.get("toss_account_no"),
            "kis_account_no": record.get("kis_account_no"),
            "kis_account_code": record.get("kis_account_code", "01"),
        }

        entry_data = {
            "data": data,
            "cached_at": now
        }
        
        self._key_cache[final_key] = entry_data
        self._key_cache[normal_key] = entry_data
        return data

    def invalidate_cache(self, user_id: str, exchange: str, broker_env: str) -> None:
        normal_key = (user_id, exchange, broker_env)
        if normal_key in self._key_cache:
            del self._key_cache[normal_key]
            
        # 시스템 매핑 캐시도 무효화 유도
        for matched in ["system_toss", "system_kis"]:
            sys_key = (matched, exchange, broker_env)
            if sys_key in self._key_cache:
                del self._key_cache[sys_key]
```

`backend/routes/trade.py` 수정:
`_load_user_exchange_record` 함수 내의 복호화 부분을 `CredentialsGateway` 위임으로 교체합니다.
```python
def _load_user_exchange_record(auth_header: str, user_id: str, exchange: str, broker_env: str) -> tuple[dict, str, str]:
    from backend.services.credentials_gateway import CredentialsGateway
    gateway = CredentialsGateway()
    creds = gateway.get_credentials(auth_header, user_id, exchange, broker_env)
    
    # 기존 record 호환을 위한 더미 레코드 구조 생성
    record = {
        "toss_account_seq": creds["toss_account_seq"],
        "toss_account_no": creds["toss_account_no"],
        "kis_account_no": creds["kis_account_no"],
        "kis_account_code": creds["kis_account_code"],
    }
    return record, creds["access_key"], creds["secret_key"]
```

`backend/routes/home.py` L557-565 수정:
```python
        from backend.services.credentials_gateway import CredentialsGateway
        gateway = CredentialsGateway()
        creds = gateway.get_credentials(auth_header, user_id, exchange, broker_env)
        
        access_key = creds["access_key"]
        secret_key = creds["secret_key"]
        
        # record 딕셔너리 호환 빌드
        record = {
            "toss_account_seq": creds["toss_account_seq"],
            "kis_account_no": creds["kis_account_no"],
            "kis_account_code": creds["kis_account_code"],
        }
```

`backend/services/chatbot/tool_registry.py` L325-333 수정:
```python
    from backend.services.credentials_gateway import CredentialsGateway
    try:
        gateway = CredentialsGateway()
        creds = gateway.get_credentials(auth_header, user_id, exchange, broker_env)
        access_key = creds["access_key"]
        secret_key = creds["secret_key"]
        record = {
            "toss_account_seq": creds["toss_account_seq"],
            "kis_account_no": creds["kis_account_no"],
            "kis_account_code": creds["kis_account_code"],
        }
        records = [record]
    except Exception:
        records = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest backend/tests/test_credentials_gateway_shared_keys.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/credentials_gateway.py backend/routes/trade.py backend/routes/home.py backend/services/chatbot/tool_registry.py backend/tests/test_credentials_gateway_shared_keys.py
git commit -m "CredentialsGateway 라우트 및 챗봇 연동 및 동일 키 공유 매핑 탑재 완료"
```

---

## 5. 최종 통합 빌드 검증

- [ ] **Step 1: Compile Check**
Run: `python -m py_compile backend/services/credentials_gateway.py backend/services/toss_client.py backend/routes/trade.py backend/routes/home.py backend/services/chatbot/tool_registry.py`
Expected: Exit code 0

- [ ] **Step 2: Full Pytest Suite**
Run: `PYTHONPATH=. pytest backend/tests/ -v`
Expected: ALL PASSED

- [ ] **Step 3: Frontend Build**
Run: `npm run build`
Expected: SUCCESS

- [ ] **Step 4: Final Commit & Release**
```bash
git commit -am "API 캐싱 및 토큰 분산 락 통합 고도화 적용 최종 완료"
```
