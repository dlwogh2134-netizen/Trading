# 챗봇 메인 LLM — LangGraph Agent + Gemini 3단 Failover + GPT 폴백 전환 설계

- **작성일**: 2026-07-20
- **범위**: `backend/services/chatbot/` 내 챗봇 메인 LLM 호출 구조
- **범위 외**: DART 공시 분석(`dart_analysis_service.py`), 뉴스 요약(`news_summary_service.py`), 웹 폴백 검색(`web_fallback_search_service.py`)은 기존 Failover 유지

---

## 1. 배경 및 목적

### 현재 문제점

1. **단일 모델, Failover 없음**: 챗봇 메인 LLM(`llm_client.py`)이 OpenAI 단일 모델(`gpt-4.1-mini`)만 사용하며, 장애나 지연 시 즉각 실패한다.
2. **극도로 제한된 컨텍스트**: `max_input_chars=2000`, `max_history_messages=16`, `max_tool_calls=3`, `max_tool_data_chars=6000`으로 하드코딩되어 있어 대화 맥락 유실, 도구 결과 누락, 복합 질문 처리 불가 문제가 빈번히 발생한다.
3. **경직된 하드코딩 라우팅**: `chat_service.py`의 `reply()` 메서드(1130줄)가 키워드 기반 정적 라우팅으로 도구를 선택하며, LLM의 자율적 판단 기회를 시스템 단에서 차단하고 있다.
4. **비용 구조**: OpenAI API 비용이 누적되고 있으며, Gemini API 키가 이미 프로젝트에 존재하지만 챗봇에서는 미사용 중이다.

### 목표

- Gemini를 메인 LLM으로 전환하여 **비용 절감** 및 **대형 컨텍스트 윈도우 활용**
- Gemini 3.5 Pro → Gemini 3.5 Flash → GPT-4.1-mini 순서의 **3단 Failover**로 가용성 확보
- **LangGraph Agent** 도입으로 복합 질문(뉴스+공시+시세 등) 처리 능력 확보
- 기존 도구(tool_registry.py) 비즈니스 로직은 100% 유지하면서 래퍼만 교체

---

## 2. 아키텍처

### 2.1 전체 흐름

```text
사용자 질문 (SSE POST /api/chatbot/stream)
    │
    ▼
┌─────────────────────────────────────────────┐
│  Flask 라우트 (chatbot.py)                  │
│  - 인증, 사용량 체크                         │
│  - AgentService.run() 호출                   │
│  - astream_events → SSE 변환                 │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  AgentService (chat_service.py 교체)         │
│  - 시스템 프롬프트 조립                       │
│  - 대화 이력 로드                             │
│  - 투자성향/메모리/RAG 컨텍스트 주입           │
│  - LangGraph Agent 실행                      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  LangGraph StateGraph                        │
│                                              │
│  [START]                                     │
│     │                                        │
│     ▼                                        │
│  [call_model] ─── tool_calls? ───→ [tools]  │
│     │ no                              │      │
│     ▼                                 │      │
│  [END]  ←─────────────────────────────┘      │
│                                              │
│  LLM 내부 Failover:                          │
│    Gemini 3.5 Pro                            │
│      ↓ 실패                                  │
│    Gemini 3.5 Flash                          │
│      ↓ 실패                                  │
│    GPT-4.1-mini                              │
└──────────────────────────────────────────────┘
```

### 2.2 LangGraph 상태 정의

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    trace_steps: list[dict]       # SSE trace 이벤트용
    user_id: str
    auth_header: str
    request_id: str
```

### 2.3 LangGraph 노드

| 노드 | 역할 |
|------|------|
| `call_model` | Failover LLM에 messages를 전달하고 응답(텍스트 또는 tool_calls)을 반환 |
| `tools` | LLM이 선택한 도구를 실행하고 `ToolMessage`로 결과를 messages에 추가 |

### 2.4 LangGraph 엣지

| 출발 | 조건 | 도착 |
|------|------|------|
| `START` | 항상 | `call_model` |
| `call_model` | tool_calls 존재 | `tools` |
| `call_model` | tool_calls 없음 (최종 답변) | `END` |
| `tools` | 항상 (도구 결과 합성을 위해) | `call_model` |

> **주의**: `tools` → `call_model` 루프는 **max_tool_rounds** 제한(기본 5회)을 두어 무한 루프를 방지한다.

---

## 3. Failover LLM 래퍼

### 3.1 구성

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

primary = ChatGoogleGenerativeAI(
    model="gemini-3.5-pro",
    google_api_key=GEMINI_API_KEY,
    temperature=0.3,
    max_output_tokens=2048,
)
secondary = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.3,
    max_output_tokens=2048,
)
fallback = ChatOpenAI(
    model="gpt-4.1-mini",
    api_key=OPENAI_API_KEY,
    temperature=0.3,
    max_tokens=2048,
)

llm = primary.with_fallbacks([secondary, fallback])
```

### 3.2 환경변수 설정

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `GEMINI_API_KEY` | (기존 존재) | Google Gemini API 키 |
| `OPENAI_API_KEY` | (기존 존재) | OpenAI API 키 (폴백용) |
| `CHATBOT_PRIMARY_MODEL` | `gemini-3.5-pro` | 1순위 모델 |
| `CHATBOT_SECONDARY_MODEL` | `gemini-3.5-flash` | 2순위 모델 |
| `CHATBOT_FALLBACK_MODEL` | `gpt-4.1-mini` | 3순위 GPT 폴백 |
| `CHATBOT_PRIMARY_PROVIDER` | `gemini` | 1순위 프로바이더 (`gemini` / `openai`) |
| `CHATBOT_SECONDARY_PROVIDER` | `gemini` | 2순위 프로바이더 |
| `CHATBOT_FALLBACK_PROVIDER` | `openai` | 3순위 프로바이더 |
| `CHATBOT_TEMPERATURE` | `0.3` | LLM temperature |
| `CHATBOT_MAX_OUTPUT_TOKENS` | `2048` | 최대 출력 토큰 |

### 3.3 Failover 동작

- 각 모델 호출 시 HTTP 오류(429, 500, 503 등), 타임아웃, API 키 미설정 시 자동으로 다음 모델로 전환
- LangChain의 `with_fallbacks()`가 내부적으로 예외를 catch하고 다음 모델을 시도
- 모든 모델 실패 시 최종 예외를 raise → Flask 라우트에서 `format_error_payload()`로 사용자 친화 에러 반환

---

## 4. Tool 마이그레이션

### 4.1 전략

기존 `tool_registry.py`의 비즈니스 로직 함수는 **100% 유지**하고, 새로운 `langchain_tools.py`에서 `@tool` 데코레이터로 래핑하여 LangGraph Agent에 바인딩한다.

### 4.2 매핑 예시

```python
# langchain_tools.py
from langchain_core.tools import tool
from backend.services.chatbot.tool_registry import (
    get_asset_price as _get_asset_price,
    search_web as _search_web,
    # ... 나머지 13개 함수
)

@tool
def get_asset_price(query: str, exchange: str = "", broker_env: str = "") -> str:
    """주식/코인/ETF의 현재가를 조회합니다. 종목명 또는 심볼 코드로 검색할 수 있습니다."""
    # auth_header는 AgentState에서 주입
    result = _get_asset_price(state_auth_header, query, exchange=exchange, broker_env=broker_env)
    return json.dumps(result, ensure_ascii=False, default=str)
```

### 4.3 auth_header 전달 방식

LangGraph의 `tools` 노드에서 도구를 실행할 때, `AgentState.auth_header`를 각 도구 함수에 주입한다. LangChain `@tool`은 직접 state를 받지 못하므로, `tools` 노드 내부에서 기존 `tool_registry` 함수를 직접 호출하는 방식으로 처리한다.

```python
def tools_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    auth_header = state["auth_header"]
    
    tool_results = []
    for tool_call in last_message.tool_calls:
        # tool_registry의 기존 함수를 직접 호출
        result = execute_tool(tool_call, auth_header)
        tool_results.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
    
    return {"messages": tool_results}
```

### 4.4 마이그레이션 대상 도구 목록

| 도구 | 원본 함수 | LangGraph 바인딩 |
|------|----------|-----------------|
| `get_asset_price` | tool_registry.get_asset_price | ✅ |
| `get_asset_orderbook` | tool_registry.get_asset_orderbook | ✅ |
| `get_asset_candles` | tool_registry.get_asset_candles | ✅ |
| `get_asset_outlook` | tool_registry.get_asset_outlook | ✅ |
| `get_crypto_market_context` | tool_registry.get_crypto_market_context | ✅ |
| `get_holdings` | tool_registry.get_holdings | ✅ |
| `get_portfolio_summary` | tool_registry.get_portfolio_summary | ✅ |
| `get_exchange_rate` | tool_registry.get_exchange_rate | ✅ |
| `get_asset_krw_conversion` | tool_registry.get_asset_krw_conversion | ✅ |
| `get_market_calendar` | tool_registry.get_market_calendar | ✅ |
| `get_home_market_rankings` | tool_registry.get_home_market_rankings | ✅ |
| `search_trade_history` | tool_registry.search_trade_history | ✅ |
| `list_open_orders` | tool_registry.list_open_orders | ✅ |
| `add_watchlist_item` | tool_registry.add_watchlist_item | ✅ |
| `remove_watchlist_item` | tool_registry.remove_watchlist_item | ✅ |
| `search_web` | tool_registry.search_web | ✅ |

---

## 5. 컨텍스트 제한 완화

### 5.1 변경 전후 비교

| 파라미터 | 변경 전 | 변경 후 | 근거 |
|---------|--------|--------|------|
| `max_input_chars` | 2,000 | 50,000 | Gemini Pro 2M 토큰, Flash 1M 토큰 지원 |
| `max_history_messages` | 16 | 50 | 멀티턴 대화 맥락 유지 (약 25 턴) |
| `max_tool_calls` | 3 | 10 | 복합 질문에서 여러 Tool 연속 호출 허용 |
| `max_tool_data_chars` | 6,000 | 30,000 | 뉴스/공시 원문 누락 방지 |
| `max_output_tokens` | 1,024 | 2,048 | 상세 분석 답변 허용 |

### 5.2 비용 안전장치

- Gemini Pro는 GPT-4o 대비 토큰당 비용이 낮지만, 컨텍스트를 대폭 늘리면 절대 비용이 증가할 수 있다.
- 기존 `_consume_shared_usage` RPC는 유지하여 일일 토큰 한도(`CHATBOT_DAILY_TOKEN_LIMIT`)로 비용 상한을 통제한다.
- `CHATBOT_DAILY_TOKEN_LIMIT` 기본값을 100,000 → 500,000으로 상향 조정한다.
- LangGraph의 `max_tool_rounds` 제한(기본 5)으로 무한 Tool 루프를 방지한다.

---

## 6. SSE 스트리밍 전환

### 6.1 현재 방식

`llm_client.py`의 `stream_reply()`가 OpenAI SSE를 수동 파싱하여 `on_delta` 콜백으로 토큰을 전달하고, `chatbot.py`의 SSE 생성기가 이를 `event: delta` 이벤트로 변환한다.

### 6.2 변경 방식

LangGraph의 `astream_events(version="v2")`를 사용하여 Agent 실행 중 발생하는 이벤트를 SSE로 변환한다.

```python
async for event in agent.astream_events(input_messages, config, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        # 토큰 단위 스트리밍 → SSE delta
        token = event["data"]["chunk"].content
        yield format_sse_event("delta", {"text": token})
    elif kind == "on_tool_start":
        # 도구 실행 시작 → SSE trace
        yield format_sse_event("trace", {"kind": "tool", "label": event["name"]})
    elif kind == "on_tool_end":
        # 도구 실행 완료 → SSE trace
        yield format_sse_event("trace", {"kind": "tool_done", "label": event["name"]})
```

### 6.3 Flask 비동기 처리

Flask는 기본적으로 동기 프레임워크이므로, LangGraph의 async API를 Flask에서 사용하기 위해:
- 옵션 A: `asyncio.run()` 또는 `async_to_sync` 래퍼로 동기 컨텍스트에서 실행
- 옵션 B: 기존처럼 별도 스레드에서 실행하고 `queue.Queue`로 SSE 이벤트 전달 (현재 패턴 유지)

**옵션 B를 선택한다** — 기존 `chatbot.py`의 스레드+큐 패턴이 이미 안정적으로 동작하고 있으므로, LangGraph의 동기 API(`stream_events`)를 스레드에서 실행하고 큐로 SSE 이벤트를 전달하는 구조를 유지한다.

---

## 7. 기존 기능 호환성

### 7.1 유지해야 하는 기존 기능

| 기능 | 현재 위치 | LangGraph 전환 후 |
|------|----------|------------------|
| 주문 파서 (`order_parser.py`) | `chat_service.reply()` 내부 | Agent의 시스템 프롬프트에 주문 감지 지침을 포함하고, 주문 감지 시 `build_order_form_redirect()` 도구를 호출 |
| 대기 작업 (`pending_action`) | `chat_service` 내 수동 상태 관리 | 초기에는 기존 패턴 유지. Agent 실행 전/후에 pending_action 체크/설정 로직을 래핑 |
| 투자성향 프롬프트 | `load_user_investment_profile_context()` | 시스템 프롬프트 조립 시 그대로 호출 |
| RAG 벡터검색 | `rag_service.build_context()` | 시스템 프롬프트 조립 시 그대로 호출 |
| 자동메모리 | `memory_service.capture_from_exchange()` | Agent 실행 후 `_record_exchange()` 그대로 호출 |
| QA 이벤트 기록 | `qa_event_repository` | 기존 라우트 레벨 기록 로직 유지 |
| 사용량 제한 | `_consume_shared_usage` RPC | Agent 실행 전에 기존 RPC 호출 유지 |
| 안전 가드 | `safety_guard.py` | Agent의 시스템 프롬프트 + Tool 실행 전 `enforce_tool_safety()` 유지 |

### 7.2 단계적 전환 전략

주문 파서, pending_action 등 기존 상태 관리 기능은 **1차에서는 Agent 외부 래퍼로 유지**하고, 안정화 후 Agent 내부 도구로 점진적으로 통합한다.

```python
# chat_service.py — 1차 전환 후 reply() 구조
def reply(self, message, ...):
    # 1. 구조화 주문 처리 (기존 유지)
    if structured_order:
        return self._create_proposal_from_structured(...)
    
    # 2. 주문 폼 리다이렉트 (기존 유지)
    order_form_redirect = build_order_form_redirect(text)
    if order_form_redirect:
        return ...
    
    # 3. pending_action 처리 (기존 유지)
    if pending_action:
        return self._run_pending_action(...)
    
    # 4. LangGraph Agent 실행 (신규)
    return self._run_agent(text, user_id, auth_header, ...)
```

---

## 8. 파일 변경 상세

### 신규 파일

#### [NEW] `backend/services/chatbot/llm_provider.py`
- Gemini + GPT Failover LLM 인스턴스 생성
- 환경변수 기반 모델/프로바이더 설정
- `create_chatbot_llm()` 팩토리 함수 제공

#### [NEW] `backend/services/chatbot/agent.py`
- LangGraph StateGraph 정의
- `call_model`, `tools` 노드 구현
- `create_agent()` 팩토리 함수 제공
- `max_tool_rounds` 제한 로직

#### [NEW] `backend/services/chatbot/langchain_tools.py`
- 기존 `tool_registry.py` 함수를 LangGraph 도구로 래핑
- 도구 description은 기존 `function_calling.py` 스키마에서 가져옴
- `build_tool_list(auth_header)` 함수로 auth_header 주입된 도구 목록 반환

### 수정 파일

#### [MODIFY] `backend/services/chatbot/chat_service.py`
- `ChatbotService.__init__`에서 Agent 인스턴스 생성
- `reply()` 메서드의 LLM 직접 호출 부분을 `_run_agent()` 호출로 교체
- 주문 파서, pending_action, 구조화 주문 등 기존 전처리/후처리는 유지
- `_build_prompt_for_user()` 유지 (시스템 프롬프트 조립)

#### [MODIFY] `backend/routes/chatbot.py`
- `stream_chatbot_message()`의 스트리밍 생성기를 LangGraph `stream_events` 기반으로 교체
- SSE 이벤트 포맷(`trace`, `delta`, `done`, `error`)은 기존과 동일하게 유지하여 프론트엔드 호환성 보장

#### [MODIFY] `backend/requirements.txt`
- 추가: `langchain-core`, `langchain-google-genai`, `langchain-openai`, `langgraph`

### 유지 파일 (변경 없음)

- `tool_registry.py` — 비즈니스 로직 100% 유지, langchain_tools에서 참조
- `safety_guard.py` — Agent tools 노드에서 기존처럼 호출
- `order_parser.py` — chat_service 전처리에서 기존처럼 호출
- `order_form_policy.py` — chat_service 전처리에서 기존처럼 호출
- `conversation_repository.py` — 대화 이력 저장 유지
- `memory_service.py` — 자동메모리 캡처 유지
- `rag_service.py` — RAG 컨텍스트 빌드 유지
- `prompt_registry.py` — 시스템 프롬프트 빌드 유지
- `qa_event_repository.py` — QA 이벤트 기록 유지
- `user_context_lookup.py` — 사용자 컨텍스트 조회 유지

### 단계적 제거 대상

- `llm_client.py` — LangGraph 안정화 확인 후 제거. 전환 기간 중에는 폴백 경로로 유지
- `function_calling.py` — LangGraph Tool 전환 완료 후 제거. 전환 기간 중에는 레거시 참조용 유지

---

## 9. 검증 계획

### 자동 테스트

- `pytest` 기반 단위 테스트:
  - `llm_provider.py`: Failover 체인 생성, 환경변수 파싱, 모델 인스턴스 타입 검증
  - `agent.py`: 상태 그래프 구조 검증, max_tool_rounds 제한 테스트
  - `langchain_tools.py`: 도구 래핑 정합성, auth_header 주입 테스트

### 수동 검증

- 기존 QA 체크리스트(`chatbot_qa_checklist_2026-07-14.md`)의 A/B/C/D 항목 재검증
- 특히 기존 실패 항목 중심:
  - C09: 전 대화 인식 (max_history_messages 완화 효과 확인)
  - C16/C17: 관심종목/자동메모리 인식
  - C21: 공시+뉴스 복합 RAG 답변 (멀티 Tool 호출 효과 확인)
  - B20/B21/B22: 호가/체결/캔들 조회 (Gemini Function Calling 정확도)
- Gemini Failover 동작 확인: Primary 모델 API 키를 임시 무효화하여 Secondary/Fallback 자동 전환 검증
- SSE 스트리밍: 프론트엔드에서 토큰 단위 렌더링, trace 이벤트 표시 정상 동작 확인
- 비용 모니터링: Gemini/OpenAI 대시보드에서 전환 전후 토큰 사용량 비교

---

## 10. 리스크 및 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Gemini Function Calling 정확도가 GPT 대비 낮을 수 있음 | 도구 미호출 또는 잘못된 인자 | 시스템 프롬프트에 도구 사용 지침 강화, Failover로 GPT가 최종 보루 |
| LangGraph 의존성 추가로 배포 크기 증가 | Docker 이미지 크기 | langchain-core, langgraph은 경량 패키지 |
| 컨텍스트 확대로 비용 증가 | 토큰 비용 | 기존 일일 토큰 한도 유지, Gemini가 GPT 대비 저렴 |
| Flask 동기 환경에서 async LangGraph 호출 복잡도 | 코드 복잡도 | 기존 스레드+큐 패턴 유지, sync API 사용 |
| 전환 중 기존 기능 회귀 | 주문 파서, pending_action 등 | 단계적 전환, 기존 전처리 래퍼 유지 |
