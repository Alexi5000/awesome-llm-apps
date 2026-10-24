import ast
import asyncio
import io
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / 'awesome_agent_skills/self-improving-agent-skills/backend/app.py'


def handler(**overrides):
    tree = ast.parse(SOURCE.read_text())
    names = {'_is_safe_path', '_is_allowed_file', 'upload_skill'}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    scope = dict(io=io, os=os, zipfile=zipfile, HTTPException=HTTPException,
                 UploadFile=object, File=lambda **kw: None,
                 logger=logging.getLogger('zip-test'), MAX_UPLOAD_SIZE=10*1024*1024,
                 MAX_FILE_SIZE=1024*1024, MAX_FILE_COUNT=50, ALLOWED_EXTENSIONS={'.md','.txt'},
                 MAX_EXPANDED_SIZE=10*1024*1024, ZIP_READ_CHUNK=64*1024,
                 create_session_from_files=lambda files, names: files,
                 traceback=SimpleNamespace(format_exc=lambda: 'test'))
    scope['File'] = lambda *args, **kw: None
    scope.update(overrides)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope['upload_skill']


class Upload:
    filename = 'skill.zip'

    def __init__(self, data):
        self.data = data
        self.sizes = []

    async def read(self, size=-1):
        self.sizes.append(size)
        return self.data if size < 0 else self.data[:size]


def archive(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, body in entries:
            zf.writestr(name, body)
    return buf.getvalue()


class ZipLimits(unittest.TestCase):
    def test_oversize_member_is_not_decompressed(self):
        upload = Upload(archive([('SKILL.md', '# skill'), ('oversize.txt', b'x'*(1024*1024+1))]))
        opened = []
        original = zipfile.ZipFile.open
        def checked(zf, entry, *args, **kwargs):
            opened.append(entry.filename)
            return original(zf, entry, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'open', checked):
            result = asyncio.run(handler()(upload))
        self.assertEqual(result, {'SKILL.md': '# skill'})
        self.assertEqual(opened, ['SKILL.md'])
        self.assertEqual(upload.sizes, [10*1024*1024+1])

    def test_expanded_reads_have_hard_limit(self):
        upload = Upload(archive([('SKILL.md', '# skill')]))
        sizes = []
        original = zipfile.ZipExtFile.read
        def checked(member, size=-1):
            sizes.append(size)
            return original(member, size)
        with patch.object(zipfile.ZipExtFile, 'read', checked):
            self.assertEqual(asyncio.run(handler()(upload)), {'SKILL.md': '# skill'})
        self.assertTrue(sizes)
        self.assertTrue(all(size == 64*1024 for size in sizes))

    def test_member_count_stops_before_next_decompression(self):
        upload = Upload(archive([(f'{i}.txt', 'ok') for i in range(51)]))
        opened = []
        original = zipfile.ZipFile.open
        def checked(zf, entry, *args, **kwargs):
            opened.append(entry.filename)
            return original(zf, entry, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'open', checked):
            self.assertEqual(len(asyncio.run(handler()(upload))), 50)
        self.assertEqual(len(opened), 50)

    def test_compressed_upload_limit_fails_before_archive_parse(self):
        upload = Upload(b'x'*(10*1024*1024+2))
        with self.assertRaises(HTTPException) as error:
            asyncio.run(handler()(upload))
        self.assertEqual(error.exception.status_code, 413)
        self.assertEqual(upload.sizes, [10*1024*1024+1])

    def test_unsafe_member_stays_excluded(self):
        upload = Upload(archive([('../secret.txt','bad'), ('SKILL.md','# skill')]))
        self.assertEqual(asyncio.run(handler()(upload)), {'SKILL.md':'# skill'})

    def test_total_expanded_size_is_capped(self):
        mib = 1024*1024
        entries = [('SKILL.md', '# skill')] + [(f'{i}.txt', b'\0'*mib) for i in range(11)]
        data = archive(entries)
        self.assertLess(len(data), 10*mib)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(handler()(Upload(data)))
        self.assertEqual(error.exception.status_code, 413)

    def test_total_budget_rejects_before_decompressing_next_member(self):
        upload = Upload(archive([('SKILL.md', '# skill'), ('a.txt', b'a'*4000), ('b.txt', b'b'*4000)]))
        opened = []
        original = zipfile.ZipFile.open
        def checked(zf, entry, *args, **kwargs):
            opened.append(entry.filename)
            return original(zf, entry, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'open', checked):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(handler(MAX_EXPANDED_SIZE=6000)(upload))
        self.assertEqual(error.exception.status_code, 413)
        self.assertEqual(opened, ['SKILL.md', 'a.txt'])

    def test_normal_multi_file_skill_is_accepted(self):
        upload = Upload(archive([('skill/SKILL.md', '# skill'), ('skill/ref.md', 'r'*200_000), ('skill/a.txt', 'a')]))
        result = asyncio.run(handler()(upload))
        self.assertEqual(result, {'SKILL.md': '# skill', 'ref.md': 'r'*200_000, 'a.txt': 'a'})
