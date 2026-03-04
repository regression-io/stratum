"""stratum-ui Python shim — server logic has moved to stratum-mcp.

This package is deprecated. Use:
  npm install -g @stratum/ui
  stratum-ui serve
"""


def main() -> None:
    print(
        "stratum-ui has moved to npm.\n"
        "\n"
        "Install with:\n"
        "  npm install -g @stratum/ui\n"
        "\n"
        "Or run without installing:\n"
        "  npx @stratum/ui serve\n"
        "\n"
        "The API server is now part of stratum-mcp:\n"
        "  stratum-mcp serve\n"
    )


if __name__ == "__main__":
    main()
