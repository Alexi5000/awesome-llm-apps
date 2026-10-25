from mcp.server import MCPServer

server = MCPServer("compatibility-fixture")


@server.tool()
def echo(value: str) -> str:
    return f"received:{value}"


@server.tool()
def deliberate_error() -> str:
    raise ValueError("expected fixture failure")


if __name__ == "__main__":
    server.run(transport="stdio")
