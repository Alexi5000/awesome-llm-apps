from typing import Iterator
from agno.agent import Agent
from agno.run.agent import RunOutput, RunEvent
from agno.models.openai import OpenAIChat
from agno.utils.pprint import pprint_run_response
from dotenv import load_dotenv

load_dotenv()
agent = Agent(model=OpenAIChat(id="gpt-4o-mini"))
response: RunOutput = agent.run("Tell me a 5 second short story about a robot")
response_stream: Iterator[RunEvent] = agent.run("Tell me a 5 second short story about a lion", stream=True)
pprint_run_response(response, markdown=True)
pprint_run_response(response_stream, markdown=True)
