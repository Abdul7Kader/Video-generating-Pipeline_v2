import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from app.storage_settings import MARKER, chosen_path, copy_store, initialize_store, activate_store
from app.production_stages import StageFailure


class StorageSettingsTest(unittest.TestCase):
    def test_environment_only_installation_creates_private_config_and_reads_changes(self):
        from app.media import media_root
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve(); config=root/'private'/'worker.json'
            with patch.dict('os.environ',{'WORKER_CONFIG_PATH':str(config),'MEDIA_ROOT':str(root/'media')}):
                identity=initialize_store()
                self.assertEqual(json.loads(config.read_text(encoding='utf-8'))['MEDIA_STORE_ID'],identity)
                self.assertTrue((root/'media'/MARKER).exists())
                copy_store(root/'media',root/'new',identity,lambda *_:None)
                activate_store(root/'new',identity)
                self.assertEqual(media_root(),root/'new')

    def test_copy_verify_resume_and_original_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve(); source=root/'alt Grüße'; target=root/'neu mit Leerzeichen'
            source.mkdir(); identity=str(uuid4())
            (source/MARKER).write_text(json.dumps({'store_id':identity}))
            (source/'master.mp4').write_bytes(b'controlled media bytes'*10000)
            progress=[]
            copy_store(source,target,identity,lambda total,done:progress.append((total,done)))
            self.assertEqual((source/'master.mp4').read_bytes(),(target/'master.mp4').read_bytes())
            self.assertEqual(progress[-1][0],progress[-1][1])
            before=(target/'master.mp4').stat().st_mtime_ns
            copy_store(source,target,identity,lambda *_:None)
            self.assertEqual((target/'master.mp4').stat().st_mtime_ns,before)
            self.assertTrue((source/'master.mp4').exists())

    def test_nested_foreign_conflicting_and_relative_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve(); source=root/'old'; target=root/'new'; source.mkdir(); target.mkdir()
            identity=str(uuid4()); (source/MARKER).write_text(json.dumps({'store_id':identity}))
            (source/'master.mp4').write_bytes(b'good'); (target/'foreign.txt').write_text('keep')
            for path in (source/'inside', source.parent, target):
                with self.assertRaises(StageFailure): copy_store(source,path,identity,lambda *_:None)
            self.assertEqual((target/'foreign.txt').read_text(),'keep')
            with self.assertRaises(StageFailure): chosen_path('relative/path')
            with self.assertRaises(StageFailure): chosen_path(str(root.anchor))
            (target/MARKER).write_text(json.dumps({'store_id':identity})); (target/'master.mp4').write_bytes(b'conflict')
            with self.assertRaises(StageFailure): copy_store(source,target,identity,lambda *_:None)
            self.assertEqual((target/'master.mp4').read_bytes(),b'conflict')
