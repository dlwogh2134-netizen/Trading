from unittest.mock import MagicMock

from backend.services.ai_fund_reconciliation import AiFundReconciliationService


def test_reconcile_marks_missing_exchange_order_as_needs_review(monkeypatch):
    writes = []
    monkeypatch.setattr(
        "backend.services.ai_fund_reconciliation.safe_query_supabase_as_service_role",
        lambda endpoint, method="GET", json_data=None, params=None: (
            [{
                "id": "ledger-order-1",
                "exchange_order_id": "exchange-order-1",
                "client_order_id": "client-order-1",
                "symbol": "BTC",
                "side": "BUY",
                "order_type": "LIMIT",
                "requested_qty": 1.0,
                "requested_price": 100.0,
            }] if method == "GET" else writes.append((endpoint, json_data)) or []
        ),
    )
    ledger = MagicMock()
    client = MagicMock()
    client.get_order_status.return_value = None

    result = AiFundReconciliationService(ledger).reconcile_config(
        {"id": "config-1", "user_id": "user-1", "exchange_type": "coinone"},
        client,
    )

    assert result.needs_review_count == 1
    assert any(write[1].get("status") == "NEEDS_REVIEW" for write in writes)
    ledger.apply_new_fill.assert_not_called()


def test_reconcile_applies_only_new_partial_fill(monkeypatch):
    updates = []
    monkeypatch.setattr(
        "backend.services.ai_fund_reconciliation.safe_query_supabase_as_service_role",
        lambda endpoint, method="GET", json_data=None, params=None: (
            [{
                "id": "ledger-order-1",
                "exchange_order_id": "exchange-order-1",
                "client_order_id": "client-order-1",
                "symbol": "BTC",
                "side": "BUY",
                "order_type": "LIMIT",
                "requested_qty": 1.0,
                "requested_price": 100.0,
            }] if method == "GET" else updates.append(json_data) or []
        ),
    )
    ledger = MagicMock()
    client = MagicMock()
    client.get_order_status.return_value = {
        "order_id": "exchange-order-1",
        "status": "PARTIALLY_FILLED",
        "executed_qty": 0.4,
        "price": 100.0,
    }

    result = AiFundReconciliationService(ledger).reconcile_config(
        {"id": "config-1", "user_id": "user-1", "exchange_type": "coinone"},
        client,
    )

    assert result.updated_count == 1
    assert updates[-1]["status"] == "PARTIALLY_FILLED"
    ledger.apply_new_fill.assert_called_once()
