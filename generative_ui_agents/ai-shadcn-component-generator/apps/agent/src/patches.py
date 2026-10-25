"""
Patches for ag_ui_langgraph bugs. Remove once upstream fixes land.

1. prepare_stream: falsely triggers regenerate path when tool messages inflate
   checkpoint count. Falls through to normal streaming path instead.
2. get_checkpoint_before_message: raises "Message ID not found in history"
   on regenerate — returns None to skip.
"""

from ag_ui_langgraph.agent import LangGraphAgent

_original_prepare_stream = LangGraphAgent.prepare_stream
_original_get_checkpoint = LangGraphAgent.get_checkpoint_before_message


async def _patched_prepare_stream(self, input, agent_state, config):
    result = await _original_prepare_stream(self, input=input, agent_state=agent_state, config=config)
    if result is not None:
        return result
    agent_state = agent_state._replace(values={**agent_state.values, "messages": []})
    return await _original_prepare_stream(self, input=input, agent_state=agent_state, config=config)


async def _patched_get_checkpoint(self, message_id, thread_id, config=None):
    try:
        return await _original_get_checkpoint(self, message_id, thread_id, config=config)
    except ValueError:
        return None



def apply():
    """Apply all patches."""
    LangGraphAgent.prepare_stream = _patched_prepare_stream
    LangGraphAgent.get_checkpoint_before_message = _patched_get_checkpoint
