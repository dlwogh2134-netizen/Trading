import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv('backend/.env')

import requests
from backend.utils.crypto_helper import CryptoHelper
from backend.services.toss_client import TossClient

def run():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    encryption_key = os.getenv("ENCRYPTION_KEY")
    
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}"
    }

    params = {
        "exchange": "eq.TOSS",
        "broker_env": "eq.REAL",
        "user_id": "eq.d4efb544-2a8a-443d-994d-9e7077eddbe7"
    }
    res = requests.get(f"{url}/rest/v1/user_api_keys", headers=headers, params=params)
    record = res.json()[0]
    
    crypto = CryptoHelper(encryption_key)
    access_key = crypto.decrypt(record.get("encrypted_access_key"))
    secret_key = crypto.decrypt(record.get("encrypted_secret_key"))
    account_seq = record.get("toss_account_seq")
    
    client = TossClient(
        client_id=access_key,
        client_secret=secret_key,
        account_seq=account_seq,
        env="REAL"
    )
    
    token = client._get_cached_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tossinvest-Account": str(account_seq)
    }
    
    # holdings API 호출 및 raw 데이터 가져오기
    token = client._get_cached_token()
    url = f"{client.base_url}/api/v1/holdings"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tossinvest-Account": str(account_seq),
        "Content-Type": "application/json"
    }
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        fallback_url = f"{client.base_url}/v1/accounts/holdings"
        res = requests.get(fallback_url, headers=headers)
        
    print("STATUS CODE:", res.status_code)
    data = res.json()
    result = data.get("result", {})
    
    # marketValue 구조 자세히 출력
    print("\n--- marketValue ---")
    print(json.dumps(result.get("marketValue", {}), indent=2, ensure_ascii=False))
    
    # 첫번째 종목 구조 출력
    items = result.get("items", [])
    if items:
        print("\n--- First Item ---")
        print(json.dumps(items[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run()
