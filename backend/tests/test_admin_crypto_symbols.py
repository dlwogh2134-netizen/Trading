from flask import Flask

from backend.routes import admin_symbols


AUTH = {"Authorization": "Bearer admin-token"}


def test_list_admin_crypto_symbols_requires_admin(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(admin_symbols.admin_symbols_bp)
    monkeypatch.setattr(
        admin_symbols,
        "_verify_admin",
        lambda auth_header: (_ for _ in ()).throw(PermissionError("관리자 권한이 필요합니다.")),
    )

    response = app.test_client().get("/api/admin/crypto-symbols", headers=AUTH)

    assert response.status_code == 403
    assert response.get_json()["success"] is False


def test_list_admin_crypto_symbols_returns_items(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(admin_symbols.admin_symbols_bp)
    monkeypatch.setattr(admin_symbols, "_verify_admin", lambda auth_header: {"id": "admin-1"})
    monkeypatch.setattr(
        admin_symbols,
        "list_crypto_assets",
        lambda query="", exchange="ALL", tradable="ALL", blocked="ALL", limit=200: [{
            "base_symbol": "H",
            "display_name_en": "Humanity",
            "default_exchange": "COINONE",
        }],
    )

    response = app.test_client().get("/api/admin/crypto-symbols?query=H", headers=AUTH)

    assert response.status_code == 200
    assert response.get_json()["data"]["items"][0]["base_symbol"] == "H"


def test_update_admin_crypto_symbol_parses_aliases(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(admin_symbols.admin_symbols_bp)
    captured = {}
    monkeypatch.setattr(admin_symbols, "_verify_admin", lambda auth_header: {"id": "admin-1"})

    def fake_patch(base_symbol, patch):
        captured["base_symbol"] = base_symbol
        captured["patch"] = patch
        return {"base_symbol": base_symbol, "aliases": list(patch.aliases)}

    monkeypatch.setattr(admin_symbols, "patch_crypto_asset", fake_patch)

    response = app.test_client().patch(
        "/api/admin/crypto-symbols/H",
        headers=AUTH,
        json={"aliases": "Humanity, 휴머니티", "default_exchange": "COINONE"},
    )

    assert response.status_code == 200
    assert captured["base_symbol"] == "H"
    assert captured["patch"].aliases == ("Humanity", "휴머니티")
