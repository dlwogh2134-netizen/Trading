from backend.services.home_service import filter_latest_snapshot_rows


def test_filter_latest_snapshot_rows_keeps_same_kst_trading_day_rows():
    rows = [
        {
            "symbol": "005930",
            "as_of": "2026-07-13T06:31:25+00:00",
            "trading_value": 8_446_959_119_500,
        },
        {
            "symbol": "000660",
            "as_of": "2026-07-13T05:17:34+00:00",
            "trading_value": 11_046_696_209_500,
        },
        {
            "symbol": "395270",
            "as_of": "2026-07-03T08:33:47+00:00",
            "trading_value": 946_838_230_538,
        },
    ]

    filtered_rows = filter_latest_snapshot_rows(rows)

    assert [row["symbol"] for row in filtered_rows] == ["005930", "000660"]
