from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .citygml.enrich import run_enrich
from .citygml.extract import run_extract
from .citygml.visualize import run_visualize
from .config import load_config
from .detect.infer import run_detect
from .logging import configure_logging
from .mapillary.fetch import run_fetch
from .merge.report import run_merge
from .pipeline import resolve_run_dir, run_pipeline

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _main(
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    configure_logging(log_level)


@app.command()
def version() -> None:
    typer.echo(__version__)


@app.command()
def extract(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    if cfg.footprint.kind != "citygml":
        typer.echo("footprint.kind != 'citygml'; nothing to extract.", err=True)
        raise typer.Exit(code=2)
    run_dir = resolve_run_dir(cfg)
    run_extract(cfg, run_dir / "stage0_extract")


@app.command()
def fetch(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    run_dir = resolve_run_dir(cfg)
    if cfg.footprint.kind == "citygml" and (
        cfg.footprint.path is None or not cfg.footprint.path.exists()
    ):
        run_extract(cfg, run_dir / "stage0_extract")
    run_fetch(cfg, run_dir / "stage1_fetch")


@app.command()
def detect(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    run_dir = resolve_run_dir(cfg)
    run_detect(cfg, run_dir / "stage1_fetch", run_dir / "stage2_detect")


@app.command()
def merge(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    run_dir = resolve_run_dir(cfg)
    if cfg.footprint.kind == "citygml" and (
        cfg.footprint.path is None or not cfg.footprint.path.exists()
    ):
        run_extract(cfg, run_dir / "stage0_extract")
    run_merge(cfg, run_dir / "stage2_detect", run_dir / "stage3_merge")


@app.command()
def enrich(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    if not cfg.enrichment.enabled:
        typer.echo("enrichment.enabled=false; skipping.", err=True)
        raise typer.Exit(code=0)
    run_dir = resolve_run_dir(cfg)
    run_enrich(cfg, run_dir / "stage3_merge", run_dir / "stage4_enrich")


@app.command()
def visualize(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    if not cfg.visualization.enabled:
        typer.echo("visualization.enabled=false; skipping.", err=True)
        raise typer.Exit(code=0)
    run_dir = resolve_run_dir(cfg)
    run_visualize(cfg, run_dir / "stage5_publish")


@app.command()
def pipeline(
    config: Path = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_config(config)
    run_pipeline(cfg)


if __name__ == "__main__":
    app()
