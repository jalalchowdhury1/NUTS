"""The day's first compute (13:05 UTC) re-runs the price update; the others don't.
12 Nov 2026: Yahoo booked the 2 Nov bond dividends after the 21:00 UTC price run,
so BIL/BND/IEF/TLT stayed on the old basis overnight. Run: python test_morning_catchup.py"""
from datetime import datetime, timezone
from unittest import mock
import lambda_function as lf

calls = []
with mock.patch.object(lf, "handle_scheduled_update_prices", lambda: calls.append("prices") or {"status": "ok"}), \
     mock.patch.object(lf, "handle_evaluate", lambda force: calls.append("eval") or {"statusCode": 200}):
    for hh, mm, want in [(13, 5, ["prices", "eval"]), (13, 35, ["eval"]), (20, 35, ["eval"]), (21, 0, ["eval"])]:
        calls.clear()
        with mock.patch.object(lf, "datetime", mock.Mock(now=lambda tz: datetime(2026, 11, 12, hh, mm, tzinfo=tz))):
            lf.handle_scheduled_compute()
        assert calls == want, (hh, mm, calls)
        print(f"PASS {hh:02d}:{mm:02d} UTC compute -> {calls}")
