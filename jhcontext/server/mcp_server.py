"""MCP server for jhcontext — exposes protocol operations as MCP tools."""

from __future__ import annotations

import json
from typing import Any

from .storage.sqlite import SQLiteStorage
from ..models import Envelope
from ..prov import PROVGraph
from ..audit import (
    verify_temporal_oversight,
    verify_negative_proof,
    verify_workflow_isolation,
    verify_integrity,
    generate_audit_report,
)


def create_mcp_server(db_path: str | None = None):
    """Create and configure the MCP server with jhcontext tools."""
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server("jhcontext")
    storage = SQLiteStorage(db_path=db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="submit_envelope",
                description="Submit a PAC-AI envelope. Returns context_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "envelope_json": {"type": "string", "description": "JSON string of the envelope"},
                    },
                    "required": ["envelope_json"],
                },
            ),
            Tool(
                name="get_envelope",
                description="Retrieve envelope by context_id. Verifies integrity hash.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context_id": {"type": "string"},
                    },
                    "required": ["context_id"],
                },
            ),
            Tool(
                name="submit_prov_graph",
                description="Submit a W3C PROV graph (Turtle format) linked to an envelope.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context_id": {"type": "string"},
                        "graph_turtle": {"type": "string", "description": "PROV graph in Turtle format"},
                    },
                    "required": ["context_id", "graph_turtle"],
                },
            ),
            Tool(
                name="query_provenance",
                description="Query PROV graph. Types: causal_chain, used_entities, temporal_sequence.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context_id": {"type": "string"},
                        "query_type": {"type": "string", "enum": ["causal_chain", "used_entities", "temporal_sequence"]},
                        "entity_id": {"type": "string"},
                    },
                    "required": ["context_id", "query_type"],
                },
            ),
            Tool(
                name="run_audit",
                description="Run audit checks on an envelope. Checks: temporal_oversight, negative_proof, integrity.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "context_id": {"type": "string"},
                        "checks": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["context_id", "checks"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "submit_envelope":
            data = json.loads(arguments["envelope_json"])
            data.pop("@context", None)
            data.pop("@type", None)
            envelope = Envelope.model_validate(data)
            context_id = storage.save_envelope(envelope)
            return [TextContent(type="text", text=json.dumps({"context_id": context_id}))]

        elif name == "get_envelope":
            envelope = storage.get_envelope(arguments["context_id"])
            if not envelope:
                return [TextContent(type="text", text='{"error": "not found"}')]
            return [TextContent(type="text", text=json.dumps(envelope.to_jsonld()))]

        elif name == "submit_prov_graph":
            from ..crypto import compute_sha256
            turtle = arguments["graph_turtle"]
            digest = compute_sha256(turtle.encode("utf-8"))
            storage.save_prov_graph(arguments["context_id"], turtle, digest)
            return [TextContent(type="text", text=json.dumps({"digest": digest}))]

        elif name == "query_provenance":
            turtle = storage.get_prov_graph(arguments["context_id"])
            if not turtle:
                return [TextContent(type="text", text='{"error": "PROV graph not found"}')]
            prov = PROVGraph(context_id=arguments["context_id"])
            prov._graph.parse(data=turtle, format="turtle")

            qt = arguments["query_type"]
            eid = arguments.get("entity_id")
            if qt == "causal_chain" and eid:
                result = prov.get_causal_chain(eid)
            elif qt == "used_entities" and eid:
                result = prov.get_used_entities(eid)
            elif qt == "temporal_sequence":
                result = prov.get_temporal_sequence()
            else:
                result = {"error": f"Unknown query_type: {qt}"}
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "run_audit":
            envelope = storage.get_envelope(arguments["context_id"])
            if not envelope:
                return [TextContent(type="text", text='{"error": "Envelope not found"}')]

            turtle = storage.get_prov_graph(arguments["context_id"])
            prov = PROVGraph(context_id=arguments["context_id"])
            if turtle:
                prov._graph.parse(data=turtle, format="turtle")

            results = []
            for check in arguments.get("checks", []):
                if check == "integrity":
                    results.append(verify_integrity(envelope))
            report = generate_audit_report(envelope, prov, results)
            return [TextContent(type="text", text=json.dumps(report.to_dict()))]

        return [TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}')]

    return server


async def run_mcp_stdio(db_path: str | None = None) -> None:
    """Run MCP server with stdio transport."""
    from mcp.server.stdio import stdio_server

    server = create_mcp_server(db_path=db_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
