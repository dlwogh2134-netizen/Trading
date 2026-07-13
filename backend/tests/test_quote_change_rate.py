from backend.routes import trade


def test_recalculate_change_rate_from_current_and_previous_close():
    assert trade._recalculate_change_rate(1909000, 1900000) == 0.4737


def test_extract_previous_close_from_quote_payload_direct_field():
    quote = {
        "current_price": 1909000,
        "previous_close": 1900000,
        "change_rate": -0.05,
    }

    current_price, previous_close, change_rate = trade._normalize_live_quote_prices(quote)

    assert current_price == 1909000
    assert previous_close == 1900000
    assert change_rate == 0.4737


def test_toss_price_source_keeps_api_change_rate_even_with_previous_close():
    quote = {
        "current_price": 1909000,
        "previous_close": 1900000,
        "change_rate": -12.08,
        "change_rate_source": "TOSS_PRICE",
    }

    current_price, previous_close, change_rate = trade._normalize_live_quote_prices(quote)

    assert current_price == 1909000
    assert previous_close == 1900000
    assert change_rate == -12.08


def test_extract_previous_close_from_kis_price_difference():
    quote = {
        "current_price": 1909000,
        "price_change": 9000,
        "change_rate": -0.05,
    }

    current_price, previous_close, change_rate = trade._normalize_live_quote_prices(quote)

    assert current_price == 1909000
    assert previous_close == 1900000
    assert change_rate == 0.4737


def test_extract_previous_close_from_kis_signed_down_price_difference():
    quote = {
        "current_price": 1891000,
        "price_change": 9000,
        "price_change_sign": "5",
        "change_rate": 0.05,
    }

    current_price, previous_close, change_rate = trade._normalize_live_quote_prices(quote)

    assert current_price == 1891000
    assert previous_close == 1900000
    assert change_rate == -0.4737
