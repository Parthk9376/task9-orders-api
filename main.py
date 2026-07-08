from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 45
RATE_LIMIT = 18
WINDOW = 10

# Orders 1..45
orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# Idempotency store
idempotency = {}
next_order_id = TOTAL_ORDERS + 1

# Per-client timestamps
rate_limits = {}


def check_rate_limit(client_id: str):
    now = time.time()

    timestamps = rate_limits.setdefault(client_id, [])

    # Remove timestamps older than WINDOW
    while timestamps and now - timestamps[0] >= WINDOW:
        timestamps.pop(0)

    if len(timestamps) >= RATE_LIMIT:
        retry = max(1, int(WINDOW - (now - timestamps[0])) + 1)

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry)},
        )

    timestamps.append(now)
    return None


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/orders")
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header(..., alias="X-Client-Id"),
):
    global next_order_id

    limited = check_rate_limit(x_client_id)
    if limited:
        return limited

    if idempotency_key in idempotency:
        return {"id": idempotency[idempotency_key]}

    order_id = next_order_id
    next_order_id += 1

    idempotency[idempotency_key] = order_id

    return JSONResponse(
        status_code=201,
        content={"id": order_id},
    )


@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: str = Header(..., alias="X-Client-Id"),
):
    limited = check_rate_limit(x_client_id)
    if limited:
        return limited

    if limit < 1:
        limit = 10

    start = int(cursor) if cursor else 0
    start = max(0, start)

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
