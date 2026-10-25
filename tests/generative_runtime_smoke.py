import importlib
import os
import socket
import sys
from pathlib import Path


def deny_network(*args, **kwargs):
    raise RuntimeError("Provider network calls are disabled in this smoke test")


socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
os.environ.update(
    OPENAI_API_KEY="test-no-live-provider",
    GOOGLE_API_KEY="test-no-live-provider",
    TAVILY_API_KEY="test-no-live-provider",
    ANTHROPIC_API_KEY="test-no-live-provider",
)
sys.path.insert(0, str(Path.cwd()))
main = importlib.import_module("main")
if hasattr(main, "app"):
    assert main.app.openapi()["paths"]
else:
    assert main.graph.get_graph().nodes
print("Offline agent construction and route/graph inspection passed")
