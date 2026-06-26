import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException

USERS_SERVICE_URL = os.environ["USERS_SERVICE_URL"]
ITEMS_SERVICE_URL = os.environ["ITEMS_SERVICE_URL"]

app = FastAPI(title="api-gateway")

_client = httpx.AsyncClient(timeout=10)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}


async def _proxy(client: httpx.AsyncClient, method: str, url: str, request: Request) -> Response:
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    try:
        upstream = await client.request(method, url, content=body, headers=headers, params=request.query_params)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Upstream unreachable: {exc}")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


@app.api_route("/users", methods=["GET", "POST"])
async def users_collection(request: Request):
    return await _proxy(_client, request.method, f"{USERS_SERVICE_URL}/users", request)


@app.api_route("/users/{user_id}", methods=["GET", "DELETE"])
async def users_item(user_id: int, request: Request):
    return await _proxy(_client, request.method, f"{USERS_SERVICE_URL}/users/{user_id}", request)


@app.api_route("/items", methods=["GET", "POST"])
async def items_collection(request: Request):
    return await _proxy(_client, request.method, f"{ITEMS_SERVICE_URL}/items", request)


@app.api_route("/items/{item_id}", methods=["GET", "DELETE"])
async def items_item(item_id: int, request: Request):
    return await _proxy(_client, request.method, f"{ITEMS_SERVICE_URL}/items/{item_id}", request)
