"""stratum CLI — meta-package entry point."""
from __future__ import annotations
import subprocess
import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: stratum <command> [options]")
        print()
        print("Commands:")
        print("  install    Register MCP server with Claude Code")
        print()
        print("Run 'stratum-mcp --help' for MCP server options.")
        return

    cmd = args[0]

    if cmd == "install":
        print("Registering stratum-mcp with Claude Code...")
        subprocess.run(["stratum-mcp", "install"], check=True)
        return

    print(f"Unknown command: {cmd}", file=sys.stderr)
    print("Run 'stratum --help' for usage.", file=sys.stderr)
    sys.exit(1)
