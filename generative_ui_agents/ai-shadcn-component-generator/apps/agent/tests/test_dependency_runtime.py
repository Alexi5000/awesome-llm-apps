import unittest
from unittest.mock import AsyncMock, patch

from ag_ui_langgraph.agent import LangGraphAgent
from langgraph.checkpoint.base import empty_checkpoint
from src.bounded_memory_saver import BoundedMemorySaver
from src import patches


class DependencyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_checkpoint_eviction_keeps_recent_threads(self):
        saver = BoundedMemorySaver(max_threads=2)
        configs = []
        for thread in range(4):
            config = {"configurable": {"thread_id": str(thread), "checkpoint_ns": ""}}
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"messages": "checkpoint payload"}
            checkpoint["channel_versions"] = {"messages": "1"}
            saved = saver.put(config, checkpoint, {}, {"messages": "1"})
            saver.put_writes(saved, [("messages", "pending payload")], "task")
            configs.append(saved)
        self.assertIsNone(saver.get_tuple(configs[0]))
        self.assertIsNone(saver.get_tuple(configs[1]))
        self.assertIsNotNone(saver.get_tuple(configs[2]))
        self.assertIsNotNone(saver.get_tuple(configs[3]))
        self.assertEqual(set(saver.storage), {"2", "3"})
        self.assertEqual({key[0] for key in saver.blobs}, {"2", "3"})
        self.assertEqual({key[0] for key in saver.writes}, {"2", "3"})

    async def test_async_checkpoint_eviction_cleans_payloads(self):
        saver = BoundedMemorySaver(max_threads=1)
        for thread in ("old", "recent"):
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"messages": "async payload"}
            checkpoint["channel_versions"] = {"messages": "1"}
            saved = await saver.aput(
                {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
                checkpoint, {}, {"messages": "1"},
            )
            await saver.aput_writes(saved, [("messages", "pending payload")], "task")
        self.assertEqual(set(saver.storage), {"recent"})
        self.assertEqual({key[0] for key in saver.blobs}, {"recent"})
        self.assertEqual({key[0] for key in saver.writes}, {"recent"})

    def test_upstream_message_tracking_preserves_parallel_lanes(self):
        patches.apply()
        agent = object.__new__(LangGraphAgent)
        agent.messages_in_process = {}
        agent.set_message_in_progress("run", {"message_id": "left"}, lane="left")
        agent.set_message_in_progress("run", {"message_id": "right"}, lane="right")
        agent.clear_message_in_progress("run", lane="left")
        agent.set_message_in_progress("run", {"message_id": "new"}, lane="left")
        self.assertEqual(agent.messages_in_process["run"]["left"]["message_id"], "new")
        self.assertEqual(agent.messages_in_process["run"]["right"]["message_id"], "right")

    async def test_checkpoint_adapter_forwards_config(self):
        config = {"configurable": {"checkpoint_ns": "branch"}}
        delegate = AsyncMock(return_value="checkpoint")
        with patch.object(patches, "_original_get_checkpoint", delegate):
            result = await patches._patched_get_checkpoint(self, "message", "thread", config)
        self.assertEqual(result, "checkpoint")
        delegate.assert_awaited_once_with(self, "message", "thread", config=config)

    async def test_missing_checkpoint_retains_regeneration_fallback(self):
        with patch.object(patches, "_original_get_checkpoint", AsyncMock(side_effect=ValueError)):
            self.assertIsNone(await patches._patched_get_checkpoint(self, "missing", "thread"))


if __name__ == "__main__":
    unittest.main()
