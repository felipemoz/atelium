from __future__ import annotations
import asyncio
import typer
from rich.console import Console

app = typer.Typer(help="Infrastructure management")
console = Console()


@app.command("health")
def health():
    """Check infrastructure health."""
    async def _run():
        from ...infra.redis import ping_redis
        from ...infra.postgres import ping_postgres
        from ...infra.ollama import get_ollama

        redis_ok = await ping_redis()
        pg_ok = await ping_postgres()
        ollama_ok = await get_ollama().ping()

        def _status(ok: bool) -> str:
            return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

        console.print(f"Redis:    {_status(redis_ok)}")
        console.print(f"Postgres: {_status(pg_ok)}")
        console.print(f"Ollama:   {_status(ollama_ok)}")

        if not (redis_ok and pg_ok):
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command("migrate")
def migrate():
    """Run database migrations."""
    import subprocess, sys
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True
    )
    console.print(result.stdout)
    if result.returncode != 0:
        console.print(f"[red]{result.stderr}[/red]")
        raise typer.Exit(result.returncode)
    console.print("[green]✓[/green] Migrations complete")


@app.command("models")
def list_models():
    """List available Ollama models."""
    async def _run():
        from ...infra.ollama import get_ollama
        models = await get_ollama().list_models()
        if not models:
            console.print("[yellow]No models found[/yellow]")
        for m in models:
            console.print(f"  • {m}")

    asyncio.run(_run())


@app.command("pull-model")
def pull_model(
    model: str = typer.Argument(..., help="Model name to pull (e.g. llama3:70b)"),
):
    """Pull an Ollama model."""
    async def _run():
        from ...infra.ollama import get_ollama
        console.print(f"Pulling [bold]{model}[/bold]...")
        await get_ollama().pull_model(model)
        console.print(f"[green]✓[/green] Model {model!r} ready")

    asyncio.run(_run())
