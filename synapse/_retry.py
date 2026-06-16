import time


def retry(func, *args, max_retries=3, backoff=1.0, should_retry=None, on_retry=None, **kwargs):
    if should_retry is None:
        should_retry = lambda e: isinstance(e, OSError)

    attempt = 0
    while True:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if not should_retry(e):
                raise
            attempt += 1
            if attempt > max_retries:
                raise
            if on_retry is not None:
                on_retry(e, attempt)
            time.sleep(backoff * attempt)
