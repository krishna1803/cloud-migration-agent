"""
Cloud Migration Agent Platform v4.0.0
Main entry point for the API server and UI.
"""

import argparse
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.utils.logger import logger


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Cloud Migration Agent Platform",
        description="AI-powered migration from AWS/Azure/GCP to Oracle Cloud Infrastructure (OCI)",
        version="4.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup_event():
        logger.info("Cloud Migration Agent Platform v4.0.0 starting up")
        logger.info("API docs available at: http://localhost:8000/docs")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Cloud Migration Agent Platform shutting down")

    return app


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    app = create_app()
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(
        "main:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
        log_level="info"
    )


def run_ui(host: str = "0.0.0.0", port: int = 7860):
    """Run the Gradio UI."""
    try:
        from src.ui.app import create_ui
        ui = create_ui()
        logger.info(f"Starting Gradio UI on {host}:{port}")
        ui.launch(server_name=host, server_port=port, share=False)
    except ImportError as e:
        logger.error(f"Could not start UI: {e}")
        print(f"Error: {e}")
        print("Install UI dependencies: pip install gradio requests")
        sys.exit(1)


# WSGI-compatible app for production deployment
app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud Migration Agent Platform v4.0.0")
    parser.add_argument(
        "mode",
        choices=["api", "ui", "both"],
        default="api",
        nargs="?",
        help="Run mode: api (FastAPI), ui (Gradio), or both"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--api-port", type=int, default=8000, help="API server port")
    parser.add_argument("--ui-port", type=int, default=7860, help="UI server port")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload (dev mode)")

    args = parser.parse_args()

    if args.mode == "api":
        run_api(args.host, args.api_port, args.reload)
    elif args.mode == "ui":
        run_ui(args.host, args.ui_port)
    elif args.mode == "both":
        import threading
        api_thread = threading.Thread(
            target=run_api,
            args=(args.host, args.api_port, False),
            daemon=True
        )
        api_thread.start()
        logger.info(f"API server started on port {args.api_port}")
        run_ui(args.host, args.ui_port)
