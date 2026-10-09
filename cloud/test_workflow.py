import copy
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from cloud import validate
from cloud.modal_app import generate_clip


class CloudPreparationTest(unittest.TestCase):
    def test_no_live_entrypoint_or_local_wan_installation(self):
        root = validate.ROOT.parent
        tree = ast.parse((validate.ROOT/'modal_app.py').read_text(encoding='utf-8'))
        calls = [n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse({'remote','spawn','deploy','run','local_entrypoint'} & set(calls))
        for filename in ('compose.yaml','compose.host-worker.yaml','backend/requirements.txt','backend/requirements-worker.txt'):
            text = (root/filename).read_text(encoding='utf-8').lower()
            self.assertNotIn('comfyui',text)
            self.assertNotIn('torch',text)
            self.assertNotIn('nvidia',text)

    def test_bundle_is_pinned_without_execution(self):
        result = validate.validate_bundle()
        self.assertEqual((result['gpu'], result['nodes'], result['model_files']), ('A100-80GB',14,4))
        self.assertFalse(result['live_enabled'])
        self.assertEqual(result['model_bytes'], 35577569479)
        with self.assertRaisesRegex(RuntimeError, 'disabled'):
            generate_clip()

    def test_prompt_and_seed_do_not_mutate_template(self):
        original = validate.load('wan-api.json')
        identity = uuid4()
        prompt = 'A camera moves through a garden. " $(echo no-shell)'
        first = validate.prepare_workflow(prompt, 2**64-1, identity)
        second = validate.prepare_workflow('Different scene', 12, uuid4())
        self.assertEqual(first['5']['inputs']['text'], prompt)
        self.assertEqual(first['10']['inputs']['noise_seed'], 2**64-1)
        self.assertEqual(first['14']['inputs']['filename_prefix'], f'wan/{identity}/clip')
        self.assertNotEqual(first['5'], second['5'])
        self.assertEqual(validate.load('wan-api.json'), original)

    def test_invalid_requests_fail_locally(self):
        for prompt, seed, identity in [('',0,uuid4()),('a'*2001,0,uuid4()),('x',True,uuid4()),
                                       ('x',-1,uuid4()),('x',2**64,uuid4()),('x',0,'../../file')]:
            with self.subTest(prompt_length=len(prompt), seed=seed), self.assertRaises(ValueError):
                validate.prepare_workflow(prompt, seed, identity)

    def test_bad_graphs_are_rejected(self):
        original = validate.load('wan-api.json')
        contracts = validate.load('node-contracts.json')['nodes']
        models = validate.load('models.lock.json')['files']
        modifications = [
            ('12','samples',['10',0]),  # decode must use completed low-noise output
            ('11','latent_image',['7',0]),
            ('10','end_at_step',20),
            ('11','add_noise','enable'),
            ('12','vae',['1',0]),  # MODEL cannot feed VAE
            ('5','clip',['3',9]),
            ('8','model',['8',0]),  # cycle
            ('7','length',82),
            ('14','format.codec','av1'),
            ('1','unet_name','wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors'),
        ]
        for identity, field, value in modifications:
            graph = copy.deepcopy(original); graph[identity]['inputs'][field] = value
            with self.subTest(node=identity, field=field), self.assertRaises(ValueError):
                validate.validate_graph(graph, contracts, models)
        graph = copy.deepcopy(original); graph['1']['class_type'] = 'PaidExternalAPI'
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            validate.validate_graph(graph, contracts, models)

    def test_changed_bundle_and_unsafe_deployment_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in validate.load('bundle.lock.json')['files_sha256']:
                shutil.copyfile(validate.ROOT/name, root/name)
            shutil.copyfile(validate.ROOT/'bundle.lock.json', root/'bundle.lock.json')
            (root/'wan-api.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Changed bundle'):
                validate.validate_bundle(root)
            shutil.copyfile(validate.ROOT/'wan-api.json', root/'wan-api.json')
            spec = validate.load('deployment.json',root); spec['gpu'] = 'A100'
            (root/'deployment.json').write_text(json.dumps(spec))
            lock = validate.load('bundle.lock.json',root)
            lock['files_sha256']['deployment.json'] = hashlib.sha256((root/'deployment.json').read_bytes()).hexdigest()
            (root/'bundle.lock.json').write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError, 'GPU'):
                validate.validate_bundle(root)

    def test_missing_resource_caps_and_startup_limits_fail_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = validate.load('deployment.json')
            for name in validate.load('bundle.lock.json')['files_sha256']:
                shutil.copyfile(validate.ROOT/name, root/name)
            for field, value in [('cpu_limit', None), ('cpu_limit', 8),
                                 ('memory_limit_mib', None), ('memory_limit_mib', 131072),
                                 ('startup_timeout_seconds', 1800), ('scaledown_window_seconds', 60)]:
                spec = copy.deepcopy(original)
                if value is None: spec.pop(field)
                else: spec[field] = value
                (root/'deployment.json').write_text(json.dumps(spec))
                lock = validate.load('bundle.lock.json')
                lock['files_sha256']['deployment.json'] = hashlib.sha256((root/'deployment.json').read_bytes()).hexdigest()
                (root/'bundle.lock.json').write_text(json.dumps(lock))
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'resource'):
                    validate.validate_bundle(root)

    def test_sdk_preview_passes_both_resource_limits_and_separate_startup_timeout(self):
        import sys
        from unittest.mock import MagicMock
        from cloud.modal_app import deployment_preview
        sdk = MagicMock()
        with patch.dict(sys.modules, {'modal': sdk}), patch('importlib.metadata.version', return_value='1.6.1'):
            deployment_preview()
        kwargs = sdk.App.return_value.function.call_args.kwargs
        self.assertEqual(kwargs['cpu'], (4, 4))
        self.assertEqual(kwargs['memory'], (65536, 65536))
        self.assertEqual(kwargs['startup_timeout'], 300)
        self.assertEqual(kwargs['timeout'], 1800)
        self.assertEqual(kwargs['retries'], 0)

    def test_volume_hash_verification_never_downloads_or_accepts_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'vae').mkdir()
            path = root/'vae/model.safetensors'; path.write_bytes(b'controlled-weight')
            record = dict(target_path='vae/model.safetensors',size_bytes=path.stat().st_size,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with patch.object(validate,'validate_bundle'), patch.object(validate,'load',return_value={'files':[record]}):
                validate.verify_model_files(root)
                path.write_bytes(b'changed-weightxxx')
                with self.assertRaises(ValueError): validate.verify_model_files(root)
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing'): validate.verify_model_files(root)
                record['target_path'] = '../outside.safetensors'
                with self.assertRaisesRegex(ValueError, 'unsafe'): validate.verify_model_files(root)


if __name__ == '__main__':
    unittest.main()
