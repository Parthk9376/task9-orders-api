from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import time

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Assigned values
TOTAL_ORDERS = 45
RATE_LIMIT = 18
WINDOW = 10  # seconds

# Fixed catalog of orders (IDs 1..45)
catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# Idempotency storage
idempotency_store = {}
next_order_id = TOTAL_ORDERS + 1

# Rate limit storage
client_requests = {}


def check_rate_limit(client_id: str, response: Response):
    now = time.time()

    if client_id not in client_requests:
        client_requests[client_id] = []

    # Keep only requests within last WINDOW seconds
    client_requests[client_id] = [
        t for t in client_requests[client_id]
        if now - t < WINDOW
    ]

    if len(client_requests[client_id]) >= RATE_LIMIT:
        retry_after = max(
            1,
            int(WINDOW - (now - client_requests[client_id][0]))
        )
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    client_requests[client_id].append(now)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header("default", alias="X-Client-Id"),
):
    global next_order_id

    check_rate_limit(client_id, response)

    # Return existing order for same idempotency key
    if idempotency_key in idempotency_store:
        return {"id": idempotency_store[idempotency_key]}

    order_id = next_order_id
    next_order_id += 1

    idempotency_store[idempotency_key] = order_id

    return {"id": order_id}


@app.get("/orders")
def list_orders(
    response: Response,
    limit: int = 10,
    cursor: Optional[str] = None,
    client_id: str = Header("default", alias="X-Client-Id"),
):
    check_rate_limit(client_id, response)

    try:
        start = int(cursor) if cursor else 0
    except ValueError:
        start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }
