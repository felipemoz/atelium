from __future__ import annotations
import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage agents")
console = Console()


@app.command("register")
def register(
    manifest: Path = typer.Argument(..., help="Path to agent manifest YAML"),
):
    """Register an agent from a manifest file."""
    async def _run():
        from ...runtime.registry import AgentRegistry
        registry = AgentRegistry()
        m = await registry.register(manifest)
        console.print(f"[green]✓[/green] Registered [bold]{m.metadata.name}[/bold] v{m.metadata.version}")

    asyncio.run(_run())


@app.command("unregister")
def unregister(
    name: str = typer.Argument(..., help="Agent name"),
):
    """Unregister an agent."""
    async def _run():
        from ...runtime.registry import AgentRegistry
        registry = AgentRegistry()
        await registry.unregister(name)
        console.print(f"[yellow]✓[/yellow] Unregistered [bold]{name}[/bold]")

    asyncio.run(_run())


@app.command("list")
def list_agents():
    """List registered agents."""
    async def _run():
        from ...runtime.registry import AgentRegistry
        registry = AgentRegistry()
        agents = await registry.list_agents()
        table = Table("Name", "Version", "Registered At")
        for a in agents:
            table.add_row(a["name"], a["version"], str(a.get("registered_at", "")))
        console.print(table)

    asyncio.run(_run())


@app.command("validate")
def validate(
    manifest: Path = typer.Argument(..., help="Path to agent manifest YAML"),
):
    """Validate a manifest without registering."""
    from ...manifest.loader import load_manifest
    from ...manifest.validator import validate_manifest

    try:
        m = load_manifest(manifest)
    except Exception as exc:
        console.print(f"[red]Parse error:[/red] {exc}")
        raise typer.Exit(1)

    result = validate_manifest(m)
    if result.errors:
        for e in result.errors:
            console.print(f"[red]ERROR:[/red] {e}")
        raise typer.Exit(1)
    for w in result.warnings:
        console.print(f"[yellow]WARN:[/yellow] {w}")
    console.print("[green]✓[/green] Manifest is valid")
