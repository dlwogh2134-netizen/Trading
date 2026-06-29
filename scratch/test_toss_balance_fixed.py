import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv('backend/.env')

import requests
from backend.utils.crypto_helper import CryptoHelper
from backend.services.toss_client import TossClient

def run_test():
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    encryption_key = os.getenv("ENCRYPTION_KEY")
    
    if not all([url, service_key, encryption_key]):
        print("Error: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, or ENCRYPTION_KEY is missing in .env")
        return

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}"
    }

    # user_api_keys 테이블에서 Toss REAL 키 정보 조회
    print("Fetching Toss REAL API key from Supabase...")
    params = {
        "exchange": "eq.TOSS",
        "broker_env": "eq.REAL",
        "user_id": "eq.d4efb544-2a8a-443d-994d-9e7077eddbe7"
    }
    res = requests.get(f"{url}/rest/v1/user_api_keys", headers=headers, params=params)
    if res.status_code != 200:
        print(f"Failed to fetch keys: {res.text}")
        return

    records = res.json()
    if not records:
        print("No TOSS REAL keys found in DB.")
        return

    record = records[0]
    print(f"Found TOSS record for user_id: {record.get('user_id')}")

    # 복호화
    crypto = CryptoHelper(encryption_key)
    access_key = crypto.decrypt(record.get("encrypted_access_key"))
    secret_key = crypto.decrypt(record.get("encrypted_secret_key"))
    account_seq = record.get("toss_account_seq")

    print(f"Successfully decrypted keys. AccountSeq: {account_seq}")

    # TossClient 기동
    client = TossClient(
        client_id=access_key,
        client_secret=secret_key,
        account_seq=account_seq,
        env="REAL"
    )

    print("Calling TossClient.get_balance()...")
    try:
        balance = client.get_balance()
        print("\n=== BALANCE RESULT ===")
        print(f"Total Evaluation: {balance.get('total_evaluation')}")
        print(f"Available Cash: {balance.get('available_cash')}")
        print(f"Number of Holdings: {len(balance.get('holdings', []))}")
        print("\nHoldings sample (top 3):")
        for i, h in enumerate(balance.get('holdings', [])[:3]):
            print(f" - {h.get('name')} ({h.get('symbol')}): qty={h.get('qty')}, avg_price={h.get('avg_price')}, current_price={h.get('current_price')}, profit={h.get('profit')}, eval_amount={h.get('eval_amount')}")
    except Exception as e:
        print(f"Toss API Call failed: {e}")

if __name__ == "__main__":
    run_test()
