from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
WINDOW = 10  # seconds

# Fixed orders for pagination
orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# Idempotency storage
idempotency_store = {}
next_order_id = TOTAL_ORDERS + 1

# Rate limit storage
client_requests = {}


def check_rate_limit(client_id: str):
    now = time.time()

    if client_id not in client_requests:
        client_requests[client_id] = []

    # Remove expired timestamps
    client_requests[client_id] = [
        t for t in client_requests[client_id]
        if now - t < WINDOW
    ]

    # Rate limit reached
    if len(client_requests[client_id]) >= RATE_LIMIT:
        retry_after = max(
            1,
            int(WINDOW - (now - client_requests[client_id][0])) + 1
        )

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

    client_requests[client_id].append(now)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header("default", alias="X-Client-Id"),
):
    global next_order_id

    check_rate_limit(client_id)

    # Same key → same order id
    if idempotency_key in idempotency_store:
        return {"id": idempotency_store[idempotency_key]}

    order_id = next_order_id
    next_order_id += 1

    idempotency_store[idempotency_key] = order_id

    return {"id": order_id}


@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    client_id: str = Header("default", alias="X-Client-Id"),
):
    check_rate_limit(client_id)

    if limit <= 0:
        limit = 10

    try:
        start = int(cursor) if cursor else 0
    except ValueError:
        start = 0

    if start < 0:
        start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }
