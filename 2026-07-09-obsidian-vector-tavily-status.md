# Obsidian · Vector DB · LLM Memory · Tavily 작업 현황

확인일: 2026-07-09  
확인 기준: 현재 로컬 코드, 마이그레이션 파일, Supabase REST 조회 결과

## 1. 요약

현재 구현은 `Obsidian 노트 동기화 -> user_knowledge_notes 저장`까지 실제 DB에서 확인되었습니다.  
`knowledge_chunks` 테이블에는 데이터가 존재하지만, 현재 확인된 데이터는 Obsidian 노트 chunk가 아니라 공시(`DISCLOSURE`) 기반 chunk입니다.

따라서 현재 상태를 정확히 나누면 다음과 같습니다.

| 영역 | 현재 상태 | 판단 |
| --- | --- | --- |
| Obsidian 플러그인 | 내부 시연용 플러그인 존재 | 1차 구현 완료 |
| Obsidian 노트 DB 저장 | `user_knowledge_notes`에 1건 저장 확인 | 동작 확인 |
| Obsidian chunk 생성 | DB 기준 `source_type=OBSIDIAN` 0건 | 추가 확인/재동기화 필요 |
| Vector DB 테이블 | `knowledge_chunks` 2,298건 존재 | 테이블 및 일부 임베딩 데이터 존재 |
| Embedding | 최근 조회 샘플 기준 `DISCLOSURE:EMBEDDED` 존재 | 공시 쪽 임베딩은 진행된 흔적 있음 |
| 자동메모리 | `user_memory_facts` 0건 | 생성 로직/샘플 데이터 필요 |
| Tavily | 코드 기준 미연동 | 후속 작업 |
| 챗봇 RAG 연결 | 현재 챗봇은 `knowledge_chunks` 검색을 사용하지 않음 | 후속 작업 |

## 2. 코드 기준 완료된 작업

### 2.1 Obsidian 플러그인

위치:

- `obsidian-plugin/ai-trading-memory/`

확인된 주요 파일:

- `obsidian-plugin/ai-trading-memory/main.js`
- `obsidian-plugin/ai-trading-memory/manifest.json`
- `obsidian-plugin/ai-trading-memory/src/templates.js`
- `obsidian-plugin/ai-trading-memory/src/marker.js`
- `obsidian-plugin/ai-trading-memory/src/markdown.js`
- `obsidian-plugin/ai-trading-memory/src/syncClient.js`

제공 기능:

- 기본 투자노트 템플릿 생성
- 현재 노트 앱으로 동기화
- AI-Trading 폴더 전체 동기화
- 자동메모리 가져오기

플러그인이 호출하는 백엔드 API:

- `POST /api/knowledge/obsidian/sync-note`
- `GET /api/knowledge/obsidian/auto-memory`

### 2.2 Flask Knowledge API

위치:

- `backend/routes/knowledge.py`

구현된 API:

- `POST /api/knowledge/obsidian/sync-note`
- `GET /api/knowledge/obsidian/auto-memory`

`sync-note` 동작:

1. Authorization Bearer 토큰으로 사용자 확인
2. `vault_name`, `file_path`, `content`, `modified_at` 수신
3. Markdown frontmatter/title/content hash 파싱
4. `user_knowledge_notes`에 upsert
5. `knowledge_chunk_service.build_chunks()`로 chunk 생성
6. `knowledge_chunks`에서 기존 source chunk 삭제 후 새 chunk 저장

관련 서비스:

- `backend/services/obsidian_service.py`
- `backend/services/knowledge_repository.py`
- `backend/services/knowledge_chunk_service.py`

### 2.3 테스트

확인 명령:

```bash
python3 -m pytest tests/backend/test_obsidian_service.py tests/backend/test_knowledge_repository.py tests/backend/test_knowledge_chunk_service.py tests/backend/test_knowledge_routes.py -q
```

결과:

```text
12 passed in 0.21s
```

## 3. DB 기준 확인 결과

Supabase REST API를 service role로 조회했습니다. 문서에는 노트 본문, 토큰, API Key 등 민감 정보는 기록하지 않습니다.

### 3.1 user_knowledge_notes

조회 결과:

- 총 1건
- 저장된 vault: `AI-Trading-Vault`
- 저장된 파일: `AI-Trading/00_나의_투자원칙.md`
- title: `나의 투자 원칙`
- source: `obsidian`
- sync_status: `SYNCED`
- modified_at: `2026-07-08T08:17:23.061+00:00`
- created_at: `2026-07-08T08:23:59.71427+00:00`

판단:

- Obsidian 플러그인에서 Supabase DB까지 노트 원문 저장은 실제로 성공했습니다.
- 시간은 UTC 기준으로 저장되어 보이며, 한국시간으로 보면 +9시간 차이가 납니다.

### 3.2 knowledge_chunks

조회 결과:

- 전체 row 수: 2,298건
- 최근 조회 샘플 1,000건 기준:
  - `source_type=DISCLOSURE`: 1,000건
  - `embedding_status=EMBEDDED`: 1,000건
- `source_type=OBSIDIAN`: 0건
- `source_id=저장된 Obsidian note id`: 0건
- `embedding_status=PENDING`: 0건
- `source_type=NEWS`: 0건

판단:

- `knowledge_chunks` 테이블은 비어 있지 않습니다.
- 다만 현재 확인된 chunk는 공시(`DISCLOSURE`) 기반입니다.
- Obsidian 노트는 `user_knowledge_notes`에 저장되어 있으나, 해당 노트의 chunk는 현재 DB에 없습니다.
- 원인 후보:
  - 노트 동기화가 `knowledge_chunks` migration 적용 전에 먼저 실행되었을 가능성
  - 이후 공시 임베딩 작업이 진행됐지만 Obsidian 노트 재동기화는 하지 않았을 가능성
  - `replace_knowledge_chunks()` 호출 당시 DB 저장 실패가 있었지만 플러그인에서 chunk 결과를 따로 확인하지 않았을 가능성

다음 확인:

- Obsidian에서 같은 노트를 다시 `현재 노트 앱으로 동기화`
- 이후 DB에서 `source_type=OBSIDIAN` row 생성 여부 확인

### 3.3 user_memory_facts

조회 결과:

- 총 0건

판단:

- 자동메모리 조회 API는 구현되어 있지만, 가져올 데이터가 아직 없습니다.
- 자동메모리 기능을 시연하려면 최소 샘플 fact를 넣거나, 챗봇/행동 로그에서 fact를 생성하는 서비스가 필요합니다.

### 3.4 news_articles

조회 결과:

- 전체 row 수: 25,011건
- 최근 조회 샘플 1,000건 기준:
  - `NAVER`: 976건
  - `FINNHUB`: 24건
- 최근 샘플 기준 `TAVILY` 없음

판단:

- 뉴스 DB는 이미 대량 수집되어 있습니다.
- 현재 코드와 DB 기준 뉴스 provider는 `NAVER`, `FINNHUB`가 실제 사용 중입니다.
- Tavily는 아직 DB provider로 들어오지 않았습니다.

## 4. 문서와 실제 코드의 차이

`docs/superpowers/plans/2026-07-08-obsidian-vector-llm-memory.md`는 완성형 계획서입니다. 실제 코드와 다른 점이 있습니다.

계획서에는 다음이 포함되어 있습니다.

- `EmbeddingService`
- `RagRetrievalService`
- `ChatRagService`
- `match_knowledge_chunks` RPC
- `obsidian_vaults`
- `obsidian_documents`
- `/api/knowledge/chat`
- `/api/knowledge/memory`
- 프론트엔드 지식 설정 화면

현재 실제 코드에는 다음만 있습니다.

- `user_knowledge_notes`
- `user_memory_facts`
- `knowledge_chunks`
- Obsidian sync API
- Obsidian auto-memory 조회 API
- chunk 분할 서비스

따라서 현재 기준 공식 상태는 계획서보다 `README.md`, `agents.md`, `database_specification.md`, `project_structure.md`에 반영된 내용이 더 정확합니다.

## 5. 현재 구조에서 embedding의 의미

`knowledge_chunks.chunk_text`는 사람이 읽는 문장입니다.  
`knowledge_chunks.embedding`은 그 문장의 의미를 숫자 벡터로 변환한 값입니다.

예시:

```text
chunk_text:
"삼성전자는 분할매수로 접근하고 손절 기준은 -3%로 둔다."

embedding:
[0.012, -0.443, 0.087, ...]
```

이 값이 있어야 챗봇이 단순 키워드 검색이 아니라 의미 기반 검색을 할 수 있습니다.

현재 DB 기준:

- 공시 chunk는 `EMBEDDED` 상태가 존재합니다.
- Obsidian chunk는 아직 DB에서 확인되지 않았습니다.

## 6. 다음 작업 방향

### 6.1 1순위: Obsidian chunk 재확인

목표:

- `user_knowledge_notes`에 저장된 Obsidian 노트가 `knowledge_chunks`에도 `source_type=OBSIDIAN`으로 생성되는지 확인

작업:

1. Obsidian에서 `AI Trading: 현재 노트 앱으로 동기화` 재실행
2. DB에서 아래 조건 확인
   - `knowledge_chunks.source_type = 'OBSIDIAN'`
   - `knowledge_chunks.source_id = user_knowledge_notes.id`
   - `embedding_status = 'PENDING'` 또는 `EMBEDDED`
3. 생성되지 않으면 Flask 로그에서 `replace_knowledge_chunks()` 실패 여부 확인

완료 기준:

- Obsidian 노트 1건당 chunk 1건 이상 생성
- `chunk_text`가 비어 있지 않음
- `source_id`가 노트 id와 연결됨

### 6.2 2순위: Obsidian chunk embedding 처리

목표:

- Obsidian chunk도 vector 검색 대상으로 만들기

작업:

1. `backend/services/embedding_service.py` 추가
2. `embedding_status=PENDING` chunk 조회
3. `chunk_text`를 embedding 모델로 변환
4. `knowledge_chunks.embedding` 업데이트
5. 성공 시 `embedding_status=EMBEDDED`
6. 실패 시 `embedding_status=FAILED`

주의:

- 모델 차원은 현재 migration의 `VECTOR(1536)`과 맞아야 합니다.
- 예: `text-embedding-3-small`은 1536차원으로 설계와 맞습니다.

완료 기준:

- Obsidian chunk가 `EMBEDDED` 상태가 됨
- embedding 컬럼이 null이 아님

### 6.3 3순위: Vector 검색 RPC 추가

목표:

- 챗봇 질문과 의미가 가까운 chunk를 찾기

작업:

1. `match_knowledge_chunks` RPC 추가
2. source 필터 지원
   - `OBSIDIAN`
   - `AUTO_MEMORY`
   - `NEWS`
   - `DISCLOSURE`
3. 사용자 private 데이터 격리
   - 개인 데이터: `user_id = auth.uid()`
   - 공용 데이터: `user_id IS NULL`
4. similarity score 반환

완료 기준:

- 질문 embedding으로 관련 chunk 검색 가능
- 다른 사용자의 Obsidian 노트가 검색되지 않음

### 6.4 4순위: 자동메모리 생성

목표:

- 사용자의 반복 패턴을 `user_memory_facts`에 저장

저장 후보:

- 자주 묻는 관심 종목
- 반복 매매 실수
- 선호 답변 방식
- 리스크 성향
- 투자 원칙

작업:

1. `user_memory_service.py` 추가
2. 챗봇 대화 또는 행동 로그에서 memory fact 후보 추출
3. confidence/evidence_count 기반으로 누적
4. Obsidian auto-memory marker로 내보내기

완료 기준:

- `user_memory_facts`에 active fact가 생김
- `GET /api/knowledge/obsidian/auto-memory`가 빈 배열이 아닌 값을 반환
- Obsidian marker 영역에 자동 반영됨

### 6.5 5순위: Tavily 추가

현재 상태:

- 코드 기준 뉴스 provider는 `NAVER`, `FINNHUB`
- DB 기준 최근 샘플도 `NAVER`, `FINNHUB`
- Tavily provider는 아직 없음

추천 설계:

- Tavily를 별도 개인 메모리로 저장하지 않습니다.
- 기존 `news_articles`에 `source='TAVILY'` provider로 저장하는 방식이 좋습니다.
- 이후 `knowledge_chunks.source_type='NEWS'`로 chunk 생성합니다.

이유:

- Tavily는 최신 웹/뉴스 검색 provider입니다.
- Obsidian/자동메모리는 사용자 개인 지식입니다.
- 두 개를 섞으면 출처 우선순위와 삭제 권한이 복잡해집니다.

작업:

1. 환경변수 추가
   - `TAVILY_API_KEY`
   - `NEWS_TAVILY_DAILY_QUERY_BUDGET`
   - `NEWS_TAVILY_MAX_ITEMS_PER_QUERY`
2. `NewsQueryPlanner`에 Tavily query 후보 추가
3. `NewsIngestService`에 `_fetch_tavily()` 추가
4. 결과를 `news_articles` 포맷으로 정규화
5. fetch log에 `source='TAVILY'` 기록
6. Tavily 결과를 chunk로 변환하는 후속 작업 연결

완료 기준:

- `news_articles.source='TAVILY'` row 생성
- Tavily 호출량 제한 적용
- 중복 URL deduplication 동작
- Tavily 기사도 `knowledge_chunks.source_type='NEWS'`로 검색 가능

### 6.6 6순위: 챗봇 RAG 연결

현재 챗봇:

- `backend/services/chatbot/chat_service.py` 기준으로 도구 호출과 LLM 응답을 사용
- `knowledge_chunks` vector 검색은 아직 사용하지 않음

목표:

- 챗봇 답변 전에 관련 context를 검색해서 LLM에 전달

추천 우선순위:

1. Obsidian 개인 노트
2. 자동메모리
3. 공시
4. 저장된 뉴스
5. 필요한 경우 Tavily 최신 검색

완료 기준:

- 챗봇 응답 payload에 citations 포함
- 어떤 근거를 사용했는지 source 표시
- 매매 실행은 계속 차단하고, 제안은 사용자 승인 흐름으로만 연결

## 7. 보안 및 설계 주의사항

### 7.1 knowledge_chunks RLS 보강 필요

현재 migration에는 `knowledge_chunks`의 공용 데이터(`user_id IS NULL`)에 대해 authenticated 사용자의 insert/update/delete가 열려 있습니다.

문서 `agents.md`에는 다음 원칙이 있습니다.

- 공용 지식 데이터는 일반 authenticated 사용자가 Insert/Update/Delete 할 수 없어야 함

따라서 Tavily/뉴스/공시 공용 chunk를 본격 운영하기 전에 RLS 보강 migration이 필요합니다.

권장 방향:

- 개인 Obsidian/App note chunk:
  - 소유자만 insert/update/delete
- 공용 NEWS/DISCLOSURE chunk:
  - 일반 사용자는 select만 가능
  - insert/update/delete는 service role 또는 백엔드 전용 경로만 허용

### 7.2 Tavily 비용 방어

Tavily는 외부 유료 API 한도가 있으므로 다음 방어가 필요합니다.

- 인증 없는 `/api/news/sync` 호출 차단
- 관리자 토큰 또는 내부 worker만 호출
- query log 기반 일일 호출량 제한
- 동일 query 반복 호출 캐싱
- DB에 최신 결과가 있으면 Tavily 재호출 생략

### 7.3 민감 데이터 처리

문서화/로그에 남기면 안 되는 정보:

- Supabase service role key
- Supabase JWT access token
- refresh token
- Obsidian 원문 노트 내용
- 사용자 API Key

## 8. 내일 작업 체크리스트

### Obsidian 담당

- Obsidian 노트 재동기화
- `knowledge_chunks.source_type=OBSIDIAN` 생성 확인
- 자동메모리 marker 동작 확인
- 템플릿 추가 여부 결정

### Vector DB 담당

- Obsidian chunk 생성 여부 확인
- embedding worker/service 구현
- `PENDING -> EMBEDDED` 업데이트 구현
- `match_knowledge_chunks` RPC 구현
- RLS 보강 migration 작성

### Tavily/뉴스 담당

- Tavily provider 추가 여부 확정
- `NewsIngestService`에 Tavily fetcher 추가
- `news_articles.source='TAVILY'` 저장
- 호출량 제한 및 fetch log 연결

### 챗봇 담당

- RAG retrieval service 추가
- 챗봇 응답 전에 vector 검색 연결
- citations 포함
- 매매 실행 차단 원칙 유지

## 9. 결론

현재까지는 Obsidian 1차 동기화와 지식 테이블 기반은 만들어졌습니다.  
다만 실제 DB 기준으로는 Obsidian 노트가 `user_knowledge_notes`에는 저장되어 있지만 `knowledge_chunks`에는 아직 연결되어 있지 않습니다.

다음 작업의 출발점은 Tavily가 아니라 Obsidian chunk 재동기화 확인입니다.  
그 다음 순서로 embedding 처리, vector 검색 RPC, 챗봇 RAG 연결, Tavily provider 추가를 진행하는 것이 가장 안전합니다.
