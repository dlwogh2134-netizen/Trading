import requests

def classify_error(exchange: str, exception: Exception) -> str:
    """
    발생한 예외 정보를 기반으로 FATAL(인증 오류) 또는 TEMPORARY(일시적 오류) 에러 유형을 판별합니다.
    """
    err_msg = str(exception)
    
    # 1. 공통 네트워크/연결/타임아웃 관련 예외 체크
    if isinstance(exception, (requests.exceptions.ConnectionError, 
                               requests.exceptions.Timeout, 
                               requests.exceptions.ConnectTimeout, 
                               requests.exceptions.ReadTimeout)):
        return "TEMPORARY"
        
    timeout_keywords = ["timeout", "timed out", "connection refused", "connection error", "max retries exceeded", "502", "503", "504"]
    if any(kw in err_msg.lower() for kw in timeout_keywords):
        return "TEMPORARY"
        
    # 2. 거래소별 에러 파싱
    if exchange == "TOSS":
        fatal_keywords = ["401", "403", "invalid_client", "unauthorized", "인증"]
        if any(kw in err_msg.lower() for kw in fatal_keywords):
            return "FATAL"
            
    elif exchange == "KIS":
        # rt_cd는 단순히 리턴 코드가 존재한다는 응답 문자열에 포함되므로 fatal로 판단해선 안 됩니다.
        # KIS 레이트 리밋 관련 에러 코드 EGW00201 등은 TEMPORARY로 분류해야 함.
        if "egw00201" in err_msg.lower() or "too many requests" in err_msg.lower():
            return "TEMPORARY"
        fatal_keywords = ["appkey", "appsecret", "인증", "유효하지 않은", "auth", "credential"]
        if any(kw in err_msg.lower() for kw in fatal_keywords):
            return "FATAL"
            
    elif exchange == "COINONE":
        fatal_keywords = ["101", "102", "103", "104", "107", "parameter error", "invalid access token", "invalid signature"]
        if any(kw in err_msg.lower() for kw in fatal_keywords):
            return "FATAL"
        if "코드 12" in err_msg or "코드 11" in err_msg:
            return "TEMPORARY"
            
    elif exchange == "BINANCE":
        fatal_keywords = ["401", "403", "-1022", "-2015", "signature", "api key", "unauthorized"]
        if any(kw in err_msg.lower() for kw in fatal_keywords):
            return "FATAL"
            
    return "FATAL"
