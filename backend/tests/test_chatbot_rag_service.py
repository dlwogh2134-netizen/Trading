from backend.services.chatbot import rag_service as rag_module
from backend.services.chatbot.rag_service import ChatbotRAGService


class FakeEmbeddingResponse:
    status_code = 200

    @staticmethod
    def json():
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}


def test_chatbot_rag_service_retrieves_disclosure_and_obsidian_chunks(monkeypatch):
    embedding_calls = []
    supabase_calls = []
    matched_rows = [
        {
            "source_type": "DISCLOSURE",
            "source_id": "20260710000001",
            "chunk_text": "삼성전자 공급계약 공시 요약",
            "similarity": 0.94,
        },
        {
            "source_type": "OBSIDIAN",
            "source_id": "note-1",
            "chunk_text": "사용자 투자 노트의 확인 항목",
            "similarity": 0.88,
        },
    ]

    def fake_post(url, **kwargs):
        embedding_calls.append((url, kwargs))
        return FakeEmbeddingResponse()

    def fake_query(auth_header, path, method, **kwargs):
        supabase_calls.append((auth_header, path, method, kwargs))
        return matched_rows

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("CHATBOT_RAG_TOP_K", "5")
    monkeypatch.setenv("CHATBOT_RAG_MAX_CONTEXT_CHARS", "6000")
    monkeypatch.setenv("CHATBOT_OPENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setattr(rag_module.requests, "post", fake_post)
    monkeypatch.setattr(rag_module, "safe_query_supabase", fake_query)

    service = ChatbotRAGService()
    context, evidence = service.build_context(
        "Bearer test-token",
        "user-1",
        "삼성전자 공시와 내 투자 노트를 함께 찾아줘",
    )

    assert embedding_calls[0][1]["json"] == {
        "model": "text-embedding-3-small",
        "input": "삼성전자 공시와 내 투자 노트를 함께 찾아줘",
    }
    assert supabase_calls == [
        (
            "Bearer test-token",
            "rpc/match_knowledge_chunks",
            "POST",
            {
                "json_data": {
                    "query_embedding": [0.1, 0.2, 0.3],
                    "match_user_id": "user-1",
                    "match_count": 5,
                }
            },
        )
    ]
    assert "source_type=DISCLOSURE" in context
    assert "source_type=OBSIDIAN" in context
    assert "삼성전자 공급계약 공시 요약" in context
    assert "사용자 투자 노트의 확인 항목" in context
    assert evidence == matched_rows


def test_chatbot_rag_service_fails_closed_when_embedding_request_fails(monkeypatch):
    def fail_post(*args, **kwargs):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(rag_module.requests, "post", fail_post)

    context, evidence = ChatbotRAGService().build_context(
        "Bearer test-token",
        "user-1",
        "공시를 찾아줘",
    )

    assert context == ""
    assert evidence == []
