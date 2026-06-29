import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# 백엔드 환경 변수 로드
load_dotenv("/Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/backend/.env")
sys.path.append("/Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject")

from backend.utils.crypto_helper import CryptoHelper
from backend.services.binance_client import BinanceClient
from backend.services.coinone_client import CoinoneClient
from backend.services.toss_client import TossClient
from backend.services.kis_client import KISClient

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

def test_connections():
    print("ENCRYPTION_KEY:", ENCRYPTION_KEY[:5] + "..." if ENCRYPTION_KEY else "None")
    
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    }
    
    # ka6865@naver.com 계정 ID 확인
    url_profiles = f"{SUPABASE_URL}/rest/v1/profiles?email=eq.ka6865@naver.com"
    res_prof = requests.get(url_profiles, headers=headers)
    if res_prof.status_code != 200 or not res_prof.json():
        print("profiles에서 ka6865@naver.com을 찾을 수 없습니다.")
        return
        
    user_id = res_prof.json()[0].get("id")
    print(f"User ID: {user_id}")
    
    # user_api_keys 조회
    url_keys = f"{SUPABASE_URL}/rest/v1/user_api_keys?user_id=eq.{user_id}"
    res_keys = requests.get(url_keys, headers=headers)
    if res_keys.status_code != 200:
        print("API Key 조회 실패")
        return
        
    records = res_keys.json()
    crypto = CryptoHelper(ENCRYPTION_KEY)
    
    for r in records:
        exchange = r.get("exchange")
        broker_env = r.get("broker_env")
        print(f"\n==========================================")
        print(f"테스트 거래소: {exchange} ({broker_env})")
        print(f"==========================================")
        
        try:
            enc_access = r.get("encrypted_access_key")
            enc_secret = r.get("encrypted_secret_key")
            access = crypto.decrypt(enc_access) if enc_access else None
            secret = crypto.decrypt(enc_secret) if enc_secret else None
            
            print("1. 복호화 결과:")
            print(f"   Access: {access[:10]}... (길이: {len(access)})" if access else "   Access: None")
            print(f"   Secret: {secret[:10]}... (길이: {len(secret)})" if secret else "   Secret: None")
            
            if exchange == "BINANCE":
                print("2. 바이낸스 API 연결 테스트...")
                client = BinanceClient(access, secret)
                res_bal = client.get_balance()
                print("   [성공] 바이낸스 잔고 조회 완료.")
                print(f"   평가금액: {res_bal.get('total_evaluation')} USDT, 현금: {res_bal.get('available_cash')} USDT")
                print(f"   보유자산 수: {len(res_bal.get('holdings', []))}")
                
            elif exchange == "COINONE":
                print("2. 코인원 API 연결 테스트...")
                client = CoinoneClient(access, secret)
                res_bal = client.get_balance()
                print("   [성공] 코인원 잔고 조회 완료.")
                print(f"   평가금액: {res_bal.get('total_evaluation')} KRW, 현금: {res_bal.get('available_cash')} KRW")
                print(f"   보유자산 수: {len(res_bal.get('holdings', []))}")
                
            elif exchange == "TOSS":
                print("2. 토스 API 연결 테스트...")
                # MOCK 혹은 REAL에 맞춰 테스트
                client = TossClient(client_id=access, client_secret=secret, account_seq=r.get("toss_account_seq"), env=broker_env)
                
                print("   계좌 목록 조회 시도...")
                accounts = client.get_accounts()
                print(f"   [성공] 조회된 계좌 개수: {len(accounts)}")
                
                print("   보유자산 조회 시도...")
                res_bal = client.get_balance()
                print("   [성공] 토스 잔고 조회 완료.")
                print(f"   평가금액: {res_bal.get('total_evaluation')} KRW, 현금: {res_bal.get('available_cash')} KRW")
                
            elif exchange == "KIS":
                print("2. 한국투자증권 API 연결 테스트...")
                client = KISClient(
                    appkey=access,
                    appsecret=secret,
                    cano=r.get("kis_account_no"),
                    acnt_prdt_cd=r.get("kis_account_code", "01"),
                    env=broker_env
                )
                res_bal = client.get_balance()
                print("   [성공] KIS 잔고 조회 완료.")
                print(f"   평가금액: {res_bal.get('total_evaluation')} KRW, 현금: {res_bal.get('available_cash')} KRW")
                
        except Exception as e:
            print(f"   [실패] 에러 발생: {str(e)}")

if __name__ == "__main__":
    test_connections()
