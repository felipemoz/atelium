from __future__ import annotations
import typer

from .commands import agent_cmd, pipeline_cmd, server_cmd, infra_cmd

app = typer.Typer(
    name="atelium",
    help="Atelium — Fault-Tolerant Agent Network Platform",
    no_args_is_help=True,
)

app.add_typer(agent_cmd.app, name="agent")
app.add_typer(pipeline_cmd.app, name="pipeline")
app.add_typer(server_cmd.app, name="server")
app.add_typer(infra_cmd.app, name="infra")


@app.callback()
def main():
    """Atelium CLI"""


if __name__ == "__main__":
    app()
