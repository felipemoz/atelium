from __future__ import annotations
import typer

app = typer.Typer(help="Manage the API server")


@app.command("start")
def start(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable hot reload"),
    workers: int = typer.Option(1, help="Number of worker processes"),
):
    """Start the Atelium API server."""
    import uvicorn
    uvicorn.run(
        "atelium.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )
