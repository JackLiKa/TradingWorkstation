"""測試 routes.py 的回測日期校驗邏輯。"""
from app.api.routes import _validate_backtest_dates


class TestValidateBacktestDates:
    """測試 _validate_backtest_dates 校驗函數。"""

    def test_valid_range_within_bounds(self):
        """日期在數據庫範圍內應該通過。"""
        config = {"startDate": "2024-01-01", "endDate": "2026-08-20"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is True
        assert msg == ""

    def test_start_after_end(self):
        """startDate 晚於 endDate 應該不通過。"""
        config = {"startDate": "2026-08-20", "endDate": "2024-01-01"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is False
        assert "不能晚於" in msg

    def test_start_too_early(self):
        """startDate 早於數據庫最早日期應該不通過。"""
        config = {"startDate": "2020-01-01", "endDate": "2026-08-20"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is False
        assert "早於數據庫最早交易日" in msg

    def test_end_too_late(self):
        """endDate 晚於數據庫最新日期應該不通過。"""
        config = {"startDate": "2024-01-01", "endDate": "2026-12-31"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is False
        assert "晚於數據庫最新交易日" in msg

    def test_missing_start_date(self):
        """缺少 startDate 應該不通過。"""
        config = {"endDate": "2026-08-20"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is False
        assert "startDate" in msg

    def test_missing_end_date(self):
        """缺少 endDate 應該不通過。"""
        config = {"startDate": "2024-01-01"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is False
        assert "endDate" in msg

    def test_no_bounds_check_when_db_unavailable(self):
        """數據庫不可用時（earliest/latest 為 None）只檢查 start <= end。"""
        config = {"startDate": "2024-01-01", "endDate": "2026-08-20"}
        ok, msg = _validate_backtest_dates(config, None, None)
        assert ok is True
        assert msg == ""

    def test_exact_boundary_dates(self):
        """日期恰好等於邊界值應該通過。"""
        config = {"startDate": "2021-01-04", "endDate": "2026-08-20"}
        ok, msg = _validate_backtest_dates(config, "2021-01-04", "2026-08-20")
        assert ok is True
        assert msg == ""
