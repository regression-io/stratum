# stratum-ui

Local HTTP server for monitoring Stratum pipeline runs and approving gate-blocked phases.

## What it does

`stratum-ui` reads from the `.stratum/runs/` workspace written by the Python library and exposes it as a JSON API. It does not communicate with Claude Code or the MCP server — it shares the same file-based data layer.

**T6-2 (monitor view)** and **T6-3 (gate queue UI)** will layer a browser UI on top of these endpoints. The scaffold ships the API only.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Health check and bound project directory |
| `GET` | `/api/runs` | All pipeline runs, newest first |
| `GET` | `/api/runs/{run_id}` | Single run with per-phase detail |
| `GET` | `/api/gates` | All pending gate requests across all runs |
| `POST` | `/api/gates/{run_id}/{phase}/approve` | Approve a pending gate |
| `POST` | `/api/gates/{run_id}/{phase}/reject` | Reject a pending gate |

## Usage

```bash
pip install stratum-ui

# Start the server bound to the current project
stratum-ui serve

# Specify a project directory and port
stratum-ui serve --project-dir ~/myapp --port 8000
```

Default port: **7821**. Binds to `127.0.0.1` only.

## Gate approval

When a pipeline phase has `policy=GATE`, `run_pipeline()` writes a `.gate` file and blocks. Approve or reject it:

```bash
curl -X POST http://localhost:7821/api/gates/{run_id}/{phase}/approve
curl -X POST http://localhost:7821/api/gates/{run_id}/{phase}/reject?note=not+ready
```

The server writes `.gate.approved` or `.gate.rejected`, which unblocks the pipeline.

## Requirements

- Python 3.11+
- FastAPI ≥ 0.110
- uvicorn ≥ 0.27

## License

Apache 2.0
