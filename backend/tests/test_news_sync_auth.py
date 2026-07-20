from __future__ import annotations

from typing import Any

import pytest
from flask import Flask

from backend.routes.news import news_bp


class FakeSyncService:
    def __init__(self) -> None:
        self.called = False

    def run_once(self) -> dict[str, Any]:
        self.called = True
        return {"inserted": 1}

    def run_for_symbol(
        self,
        symbol: str,
        display_name: str = "",
        market: str = "",
        asset_type: str = "",
    ) -> dict[str, Any]:
        self.called = True
        return {
            "symbol": symbol,
            "display_name": display_name,
            "market": market,
            "asset_type": asset_type,
        }


@pytest.fixture
def news_sync_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    monkeypatch.setenv("NEWS_SYNC_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(
        "backend.routes.news.validate_access_token",
        lambda auth_header: ("user-1", auth_header.removeprefix("Bearer ")),
        raising=False,
    )
    app = Flask(__name__)
    app.news_ingest_service = FakeSyncService()
    app.register_blueprint(news_bp)
    return app


def test_news_sync_accepts_anonymous_symbol_request(news_sync_app: Flask) -> None:
    # Given: 비로그인 사용자가 특정 종목의 최신 뉴스를 요청합니다.
    service = news_sync_app.news_ingest_service

    # When: 인증 헤더 없이 종목별 뉴스 수집을 요청합니다.
    response = news_sync_app.test_client().post(
        "/api/news/sync",
        json={
            "symbol": "005930",
            "display_name": "삼성전자",
            "market": "DOMESTIC",
            "asset_type": "STOCK",
        },
    )

    # Then: 전체 수집이 아니라 해당 종목 온디맨드 수집만 실행합니다.
    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "symbol": "005930",
        "display_name": "삼성전자",
        "market": "DOMESTIC",
        "asset_type": "STOCK",
    }
    assert service.called is True


def test_news_sync_rejects_anonymous_request_without_symbol(news_sync_app: Flask) -> None:
    # Given: 뉴스 동기화 서비스가 앱에 연결되어 있습니다.
    service = news_sync_app.news_ingest_service

    # When: 인증 없이 종목을 비운 뉴스 수집을 요청합니다.
    response = news_sync_app.test_client().post("/api/news/sync", json={})

    # Then: 익명 요청은 종목별 수집으로 제한되어 전체 수집 비용을 만들지 않습니다.
    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert service.called is False


def test_news_sync_accepts_logged_in_user_for_symbol_request(news_sync_app: Flask) -> None:
    # Given: 로그인 사용자가 특정 종목의 최신 뉴스를 요청합니다.
    service = news_sync_app.news_ingest_service

    # When: 사용자 JWT와 종목을 함께 전달해 뉴스 수집을 요청합니다.
    response = news_sync_app.test_client().post(
        "/api/news/sync",
        headers={"Authorization": "Bearer user-token"},
        json={
            "symbol": "005930",
            "display_name": "삼성전자",
            "market": "DOMESTIC",
            "asset_type": "STOCK",
        },
    )

    # Then: 로그인 사용자도 동일한 종목별 온디맨드 수집 경로를 사용합니다.
    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "symbol": "005930",
        "display_name": "삼성전자",
        "market": "DOMESTIC",
        "asset_type": "STOCK",
    }
    assert service.called is True


def test_news_sync_rejects_logged_in_user_without_symbol(news_sync_app: Flask) -> None:
    # Given: 로그인 사용자가 전체 뉴스 수집을 요청합니다.
    service = news_sync_app.news_ingest_service

    # When: 사용자 JWT만 전달하고 종목을 비워둡니다.
    response = news_sync_app.test_client().post(
        "/api/news/sync",
        headers={"Authorization": "Bearer user-token"},
        json={},
    )

    # Then: 사용자 요청은 종목별 수집으로 제한되어 전체 수집 비용을 만들지 않습니다.
    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert service.called is False


def test_news_sync_accepts_configured_admin_token(news_sync_app: Flask) -> None:
    # Given: 관리자가 올바른 뉴스 동기화 토큰을 가지고 있습니다.
    service = news_sync_app.news_ingest_service

    # When: 관리자 토큰으로 뉴스 동기화를 요청합니다.
    response = news_sync_app.test_client().post(
        "/api/news/sync",
        headers={"X-Admin-Token": "admin-secret"},
        json={},
    )

    # Then: 관리자는 예약 수집과 같은 전체 동기화 서비스를 실행할 수 있습니다.
    assert response.status_code == 200
    assert response.get_json()["data"] == {"inserted": 1}
    assert service.called is True
