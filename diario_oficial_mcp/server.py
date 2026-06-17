"""MCP server exposing tools to obtain the Colombian Diario Oficial daily PDF.

Tools:
  - list_recent_editions: show the most recent editions (no download).
  - download_latest_edition: download the newest published edition.
  - download_edition_by_date: download the edition for a given day (dd/MM/yyyy).
  - download_edition_by_number: download a specific edition by its number.

Each download tool saves the PDF to disk and returns its path plus metadata,
so a downstream agent can read it or build alerts on top of it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .client import DiarioOficialClient, DiarioOficialError, Edition

mcp = FastMCP("diario-oficial")


def _default_output_dir() -> Path:
    env = os.environ.get("DIARIO_OFICIAL_DIR")
    base = Path(env) if env else Path.home() / "Downloads" / "diario-oficial"
    return base


def _resolve_dir(output_dir: str | None) -> Path:
    target = Path(output_dir).expanduser() if output_dir else _default_output_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def _filename(edition: Edition) -> str:
    numero = re.sub(r"[.\s]", "", edition.numero) or "edicion"
    # dd/MM/yyyy -> yyyy-MM-dd for sortable filenames
    parts = edition.fecha.split("/")
    fecha = "-".join(reversed(parts)) if len(parts) == 3 else "fecha"
    return f"DiarioOficial_{numero}_{fecha}.pdf"


def _save(edition: Edition, pdf: bytes, output_dir: str | None) -> dict:
    directory = _resolve_dir(output_dir)
    path = directory / _filename(edition)
    path.write_bytes(pdf)
    return {
        "numero": edition.numero,
        "tipo": edition.tipo,
        "fecha": edition.fecha,
        "path": str(path),
        "size_bytes": len(pdf),
    }


@mcp.tool()
def list_recent_editions() -> list[dict]:
    """List the most recently published Diario Oficial editions (newest first).

    Returns each edition's number, type (e.g. Ordinaria), and date (dd/MM/yyyy).
    Use this to discover what is available before downloading.
    """
    with DiarioOficialClient() as client:
        return [e.as_dict() for e in client.list_recent()]


@mcp.tool()
def download_latest_edition(output_dir: str | None = None) -> dict:
    """Download the newest published Diario Oficial edition as a PDF.

    Args:
        output_dir: Directory to save the PDF. Defaults to the DIARIO_OFICIAL_DIR
            environment variable, or ~/Downloads/diario-oficial.

    Returns metadata (numero, tipo, fecha) plus the saved file path and size.
    """
    with DiarioOficialClient() as client:
        edition, pdf = client.fetch_latest()
    return _save(edition, pdf, output_dir)


@mcp.tool()
def download_edition_by_date(date: str, output_dir: str | None = None) -> dict:
    """Download the Diario Oficial edition published on a specific date.

    Args:
        date: Publication date in dd/MM/yyyy format (e.g. "16/06/2026").
        output_dir: Directory to save the PDF (see download_latest_edition).

    Returns metadata plus the saved file path and size. Raises if no edition
    was published on that date.
    """
    with DiarioOficialClient() as client:
        edition, pdf = client.fetch_by_date(date)
    return _save(edition, pdf, output_dir)


@mcp.tool()
def download_edition_by_number(number: str, output_dir: str | None = None) -> dict:
    """Download a specific Diario Oficial edition by its edition number.

    Args:
        number: Edition number, with or without thousands separators
            (e.g. "53524" or "53.524").
        output_dir: Directory to save the PDF (see download_latest_edition).

    Returns metadata plus the saved file path and size. Raises if the edition
    number is not found.
    """
    with DiarioOficialClient() as client:
        edition, pdf = client.fetch_by_number(number)
    return _save(edition, pdf, output_dir)


def main() -> None:
    """Entry point for running the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
