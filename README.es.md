# Diario Oficial MCP

🌐 [English](README.md) | **Español**

Un servidor [MCP](https://modelcontextprotocol.io) que obtiene el PDF diario del
**Diario Oficial** de Colombia desde el portal público de consulta de la
Imprenta Nacional (`https://svrpubindc.imprenta.gov.co/diario/`).

La función del servidor es la obtención del documento: descarga el PDF oficial y
devuelve la ruta del archivo junto con sus metadatos. La lectura del documento o
la creación de alertas sobre su contenido quedan a cargo del agente o usuario
que lo invoque.

> **Aviso.** Este es un proyecto comunitario no oficial. No está afiliado,
> avalado ni respaldado por la Imprenta Nacional de Colombia. Funciona leyendo el
> HTML actual del portal público de consulta, por lo que puede dejar de
> funcionar si el sitio cambia. Úselo de forma responsable y mantenga un volumen
> de solicitudes moderado hacia un servicio del Estado.

## Herramientas

| Herramienta | Descripción |
| --- | --- |
| `list_recent_editions` | Lista las ediciones más recientes (numero, tipo, fecha). Sin descarga. |
| `download_latest_edition` | Descarga la edición publicada más reciente. |
| `download_edition_by_date` | Descarga la edición de un día determinado (`dd/MM/yyyy`). |
| `download_edition_by_number` | Descarga una edición específica por su número (`53524` o `53.524`). |

Cada herramienta de descarga guarda el PDF y devuelve:

```json
{
  "numero": "53.524",
  "tipo": "Ordinaria",
  "fecha": "16/06/2026",
  "path": "/Users/usuario/Downloads/diario-oficial/DiarioOficial_53524_2026-06-16.pdf",
  "size_bytes": 13265672
}
```

## Dónde se guardan los PDF

En orden de prioridad:

1. El argumento `output_dir` que se pasa a la herramienta.
2. La variable de entorno `DIARIO_OFICIAL_DIR`.
3. Por defecto: `~/Downloads/diario-oficial`.

## Uso (recomendado: sin clonar)

Solo necesita tener instalado [`uv`](https://docs.astral.sh/uv/). `uv` descarga
el código desde git, prepara un entorno aislado y ejecuta el servidor — sin
clonar ni instalar manualmente. Agregue esto a su configuración de MCP:

- **Kiro:** `.kiro/settings/mcp.json` (espacio de trabajo) o `~/.kiro/settings/mcp.json` (global)
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
        "DIARIO_OFICIAL_DIR": "/Users/usuario/Documents/diario-oficial"
      },
      "disabled": false,
      "autoApprove": ["list_recent_editions"]
    }
  }
}
```

Para fijar una versión publicada, agregue una etiqueta (tag), por ejemplo
`git+https://github.com/jkamilo81/diario-oficial-mcp@v0.1.0`.

Para verificar que arranca:

```bash
uvx --from git+https://github.com/jkamilo81/diario-oficial-mcp diario-oficial-mcp
```

(El proceso inicia y queda esperando a un cliente MCP por stdio; presione Ctrl+C
para salir.)

Luego, un colega puede pedirle a su agente cosas como *"descarga el Diario
Oficial de hoy"* o *"obtén la edición 53.510"*, y después leer o configurar
alertas sobre el PDF guardado.

## Desarrollo local

```bash
git clone https://github.com/jkamilo81/diario-oficial-mcp
cd diario-oficial-mcp
uv venv
uv pip install -e ".[dev]"
uv run diario-oficial-mcp   # ejecuta por stdio
pytest -q                   # pruebas de humo contra el portal en vivo
```

Configuración apuntando a su copia local en lugar de git:

```json
{
  "mcpServers": {
    "diario-oficial": {
      "command": "uv",
      "args": ["run", "--directory", "/ruta/absoluta/a/diario-oficial-mcp", "diario-oficial-mcp"]
    }
  }
}
```

## Cómo funciona

El portal es una aplicación JSF/PrimeFaces. Descargar una edición es un flujo de
tres pasos ligado a la sesión, gestionado por `client.py`:

1. `GET /diario/` — obtiene la cookie `JSESSIONID` y el `ViewState` de JSF; la
   página inicial ya lista las ediciones más recientes con un botón "Ver Diario"
   por fila.
2. `POST` del botón de la fila — devuelve una página de visor que contiene una
   URL de contenido transmitido (streamed content) de PrimeFaces.
3. `GET` de esa URL de contenido transmitido (en la misma sesión) — devuelve los
   bytes del PDF.

La búsqueda por fecha o número es un `POST` del formulario de búsqueda que vuelve
a renderizar la tabla de ediciones con la fila correspondiente, tras lo cual se
ejecuta el mismo flujo de descarga.

## Solución de problemas

- **No se devuelven ediciones / "Could not find ... ViewState".** Probablemente
  cambió el HTML del portal. Las partes frágiles son los identificadores de
  componentes PrimeFaces en `client.py` (p. ej. `dtbDiariosOficiales:*:j_idt38`).
  Ejecute `pytest -q` para confirmar y actualice el análisis (parsing).
- **`No edition found for date ...`.** No se publicó edición ese día (fines de
  semana/festivos), o la fecha no está en formato `dd/MM/yyyy`.
- **Errores de TLS / certificados.** `httpx` incluye su propio almacén de CA, así
  que suele ser un problema de red/proxy y no del portal.
- **El servidor "se queda colgado" al ejecutarlo manualmente.** Es lo esperado:
  espera a un cliente MCP por stdio. Está pensado para ser lanzado por Kiro /
  Claude Desktop.

## Notas y limitaciones

- Depende de la estructura HTML actual del portal; vea Solución de problemas.
- Las ediciones suelen ser PDF escaneados de gran tamaño (más de 10 MB). La
  extracción de texto / OCR para lectura o alertas queda intencionalmente fuera
  del alcance de este servidor.
- Sea considerado con el volumen de solicitudes hacia un servicio del Estado.

## Licencia

[MIT](LICENSE)
