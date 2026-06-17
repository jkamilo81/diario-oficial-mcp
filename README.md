# Diario Oficial MCP

🌐 **English** | [Español](README.es.md)

An [MCP](https://modelcontextprotocol.io) server that obtains the Colombian
**Diario Oficial** daily PDF from the Imprenta Nacional public consultation
portal (`https://svrpubindc.imprenta.gov.co/diario/`).

The server's job is acquisition: it downloads the official PDF and returns its
file path plus metadata. Reading the document or building alerts on top of it is
left to the calling agent / user.

> **Disclaimer.** This is an unofficial, community project. It is not affiliated
> with, endorsed by, or supported by the Imprenta Nacional de Colombia. It works
> by reading the public consultation portal's current HTML, so it may break if
> the site changes. Use it responsibly and keep request volume modest against a
> government service.

## Tools

| Tool | Description |
| --- | --- |
| `list_recent_editions` | List the most recent editions (numero, tipo, fecha). No download. |
| `download_latest_edition` | Download the newest published edition. |
| `download_edition_by_date` | Download the edition for a given day (`dd/MM/yyyy`). |
| `download_edition_by_number` | Download a specific edition by number (`53524` or `53.524`). |

Each download tool saves the PDF and returns:

```json
{
  "numero": "53.524",
  "tipo": "Ordinaria",
  "fecha": "16/06/2026",
  "path": "/Users/you/Downloads/diario-oficial/DiarioOficial_53524_2026-06-16.pdf",
  "size_bytes": 13265672
}
```

## Where PDFs are saved

In order of precedence:

1. The `output_dir` argument passed to the tool.
2. The `DIARIO_OFICIAL_DIR` environment variable.
3. Default: `~/Downloads/diario-oficial`.

## Use it (recommended: no clone)

You only need [`uv`](https://docs.astral.sh/uv/) installed. `uv` fetches the
code from git, sets up an isolated environment, and runs the server — no manual
clone or install. Add this to your MCP config:

- **Kiro:** `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (global)
- **Claude Desktop:** `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "diario-oficial": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/jkamilo81/diario-oficial-mcp",
        "diario-oficial-mcp"
      ],
      "env": {
        "DIARIO_OFICIAL_DIR": "/Users/you/Documents/diario-oficial"
      },
      "disabled": false,
      "autoApprove": ["list_recent_editions"]
    }
  }
}
```

Pin a released version by appending a tag, e.g.
`git+https://github.com/jkamilo81/diario-oficial-mcp@v0.1.0`.

Verify it runs at all:

```bash
uvx --from git+https://github.com/jkamilo81/diario-oficial-mcp diario-oficial-mcp
```

(The process starts and waits for an MCP client on stdio; press Ctrl+C to exit.)

A colleague can then ask their agent things like *"download today's Diario
Oficial"* or *"get edition 53.510"*, then read or set up alerts on the saved PDF.

## Local development

```bash
git clone https://github.com/jkamilo81/diario-oficial-mcp
cd diario-oficial-mcp
uv venv
uv pip install -e ".[dev]"
uv run diario-oficial-mcp   # run over stdio
pytest -q                   # smoke tests against the live portal
```

Config pointing at your local checkout instead of git:

```json
{
  "mcpServers": {
    "diario-oficial": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/diario-oficial-mcp", "diario-oficial-mcp"]
    }
  }
}
```

## How it works

The portal is a JSF/PrimeFaces application. Downloading an edition is a
session-bound, three-step flow handled by `client.py`:

1. `GET /diario/` — obtain the `JSESSIONID` cookie and JSF `ViewState`; the
   landing page already lists the most recent editions with per-row "Ver Diario"
   buttons.
2. `POST` the row button — returns a viewer page containing a PrimeFaces
   streamed-content URL.
3. `GET` that streamed-content URL (same session) — returns the PDF bytes.

Search by date or number is a `POST` of the search form that re-renders the
editions table with the matching row, after which the same download flow runs.

## Troubleshooting

- **No editions returned / "Could not find ... ViewState".** The portal HTML
  likely changed. The brittle parts are the PrimeFaces component ids in
  `client.py` (e.g. `dtbDiariosOficiales:*:j_idt38`). Run `pytest -q` to confirm
  and update the parsing.
- **`No edition found for date ...`.** No edition was published that day
  (weekends/holidays), or the date is not in `dd/MM/yyyy` format.
- **TLS / certificate errors.** `httpx` bundles its own CA store, so this is
  usually a network/proxy issue rather than the portal.
- **The server "hangs" when run manually.** Expected — it waits for an MCP
  client on stdio. It's meant to be launched by Kiro / Claude Desktop.

## Notes & limitations

- Depends on the portal's current HTML structure; see Troubleshooting.
- Editions are typically large scanned PDFs (10+ MB). Text extraction / OCR for
  reading or alerting is intentionally out of scope for this server.
- Be considerate with request volume against a government service.

## License

[MIT](LICENSE)
