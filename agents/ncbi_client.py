import os
from functools import lru_cache
from threading import Lock
from time import monotonic, sleep

import requests


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_request_lock = Lock()
_last_request = None


@lru_cache(maxsize=256)
def _fetch(endpoint, params, timeout, requests_per_second, cache_window):
    global _last_request
    with _request_lock:
        if _last_request is not None:
            delay = 1 / requests_per_second - (monotonic() - _last_request)
            if delay > 0:
                sleep(delay)
        _last_request = monotonic()

    try:
        response = requests.get(f"{EUTILS_BASE}/{endpoint}", params=dict(params), timeout=timeout)
    except requests.RequestException:
        raise RuntimeError(f"NCBI request failed for {endpoint}") from None
    if not response.ok:
        raise RuntimeError(f"NCBI returned HTTP {response.status_code} for {endpoint}")
    return response


def fetch_eutils(endpoint: str, params: dict, timeout: int = 15) -> requests.Response:
    """Throttle E-utilities requests and reuse successful responses within a 15-minute window."""
    request_params = {**params, "tool": "causalmed"}
    for env_name, parameter in (("NCBI_API_KEY", "api_key"), ("NCBI_EMAIL", "email")):
        value = os.getenv(env_name, "").strip()
        if value:
            request_params[parameter] = value

    return _fetch(
        endpoint,
        tuple(sorted(request_params.items())),
        timeout,
        10 if "api_key" in request_params else 3,
        int(monotonic() // 900),
    )
