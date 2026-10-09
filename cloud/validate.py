"""Offline checks only: no SDK, network, model download or inference."""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from uuid import UUID

ROOT = Path(__file__).resolve().parent


def load(name, root=ROOT):
    return json.loads((root / name).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_graph(graph, contracts, models):
    require(set(graph) == {str(i) for i in range(1, 15)}, 'Unexpected workflow nodes')
    edges = {key: [] for key in graph}
    for identity, node in graph.items():
        require(node['class_type'] in contracts, 'Unknown or custom node')
        schema = contracts[node['class_type']]
        inputs = node['inputs']
        require(set(inputs) <= set(schema['inputs']), 'Unknown node input')
        require(all(key in inputs for key, field in schema['inputs'].items() if field['required']), 'Missing node input')
        for key, value in inputs.items():
            kind = schema['inputs'][key]['type']
            if isinstance(value, list):
                require(len(value) == 2 and value[0] in graph and type(value[1]) is int, 'Invalid node link')
                upstream = contracts[graph[value[0]]['class_type']]['outputs']
                require(0 <= value[1] < len(upstream) and upstream[value[1]] == kind, 'Wrong link type or output port')
                edges[identity].append(value[0])
            else:
                valid = (kind in ('STRING', 'COMBO') and isinstance(value, str)
                         or kind == 'INT' and type(value) is int
                         or kind == 'FLOAT' and type(value) in (int, float))
                require(valid, 'Wrong literal input type')
    active, visited = set(), set()
    def visit(identity):
        require(identity not in active, 'Workflow cycle')
        if identity in visited:
            return
        active.add(identity)
        for upstream in edges[identity]:
            visit(upstream)
        active.remove(identity)
        visited.add(identity)
    visit('14')
    require(visited == set(graph), 'Disconnected workflow nodes')
    filenames = {PurePosixPath(item['target_path']).name for item in models}
    loaded = [graph[i]['inputs'][field] for i, field in [('1','unet_name'),('2','unet_name'),('3','clip_name'),('4','vae_name')]]
    require(set(loaded) == filenames and len(filenames) == 4, 'Model names do not match pinned weights')
    require('high_noise' in loaded[0] and 'low_noise' in loaded[1], 'Swapped diffusion models')
    require(graph['3']['inputs']['type'] == 'wan', 'Wrong text encoder type')
    require(graph['7']['inputs'] == dict(width=720,height=1280,length=81,batch_size=1), 'Unexpected latent profile')
    high, low = graph['10']['inputs'], graph['11']['inputs']
    require(high['model'] == ['8',0] and graph['8']['inputs']['model'] == ['1',0]
            and low['model'] == ['9',0] and graph['9']['inputs']['model'] == ['2',0], 'Wrong noise-stage models')
    require(high['latent_image'] == ['7',0] and low['latent_image'] == ['10',0]
            and graph['12']['inputs']['samples'] == ['11',0], 'Broken high/low noise handoff')
    require(high['add_noise'] == 'enable' and low['add_noise'] == 'disable'
            and high['return_with_leftover_noise'] == 'enable' and low['return_with_leftover_noise'] == 'disable'
            and high['steps'] == low['steps'] == 20 and high['start_at_step'] == 0
            and high['end_at_step'] == low['start_at_step'] == 10 and low['end_at_step'] == 20, 'Wrong sampling split')
    require(graph['13']['inputs']['fps'] == 16 and graph['14']['inputs']['format'] == 'mp4'
            and graph['14']['inputs']['format.codec'] == 'h264', 'Wrong raw video profile')


def validate_bundle(root=ROOT):
    lock = load('bundle.lock.json', root)
    for name, digest in lock['files_sha256'].items():
        require(Path(name).name == name, 'Invalid bundle path')
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, f'Changed bundle file: {name}')
    require(re.fullmatch(r'[0-9a-f]{40}', lock['comfy_commit']), 'Unpinned ComfyUI')
    models = load('models.lock.json', root)['files']
    require(len(models) == 4, 'Wrong model count')
    for model in models:
        path = PurePosixPath(model['target_path'])
        require(not path.is_absolute() and len(path.parts) == 2 and '..' not in path.parts
                and path.parts[0] in ('diffusion_models','text_encoders','vae'), 'Unsafe model path')
        require(re.fullmatch(r'[0-9a-f]{40}', model['revision']) and re.fullmatch(r'[0-9a-f]{64}', model['sha256'])
                and model['size_bytes'] > 0, 'Unpinned model')
    schemas = load('node-contracts.json', root)
    require(schemas['comfy_commit'] == lock['comfy_commit'], 'Wrong node contract version')
    validate_graph(load('wan-api.json', root), schemas['nodes'], models)
    deploy = load('deployment.json', root)
    require(deploy['gpu'] == 'A100-80GB' and deploy['max_containers'] == 1, 'Wrong GPU or concurrency')
    require(deploy['min_containers'] == deploy['buffer_containers'] == deploy['retries'] == 0
            and deploy['timeout_seconds'] == 1800 and deploy['live_enabled'] is False, 'Unsafe deployment defaults')
    require(deploy.get('cpu_limit') == deploy['cpu'] == 4
            and deploy.get('memory_limit_mib') == deploy['memory_mib'] == 65536
            and deploy.get('startup_timeout_seconds') == 300
            and deploy['scaledown_window_seconds'] == 2, 'Unsafe resource or startup limits')
    require(deploy['models_volume'] != deploy['results_volume'] and deploy['comfy_listen'] == '127.0.0.1', 'Unsafe storage or server binding')
    return dict(workflow=lock['workflow_version'], nodes=14, model_files=4,
                model_bytes=sum(m['size_bytes'] for m in models), gpu=deploy['gpu'], live_enabled=False)


def prepare_workflow(prompt, seed, clip_id):
    validate_bundle()
    require(isinstance(prompt, str) and 1 <= len(prompt.strip()) <= 2000, 'Invalid Wan prompt')
    require(type(seed) is int and 0 <= seed <= 2**64-1, 'Invalid seed')
    identity = str(UUID(str(clip_id)))
    graph = copy.deepcopy(load('wan-api.json'))
    graph['5']['inputs']['text'] = prompt.strip()
    for key in ('10','11'):
        graph[key]['inputs']['noise_seed'] = seed
    graph['14']['inputs']['filename_prefix'] = f'wan/{identity}/clip'
    return graph


def verify_model_files(directory):
    """Verify an existing volume snapshot, never download missing weights."""
    root = Path(directory).resolve()
    validate_bundle()
    for model in load('models.lock.json')['files']:
        path = (root / model['target_path']).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'Missing or unsafe model file')
        require(path.stat().st_size == model['size_bytes'], 'Wrong model size')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024*1024):
                digest.update(block)
        require(digest.hexdigest() == model['sha256'], 'Wrong model checksum')


if __name__ == '__main__':
    print(json.dumps(validate_bundle(), indent=2))
