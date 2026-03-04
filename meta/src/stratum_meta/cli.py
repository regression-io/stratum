"""stratum CLI — meta-package entry point."""
from __future__ import annotations
import shutil
import subprocess
import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: stratum <command> [options]")
        print()
        print("Commands:")
        print("  install    Register MCP server with Claude Code and install @stratum/ui")
        print("  serve      Start the stratum-mcp API server and UI")
        print()
        print("Run 'stratum-mcp --help' for MCP server options.")
        return

    cmd = args[0]

    if cmd == "install":
        # 1. Register MCP server
        print("Registering stratum-mcp with Claude Code...")
        subprocess.run(["stratum-mcp", "install"], check=True)

        # 2. Install @stratum/ui via npm if available
        npm = shutil.which("npm")
        if npm:
            print("Installing @stratum/ui...")
            subprocess.run([npm, "install", "-g", "@stratum/ui"], check=True)
            print("Done. Run 'stratum serve' to start.")
        else:
            print()
            print("npm not found — skipping @stratum/ui install.")
            print("To install the UI later:")
            print("  npm install -g @stratum/ui")
            print("  stratum-ui serve")
        return

    if cmd == "serve":
        # Start API server (stratum-mcp serve) and UI (stratum-ui serve) together.
        # stratum-mcp serve runs in the foreground on :7821.
        # stratum-ui serve (npm) runs in a background subprocess on :7820.

        rest = args[1:]

        # Extract --port so we can derive the correct api_base default.
        api_port = 7821
        if "--port" in rest:
            idx = rest.index("--port")
            if idx + 1 < len(rest):
                try:
                    api_port = int(rest[idx + 1])
                except ValueError:
                    pass

        # Extract --api-base if explicitly given; strip it from rest because
        # stratum-mcp serve does not accept that flag.
        mcp_rest = list(rest)
        api_base = f"http://localhost:{api_port}"
        if "--api-base" in mcp_rest:
            idx = mcp_rest.index("--api-base")
            if idx + 1 < len(mcp_rest):
                api_base = mcp_rest[idx + 1]
                mcp_rest.pop(idx + 1)
            mcp_rest.pop(idx)

        # Resolve stratum-ui CLI (installed globally via npm)
        stratum_ui_bin = shutil.which("stratum-ui")

        ui_proc = None
        if stratum_ui_bin:
            import time
            ui_proc = subprocess.Popen(
                [stratum_ui_bin, "serve", "--api-base", api_base],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            # Brief liveness check — give the process 500ms to fail fast
            time.sleep(0.5)
            if ui_proc.poll() is not None:
                stderr_out = ui_proc.stderr.read().decode(errors="replace").strip()
                print(f"Warning: stratum-ui exited immediately (code {ui_proc.returncode}).")
                if stderr_out:
                    print(f"  {stderr_out}")
                print("  Run 'npm run build:app' inside @stratum/ui to build the standalone app.")
                ui_proc = None
            else:
                print(f"stratum-ui started (pid {ui_proc.pid}) → http://localhost:7820")
        else:
            print("stratum-ui not found — UI will not be served.")
            print("Run 'stratum install' or 'npm install -g @stratum/ui' to enable it.")

        try:
            subprocess.run(["stratum-mcp", "serve"] + mcp_rest, check=True)
        finally:
            if ui_proc and ui_proc.poll() is None:
                ui_proc.terminate()
                ui_proc.wait()
        return

    print(f"Unknown command: {cmd}", file=sys.stderr)
    print("Run 'stratum --help' for usage.", file=sys.stderr)
    sys.exit(1)
