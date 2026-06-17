"""Client for the Imprenta Nacional 'Diario Oficial' public consultation portal.

The portal (https://svrpubindc.imprenta.gov.co/diario/) is a JSF/PrimeFaces app.
Obtaining an edition PDF is a 3-step, session-bound flow:

  1. GET /diario/                -> JSESSIONID cookie + javax.faces.ViewState,
                                    plus a datatable listing the most recent
                                    editions (newest first) with a per-row
                                    "Ver Diario" submit button.
  2. POST the row button         -> a viewer page containing a PrimeFaces
                                    streamed-content URL (dynamiccontent...).
  3. GET that streamed-content   -> the PDF bytes (same session).

Searching by date or edition number is a POST of the search form (btnBuscar)
that re-renders the datatable with the matching row, after which the same
download flow applies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

ORIGIN = "https://svrpubindc.imprenta.gov.co"
BASE_URL = f"{ORIGIN}/diario/"
USER_AGENT = "Mozilla/5.0 (compatible; diario-oficial-mcp/0.1)"

_VIEWSTATE_RE = re.compile(
    r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"'
)
_NUM_RE = re.compile(
    r'dtbDiariosOficiales:(\d+):numeroDiario"[^>]*>([^<]*)</label>'
)
_TIPO_RE = re.compile(
    r'dtbDiariosOficiales:%s:tipoEdicion"[^>]*>([^<]*)</label>'
)
_FECHA_RE = re.compile(
    r'dtbDiariosOficiales:%s:fechaDiario"[^>]*>([^<]*)</label>'
)
_DYNAMIC_RE = re.compile(r'data="([^"]*dynamiccontent[^"]*)"')


class DiarioOficialError(RuntimeError):
    """Raised when the portal response cannot be parsed or no edition matches."""


@dataclass
class Edition:
    """A row in the editions datatable."""

    row_index: str
    numero: str  # e.g. "53.524"
    tipo: str  # e.g. "Ordinaria"
    fecha: str  # dd/MM/yyyy

    def as_dict(self) -> dict:
        return {"numero": self.numero, "tipo": self.tipo, "fecha": self.fecha}


def _normalize_number(value: str) -> str:
    """Strip thousands separators and whitespace: '53.524' -> '53524'."""
    return re.sub(r"[.\s]", "", value)


def _parse_viewstate(html: str) -> str:
    m = _VIEWSTATE_RE.search(html)
    if not m:
        raise DiarioOficialError("Could not find JSF ViewState in portal response.")
    return m.group(1)


def _parse_editions(html: str) -> list[Edition]:
    editions: list[Edition] = []
    for m in _NUM_RE.finditer(html):
        idx, numero = m.group(1), m.group(2).strip()
        tipo_m = re.search(_TIPO_RE.pattern % idx, html)
        fecha_m = re.search(_FECHA_RE.pattern % idx, html)
        editions.append(
            Edition(
                row_index=idx,
                numero=numero,
                tipo=tipo_m.group(1).strip() if tipo_m else "",
                fecha=fecha_m.group(1).strip() if fecha_m else "",
            )
        )
    return editions


def _form_fields(viewstate: str, **overrides: str) -> dict[str, str]:
    """Base set of JSF form fields proven to work for search/download POSTs."""
    fields = {
        "frmConDiario": "frmConDiario",
        "numeroDiarioOf": "",
        "numeroRecibo": "",
        "tipoNorma_focus": "",
        "tipoNorma_input": "",
        "numeroNorma": "",
        "entidad_input": "",
        "entidad_hinput": "",
        "fechaInicial_input": "",
        "fechaFinal_input": "",
        "dtbDiariosOficiales_selection": "",
        "javax.faces.ViewState": viewstate,
    }
    fields.update(overrides)
    return fields


class DiarioOficialClient:
    """Stateful client over a single HTTP session against the portal."""

    def __init__(self, timeout: float = 120.0) -> None:
        # httpx bundles certifi, so TLS verification works out of the box.
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=timeout,
            follow_redirects=True,
        )

    def __enter__(self) -> "DiarioOficialClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- low level steps -------------------------------------------------

    def _landing(self) -> tuple[str, str, list[Edition]]:
        resp = self._http.get("")
        resp.raise_for_status()
        html = resp.text
        return html, _parse_viewstate(html), _parse_editions(html)

    def _search(self, viewstate: str, **criteria: str) -> tuple[str, str, list[Edition]]:
        fields = _form_fields(viewstate, btnBuscar="btnBuscar", **criteria)
        resp = self._http.post("", data=fields)
        resp.raise_for_status()
        html = resp.text
        return html, _parse_viewstate(html), _parse_editions(html)

    def _download_row(self, edition: Edition, viewstate: str) -> bytes:
        button = f"dtbDiariosOficiales:{edition.row_index}:j_idt38"
        fields = _form_fields(viewstate, **{button: button})
        viewer = self._http.post("", data=fields)
        viewer.raise_for_status()
        m = _DYNAMIC_RE.search(viewer.text)
        if not m:
            raise DiarioOficialError(
                "Viewer page did not contain a PDF resource link "
                f"(edition {edition.numero})."
            )
        res_url = m.group(1).replace("&amp;", "&")
        # The resource path is server-absolute (/diario/...); resolve against the
        # origin so httpx does not prepend the base_url path.
        if res_url.startswith("/"):
            res_url = ORIGIN + res_url
        pdf = self._http.get(res_url)
        pdf.raise_for_status()
        if pdf.content[:4] != b"%PDF":
            raise DiarioOficialError(
                f"Downloaded resource for edition {edition.numero} is not a PDF."
            )
        return pdf.content

    # --- public API ------------------------------------------------------

    def list_recent(self) -> list[Edition]:
        """Return the most recent editions listed on the landing page (newest first)."""
        _, _, editions = self._landing()
        return editions

    def fetch_latest(self) -> tuple[Edition, bytes]:
        _, viewstate, editions = self._landing()
        if not editions:
            raise DiarioOficialError("No editions listed on the portal landing page.")
        latest = editions[0]
        return latest, self._download_row(latest, viewstate)

    def fetch_by_date(self, date: str) -> tuple[Edition, bytes]:
        """date in dd/MM/yyyy."""
        _, viewstate, _ = self._landing()
        _, viewstate, editions = self._search(
            viewstate, fechaInicial_input=date, fechaFinal_input=date
        )
        match = next((e for e in editions if e.fecha == date), None)
        if match is None:
            raise DiarioOficialError(f"No edition found for date {date}.")
        return match, self._download_row(match, viewstate)

    def fetch_by_number(self, number: str) -> tuple[Edition, bytes]:
        target = _normalize_number(number)
        _, viewstate, _ = self._landing()
        _, viewstate, editions = self._search(viewstate, numeroDiarioOf=target)
        match = next(
            (e for e in editions if _normalize_number(e.numero) == target), None
        )
        if match is None:
            raise DiarioOficialError(f"No edition found for number {number}.")
        return match, self._download_row(match, viewstate)
