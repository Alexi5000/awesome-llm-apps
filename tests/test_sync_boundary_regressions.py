import ast
import asyncio
import logging
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import Mock, patch
from textwrap import dedent

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


def function(path, name, scope):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    node.args.defaults = []
    scope.update(HTTPException=HTTPException, UploadFile=object, Optional=Optional, List=List)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[name]


class UploadLimits(unittest.TestCase):
    def test_read_is_bounded_before_oversized_payload_is_rejected(self):
        cases = [
            ('rag_tutorials/multimodal_agentic_rag/backend/server.py', 'add_file_source', 120*1024*1024, {'title':'', 'notes':''}, 'file'),
            ('advanced_llm_apps/multimodal_video_moment_finder/backend/server.py', 'find_moment', 10*1024*1024, {'video_id':None, 'top_k':5}, 'image'),
        ]
        for path, name, limit, args, param in cases:
            class Large:
                def __len__(self): return limit+1
            class Upload:
                async def read(self, size):
                    self.size = size
                    return Large()
            upload = Upload()
            with self.subTest(name=name), self.assertRaises(HTTPException):
                asyncio.run(function(path, name, {})(**{param:upload}, **args))
            self.assertEqual(upload.size, limit+1)

    def test_folder_upload_caps_each_read_and_preserves_small_files(self):
        class Upload:
            filename = 'SKILL.md'
            def __init__(self, content): self.content = content
            async def read(self, size):
                self.size = size
                return self.content[:size]
        good, large = Upload(b'# valid'), Upload(b'x'*20)
        scope = dict(MAX_FILE_COUNT=50, MAX_FILE_SIZE=10, MAX_UPLOAD_SIZE=30,
                     _is_safe_path=lambda name:True, _is_allowed_file=lambda name:True,
                     logger=logging.getLogger('bounded'), os=os,
                     create_session_from_files=lambda files,names:files)
        handler = function('agent_skills/self-improving-agent-skills/backend/app.py','upload_files',scope)
        self.assertEqual(asyncio.run(handler([good,large])), {'SKILL.md':'# valid'})
        self.assertEqual((good.size,large.size),(11,11))


class GithubCredentials(unittest.TestCase):
    def test_concurrent_runs_keep_model_and_child_credentials_request_local(self):
        dispatched=[]
        class Tools:
            def __init__(self,server_params): self.params=server_params
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
        class Agent:
            def __init__(self,model,tools,**kwargs): self.model,self.tool=model,tools[0]
            async def arun(self,message):
                await asyncio.sleep(0)
                dispatched.append((self.model.api_key,self.tool.params.env))
                return SimpleNamespace(content=message)
        scope=dict(asyncio=asyncio,os=os,dedent=dedent,Agent=Agent,MCPTools=Tools,
                   StdioServerParameters=SimpleNamespace,OpenAIChat=lambda **kwargs:SimpleNamespace(**kwargs),RunOutput=object)
        run=function('mcp_ai_agents/github_mcp_agent/github_agent.py','run_github_agent',scope)
        async def interleave():
            return await asyncio.gather(run('a','openai-a','github-a'),run('b','openai-b','github-b'))
        with patch.dict(os.environ, {'OPENAI_API_KEY':'operator','GITHUB_TOKEN':'operator-gh','UNRELATED_SECRET':'secret'}):
            self.assertEqual(asyncio.run(interleave()),['a','b'])
            self.assertEqual(os.environ['OPENAI_API_KEY'],'operator')
            self.assertEqual(os.environ['GITHUB_TOKEN'],'operator-gh')
        self.assertEqual([(key,env['GITHUB_PERSONAL_ACCESS_TOKEN']) for key,env in dispatched],[('openai-a','github-a'),('openai-b','github-b')])
        self.assertTrue(all('UNRELATED_SECRET' not in env and 'OPENAI_API_KEY' not in env for _,env in dispatched))
