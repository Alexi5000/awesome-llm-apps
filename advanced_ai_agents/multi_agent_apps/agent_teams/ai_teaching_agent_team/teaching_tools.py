from copy import deepcopy

from agno.tools.function import Function
from composio import Composio
from composio.core.provider import AgenticProvider
from jsonschema import validate

DOCUMENT_ACTIONS = (
    "GOOGLEDOCS_CREATE_DOCUMENT",
    "GOOGLEDOCS_UPDATE_EXISTING_DOCUMENT",
)


class TeachingAgnoProvider(AgenticProvider[Function, list[Function]], name="teaching_agno"):
    def wrap_tool(self, tool, execute_tool):
        schema = deepcopy(tool.input_parameters)

        def execute(**arguments):
            validate(arguments, schema)
            return execute_tool(tool.slug, arguments)

        return Function(
            name=tool.slug,
            description=tool.description,
            parameters=schema,
            entrypoint=execute,
            skip_entrypoint_processing=True,
        )

    def wrap_tools(self, tools, execute_tool):
        return [self.wrap_tool(tool, execute_tool) for tool in tools]


def google_docs_tools(api_key, user_id, *, http_client=None):
    if not api_key.strip():
        raise ValueError("A Composio API key is required")
    if not user_id.strip():
        raise ValueError("A connected Composio user ID is required")
    options = {"http_client": http_client} if http_client is not None else {}
    client = Composio(api_key=api_key, provider=TeachingAgnoProvider(), **options)
    tools = client.tools.get(user_id=user_id, tools=list(DOCUMENT_ACTIONS))
    if {tool.name for tool in tools} != set(DOCUMENT_ACTIONS):
        raise ValueError("Composio did not return both Google Docs tools")
    return tools
