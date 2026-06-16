import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse._retry import retry


class RetryTests(unittest.TestCase):
    def test_returns_result_on_first_success(self):
        calls = []

        def func():
            calls.append(1)
            return "ok"

        result = retry(func, max_retries=3, backoff=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 1)

    def test_retries_until_success(self):
        attempts = []

        def func():
            attempts.append(1)
            if len(attempts) < 3:
                raise OSError("transient")
            return "ok"

        result = retry(func, max_retries=5, backoff=0)
        self.assertEqual(result, "ok")
        self.assertEqual(len(attempts), 3)

    def test_raises_after_exhausting_retries(self):
        attempts = []

        def func():
            attempts.append(1)
            raise OSError("always fails")

        max_retries = 2
        with self.assertRaises(OSError):
            retry(func, max_retries=max_retries, backoff=0)

        self.assertEqual(len(attempts), max_retries + 1)

    def test_should_retry_false_stops_immediately(self):
        attempts = []

        def func():
            attempts.append(1)
            raise ValueError("not retryable")

        with self.assertRaises(ValueError):
            retry(func, max_retries=5, backoff=0, should_retry=lambda e: False)

        self.assertEqual(len(attempts), 1)

    def test_default_should_retry_only_catches_oserror(self):
        def func():
            raise TypeError("bug, not a transient failure")

        with self.assertRaises(TypeError):
            retry(func, max_retries=3, backoff=0)

    def test_on_retry_called_per_attempt_not_on_final_failure(self):
        calls = []
        max_retries = 2

        def func():
            raise OSError("fail")

        with self.assertRaises(OSError):
            retry(func, max_retries=max_retries, backoff=0, on_retry=lambda e, attempt: calls.append(attempt))

        self.assertEqual(calls, list(range(1, max_retries + 1)))

    def test_on_retry_not_called_when_should_retry_is_false(self):
        calls = []

        def func():
            raise ValueError("not retryable")

        with self.assertRaises(ValueError):
            retry(
                func,
                max_retries=3,
                backoff=0,
                should_retry=lambda e: False,
                on_retry=lambda e, attempt: calls.append(attempt),
            )

        self.assertEqual(calls, [])

    def test_forwards_args_and_kwargs(self):
        def func(a, b, c=None):
            return (a, b, c)

        result = retry(func, 1, 2, c=3, max_retries=0, backoff=0)
        self.assertEqual(result, (1, 2, 3))

    def test_backoff_scales_with_attempt(self):
        sleeps = []
        real_sleep = time.sleep
        time.sleep = lambda s: sleeps.append(s)
        try:
            def func():
                raise OSError("fail")

            with self.assertRaises(OSError):
                retry(func, max_retries=3, backoff=1)
        finally:
            time.sleep = real_sleep

        self.assertEqual(sleeps, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
