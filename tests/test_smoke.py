"""Smoke tests against the live Diario Oficial portal.

These hit the real government portal, so they require network access. They are
the early-warning system for the most brittle part of this project: the
PrimeFaces HTML parsing in client.py. If the portal changes its markup, these
fail loudly instead of the tools silently returning nothing.

Run with:  pytest -q
Skip live tests offline:  they will be skipped automatically on network error.
"""

from __future__ import annotations

import re

import httpx
import pytest

from diario_oficial_mcp.client import DiarioOficialClient, DiarioOficialError

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


@pytest.fixture(scope="module")
def client():
    c = DiarioOficialClient()
    yield c
    c.close()


def _skip_if_offline(exc: Exception) -> None:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
        pytest.skip(f"portal unreachable: {exc!r}")


def test_list_recent_returns_editions(client):
    """The landing page must yield parseable edition rows."""
    try:
        editions = client.list_recent()
    except Exception as exc:  # noqa: BLE001 - convert network issues to skips
        _skip_if_offline(exc)
        raise

    assert editions, "no editions parsed from landing page (HTML may have changed)"
    first = editions[0]
    assert first.numero, "edition number missing"
    assert DATE_RE.match(first.fecha), f"unexpected date format: {first.fecha!r}"


def test_download_latest_is_pdf(client):
    """The full 3-step download flow must return real PDF bytes."""
    try:
        edition, pdf = client.fetch_latest()
    except DiarioOficialError:
        raise
    except Exception as exc:  # noqa: BLE001
        _skip_if_offline(exc)
        raise

    assert pdf[:4] == b"%PDF", "downloaded resource is not a PDF"
    assert len(pdf) > 10_000, "PDF suspiciously small"
    assert edition.numero
