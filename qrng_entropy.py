"""
Sentinel QRNG Entropy Source — quantum random numbers (ANU QRNG) for key
generation, with a local pool and a cryptographically-secure fallback.

The ANU QRNG public API is rate-limited to ~1 request/minute per IP, which
makes live per-key fetches unworkable at demo time. So: prime a pool once
at startup with a single batched request, serve from that pool, and fall
back to `secrets.token_bytes()` — transparently and loudly — whenever the
pool runs dry or the network misbehaves.
"""

import json
import secrets
import threading
import time
import urllib.request
from collections import deque

QRNG_URL = "https://qrng.anu.edu.au/API/jsonI.php"
QRNG_MAX_LENGTH = 1024          # ANU QRNG per-request cap for type=uint8
QRNG_MIN_INTERVAL_SECONDS = 60  # API enforces ~1 request/minute per IP
REQUEST_TIMEOUT_SECONDS = 5

POOL_TARGET_SIZE = 1024         # bytes fetched per successful refill (API max)
POOL_REFILL_THRESHOLD = 64      # trigger a background refill below this


def _fetch_from_anu(n):
    """One blocking HTTP call to the ANU QRNG API. Raises on any failure."""
    n = max(1, min(n, QRNG_MAX_LENGTH))
    url = f"{QRNG_URL}?length={n}&type=uint8"
    req = urllib.request.Request(url, headers={"User-Agent": "sentinel-hackathon/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read())
    if not body.get("success"):
        raise RuntimeError(f"ANU QRNG API responded success=false: {body}")
    return bytes(body["data"])


class QuantumEntropyPool:
    """A local queue of quantum random bytes, backfilled from ANU QRNG.

    get_bytes() never blocks on the network: it serves from the pool, and
    tops up with secrets.token_bytes() (CSPRNG, not quantum) if the pool is
    short. A background thread refills the pool opportunistically, respecting
    the API's 1-request/minute limit.
    """

    def __init__(self, target_size=POOL_TARGET_SIZE, refill_threshold=POOL_REFILL_THRESHOLD):
        self._pool = deque()
        self._lock = threading.Lock()
        self._target_size = target_size
        self._refill_threshold = refill_threshold
        self._last_request_time = 0.0
        self._refill_in_progress = False
        self.quantum_bytes_served = 0
        self.fallback_bytes_served = 0

    def _refill_allowed(self):
        if self._refill_in_progress:
            return False
        if self._last_request_time == 0.0:
            return True
        return (time.time() - self._last_request_time) >= QRNG_MIN_INTERVAL_SECONDS

    def _do_refill(self):
        self._refill_in_progress = True
        self._last_request_time = time.time()
        try:
            chunk = _fetch_from_anu(self._target_size)
            with self._lock:
                self._pool.extend(chunk)
            print(f"[qrng] refilled pool with {len(chunk)} bytes of real ANU QRNG quantum entropy")
        except Exception as e:
            print(f"[qrng] WARNING: ANU QRNG refill failed ({e}); "
                  f"further requests will use secrets.token_bytes() fallback until it recovers")
        finally:
            self._refill_in_progress = False

    def _try_refill(self, blocking):
        if not self._refill_allowed():
            return
        if blocking:
            self._do_refill()
        else:
            threading.Thread(target=self._do_refill, daemon=True).start()

    def prime(self):
        """Blocking initial fetch — call once at startup to front-load the pool."""
        print("[qrng] priming entropy pool with one ANU QRNG request "
              f"(target {self._target_size} bytes)...")
        self._try_refill(blocking=True)
        print(f"[qrng] pool primed: {len(self._pool)} bytes available")

    def get_bytes(self, n):
        with self._lock:
            take = min(n, len(self._pool))
            out = bytes(self._pool.popleft() for _ in range(take))
            remaining = len(self._pool)

        if remaining < self._refill_threshold:
            self._try_refill(blocking=False)

        self.quantum_bytes_served += take
        if take < n:
            shortfall = n - take
            print(f"[qrng] WARNING: entropy pool exhausted — serving {shortfall}/{n} "
                  f"requested bytes via secrets.token_bytes() fallback (NOT quantum-sourced)")
            out += secrets.token_bytes(shortfall)
            self.fallback_bytes_served += shortfall

        return out

    def stats(self):
        return {
            "pool_bytes_remaining": len(self._pool),
            "quantum_bytes_served": self.quantum_bytes_served,
            "fallback_bytes_served": self.fallback_bytes_served,
        }


_pool = QuantumEntropyPool()


def prime_pool():
    """Call once at process startup (blocking) to front-load the entropy pool."""
    _pool.prime()


def get_quantum_bytes(n):
    """Returns n bytes of entropy: real ANU QRNG data if the local pool has
    it, else a cryptographically secure fallback. Never blocks on the network.
    """
    return _pool.get_bytes(n)


def pool_stats():
    """Diagnostics: how much of the served entropy was real quantum data
    vs. fallback, and how much is left in the pool."""
    return _pool.stats()
