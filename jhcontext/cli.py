"""jhcontext CLI — serve, mcp, audit commands."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jhcontext",
        description="PAC-AI: Protocol for Auditable Context in AI",
    )
    sub = parser.add_subparsers(dest="command")

    # --- serve ---
    serve_p = sub.add_parser("serve", help="Start jhcontext REST API server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8400)
    serve_p.add_argument("--db", default=None, help="SQLite database path")
    serve_p.add_argument("--tls-cert", default=None)
    serve_p.add_argument("--tls-key", default=None)

    # --- mcp ---
    mcp_p = sub.add_parser("mcp", help="Start jhcontext MCP server (stdio)")
    mcp_p.add_argument("--db", default=None, help="SQLite database path")
    mcp_p.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    mcp_p.add_argument("--port", type=int, default=8401)

    # --- version ---
    sub.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "serve":
        _run_serve(args)
    elif args.command == "mcp":
        _run_mcp(args)
    elif args.command == "version":
        print("jhcontext 0.2.0")
    else:
        parser.print_help()


def _run_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
        from .server.app import create_app
    except ImportError:
        print("Server dependencies not installed. Run: pip install jhcontext[server]", file=sys.stderr)
        sys.exit(1)

    app = create_app(db_path=args.db)

    ssl_kwargs = {}
    if args.tls_cert and args.tls_key:
        ssl_kwargs["ssl_certfile"] = args.tls_cert
        ssl_kwargs["ssl_keyfile"] = args.tls_key

    print(f"Starting jhcontext server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, **ssl_kwargs)


def _run_mcp(args: argparse.Namespace) -> None:
    try:
        import asyncio
        from .server.mcp_server import run_mcp_stdio
    except ImportError:
        print("MCP dependencies not installed. Run: pip install jhcontext[server]", file=sys.stderr)
        sys.exit(1)

    if args.transport == "stdio":
        asyncio.run(run_mcp_stdio(db_path=args.db))
    else:
        print(f"SSE transport on port {args.port} (not yet implemented)")
        sys.exit(1)


if __name__ == "__main__":
    main()
