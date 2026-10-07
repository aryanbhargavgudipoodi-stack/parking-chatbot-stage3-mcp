"""
Minimal in-memory fixed-window rate limiter for the write endpoint.
Not meant for multi-process/distributed deployments (use Redis there) --
sufficient to demonstrate basic abuse protection for this project's scope.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 60
_MAX_REQUESTS_PER_WINDOW = 30
_hits = defaultdict(deque)


def rate_limit(request: Request):
    client_id = request.client.host if request.client else "unknown"
    now = time.time()
    hits = _hits[client_id]
    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many requests, slow down")
    hits.append(now)