"""The API: the MCP server's streamable HTTP app at /mcp, the chat stream, the answer log, health.

    POST /mcp                       the MCP server at revision 2026-07-28, stateless, read only
    POST /v1/chat                   one turn, streamed as server sent events
    POST /v1/chat/{thread}/resume   the person's choice for an interrupt
    GET  /v1/answers/{id}           a stored answer with its trace id
    GET  /v1/answers                the recent answers (the demo queue on the desk)
    GET  /v1/traces/{trace_id}      the spans of one turn
    GET  /health                    version, revision, the provider the router would pick, budgets

The public endpoint needs no token; the client budget (60 an hour, 600 a day per client) and the
ceilings on rows, time and k protect the free tier. The agent is a client of the MCP server mounted
here, over streamable HTTP on the loopback address, exactly as any host is.
"""

from __future__ import annotations

import contextlib
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from mcp import Client
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from readback_agent.run import Agent
from readback_core.statements import STATEMENT
from readback_mcp_server.server import PROTOCOL_REVISION, VERSION, build_server
from readback_providers.ledger import Ledger
from readback_providers.router import Router
from readback_tracing import install

from readback_api import db
from readback_api.client_budget import ClientBudget, MemoryCounter

PORT = int(os.environ.get("PORT", "8080"))


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    thread_id: str | None = Field(default=None, max_length=64)
    provider: str | None = Field(default=None, max_length=40)


class ResumeIn(BaseModel):
    choice: str = Field(min_length=1, max_length=200)
    provider: str | None = Field(default=None, max_length=40)


def allowed_hosts() -> list[str]:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", "testserver"]
    for h in os.environ.get("READBACK_PUBLIC_HOSTS", "readback-mcp.vercel.app").split(","):
        h = h.strip()
        if h:
            hosts += [h, f"{h}:*"]
    return hosts


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def checkpointer() -> Any:
    url = db.database_url()
    if url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        from psycopg.rows import dict_row

        conn_url = url.replace("postgresql+psycopg://", "postgresql://")
        conn = await AsyncConnection.connect(conn_url, autocommit=True, prepare_threshold=0, row_factory=dict_row,
                                             options=f"-csearch_path={db.SCHEMA}")
        saver = AsyncPostgresSaver(conn)  # type: ignore[arg-type]
        await saver.setup()
        return saver
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


def create_app(*, agent_transport: str | None = None) -> FastAPI:
    exporter = install()
    server = build_server()
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts(),
                                         allowed_origins=["https://mekala27-45.github.io", "http://localhost:*", "http://127.0.0.1:*"])
    mcp_app = server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, transport_security=security)
    engine = db.engine()
    if engine.dialect.name != "postgresql":
        db.create_local(engine)
    log = db.Log(engine)
    ledger = Ledger(engine)
    budget = ClientBudget(db.SqlCounter(engine) if engine.dialect.name == "postgresql" else MemoryCounter())
    transport = agent_transport or os.environ.get("READBACK_AGENT_MCP", "http")
    state: dict[str, Any] = {}

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with server.session_manager.run():
            state["agent"] = Agent(ledger=ledger, checkpointer=await checkpointer())
            yield

    app = FastAPI(title="readback", version=VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["https://mekala27-45.github.io", "http://localhost:3000", "http://127.0.0.1:3000"],
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["content-type", "mcp-protocol-version", "mcp-method", "mcp-name"])

    @app.middleware("http")
    async def protect(request: Request, call_next: Any) -> Any:
        guarded = request.url.path.startswith(("/mcp", "/v1/chat")) and request.method == "POST"
        if guarded and client_address(request) not in {"127.0.0.1", "::1", "testclient"}:
            decision = budget.check(client_address(request))
            if not decision.allowed:
                return JSONResponse({"error": decision.message, "statement": STATEMENT}, status_code=429)
        return await call_next(request)

    def mcp_client() -> Client:
        if transport == "memory":
            return Client(server)
        return Client(f"http://127.0.0.1:{PORT}/mcp")

    async def events(question: str, thread_id: str | None, provider: str | None, resume: str | None) -> AsyncIterator[bytes]:
        agent: Agent = state["agent"]
        traces: set[str] = set()
        async with mcp_client() as client:
            async for event in agent.stream(client, question, thread_id=thread_id, provider=provider, resume=resume):
                traces.add(event["trace_id"])
                if event["event"] == "answer":
                    answer_id = uuid.uuid4().hex
                    event["answer"]["id"] = answer_id
                    # The audit row is written, and committed, before the final event is sent.
                    log.write_answer(answer_id, event["thread_id"], event["answer"])
                    event["answer_id"] = answer_id
                yield f"event: {event['event']}\ndata: {json.dumps(event, default=str)}\n\n".encode()
        # The turn's span closes when the stream ends; its spans are stored then.
        for trace_id in traces:
            log.write_spans(exporter.rows(trace_id))
        yield f"event: done\ndata: {json.dumps({'statement': STATEMENT})}\n\n".encode()

    @app.post("/v1/chat")
    async def chat(body: ChatIn) -> StreamingResponse:
        return StreamingResponse(events(body.question, body.thread_id, body.provider, None), media_type="text/event-stream",
                                 headers={"cache-control": "no-store", "x-accel-buffering": "no"})

    @app.post("/v1/chat/{thread_id}/resume")
    async def resume(thread_id: str, body: ResumeIn) -> StreamingResponse:
        return StreamingResponse(events("", thread_id, body.provider, body.choice), media_type="text/event-stream",
                                 headers={"cache-control": "no-store"})

    @app.get("/v1/answers/{answer_id}")
    async def get_answer(answer_id: str) -> dict[str, Any]:
        found = log.read_answer(answer_id)
        if found is None:
            raise HTTPException(404, detail={"error": "no such answer", "statement": STATEMENT})
        return found

    @app.get("/v1/answers")
    async def list_answers(limit: int = 20) -> dict[str, Any]:
        return {"answers": log.recent(limit), "statement": STATEMENT}

    @app.get("/v1/traces/{trace_id}")
    async def get_trace(trace_id: str) -> dict[str, Any]:
        return {"trace_id": trace_id, "spans": log.spans_of(trace_id), "statement": STATEMENT}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        agent: Agent | None = state.get("agent")
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("select 1")
            database = "ok"
        except Exception as err:  # the health route reports, it does not raise
            database = f"error: {type(err).__name__}"
        router = Router(agent.providers if agent else [], ledger) if agent else None
        pick = router.choose() if router else None
        return {
            "status": "ok",
            "version": VERSION,
            "protocol_revision": PROTOCOL_REVISION,
            "database": database,
            "provider": pick.provider.name if pick else "floor",
            "provider_reason": pick.reason if pick else "starting",
            "budgets": router.status() if router else [],
            "statement": STATEMENT,
        }

    # Last, so the routes above match first: the MCP app answers /mcp and nothing else.
    app.mount("/", mcp_app)
    return app
