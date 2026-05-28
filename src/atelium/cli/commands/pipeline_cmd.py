from __future__ import annotations
import asyncio
import json
from pathlib import Path
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(help="Run and inspect pipelines")
console = Console()


@app.command("run")
def run(
    manifest_name: str = typer.Argument(..., help="Registered agent name"),
    input_file: Path = typer.Option(None, "--input", "-i", help="JSON file with input data"),
    input_json: str = typer.Option(None, "--json", "-j", help="Inline JSON input"),
):
    """Run a pipeline for a registered agent."""
    if input_file:
        input_data = json.loads(input_file.read_text())
    elif input_json:
        input_data = json.loads(input_json)
    else:
        typer.echo("Provide --input or --json", err=True)
        raise typer.Exit(1)

    async def _run():
        from ...infra import get_redis, get_pool
        from ...core.state import StepStateManager
        from ...core.router import EmergentRouter
        from ...infra.ollama import get_ollama
        from ...runtime.executor import AgentExecutor
        from ...runtime.graph import PipelineGraph
        from ...runtime.registry import AgentRegistry

        redis = await get_redis()
        pool = await get_pool()
        ollama = get_ollama()

        state = StepStateManager(redis_client=redis, postgres_pool=pool)
        router = EmergentRouter(redis_client=redis, postgres_pool=pool, embedder=ollama)
        executor = AgentExecutor(state_manager=state, llm_client=ollama, router=router)
        graph = PipelineGraph(state_manager=state, executor=executor, router=router)

        registry = AgentRegistry()
        manifest = await registry.get(manifest_name)
        if not manifest:
            console.print(f"[red]Agent {manifest_name!r} not found[/red]")
            raise typer.Exit(1)

        console.print(f"Running pipeline for [bold]{manifest_name}[/bold]...")
        pipeline = await graph.run(manifest=manifest, input_data=input_data)

        status_color = "green" if pipeline.status.value == "succeeded" else "red"
        console.print(
            f"[{status_color}]Pipeline {pipeline.pipeline_id} → {pipeline.status.value}[/{status_color}]"
            + (f" ({pipeline.elapsed_ms}ms)" if pipeline.elapsed_ms else "")
        )

    asyncio.run(_run())


@app.command("steps")
def steps(
    pipeline_id: str = typer.Argument(..., help="Pipeline UUID"),
):
    """List all steps for a pipeline."""
    async def _run():
        from ...infra import get_redis, get_pool
        from ...core.state import StepStateManager

        redis = await get_redis()
        pool = await get_pool()
        state = StepStateManager(redis_client=redis, postgres_pool=pool)
        steps = await state.load_pipeline_steps(UUID(pipeline_id))

        if not steps:
            console.print("[yellow]No steps found[/yellow]")
            return

        table = Table("Step ID", "Agent", "Status", "Iter", "Elapsed", "Tokens")
        for s in steps:
            status_style = "green" if s.status.value == "succeeded" else "red" if "fail" in s.status.value else "yellow"
            table.add_row(
                str(s.step_id)[:8] + "...",
                s.agent_name,
                f"[{status_style}]{s.status.value}[/{status_style}]",
                str(s.iteration),
                f"{s.elapsed_ms}ms" if s.elapsed_ms else "-",
                str(s.tokens_used),
            )
        console.print(table)

    asyncio.run(_run())
