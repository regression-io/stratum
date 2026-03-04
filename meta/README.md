# stratum

Meta-package. Installs the full Stratum stack in one command:

```bash
pip install stratum
stratum install   # register MCP + install UI
stratum serve     # start API server + UI on :7821
```

Components:
- [`stratum-py`](https://pypi.org/project/stratum-py/) — Python library (`@pipeline`, `@phase`, `stratum.run()`)
- [`stratum-mcp`](https://pypi.org/project/stratum-mcp/) — MCP server for Claude Code
