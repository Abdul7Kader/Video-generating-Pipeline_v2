"""Deployment definition for offline SDK inspection; no global deployable app yet.

No call/run/deploy entry point: live activation requires steps 21–24 and verified
credits plus an effective zero net spend limit before any GPU allocation.
Sources: https://modal.com/docs/guide/images, /guide/gpu, /guide/scale.
"""
from pathlib import Path
from cloud.validate import load, validate_bundle


def generate_clip():
    raise RuntimeError('CLOUD live execution is disabled until steps 21–24 and cost verification.')


def deployment_preview():
    """Construct lazy SDK definitions locally; never deploy or execute them."""
    validate_bundle()
    import modal
    from importlib.metadata import version
    if version('modal') != '1.6.1':
        raise RuntimeError('Use the pinned cloud/requirements-sdk.txt for inspection.')
    root = Path(__file__).resolve().parent
    spec = load('deployment.json')
    commit = load('bundle.lock.json')['comfy_commit']
    image = (modal.Image.debian_slim(python_version=spec['python_version'])
             .apt_install('git', 'ffmpeg', 'libgl1', 'libglib2.0-0')
             .pip_install_from_requirements(str(root/'requirements-linux.lock'),
                                           extra_index_url='https://download.pytorch.org/whl/cu128',
                                           extra_options='--require-hashes --no-deps --only-binary=:all:')
             .run_commands('git init /opt/ComfyUI',
                           'git -C /opt/ComfyUI remote add origin https://github.com/Comfy-Org/ComfyUI.git',
                           f'git -C /opt/ComfyUI fetch --depth 1 origin {commit}',
                           f'git -C /opt/ComfyUI checkout --detach {commit}')
             .env({'PYTHONPATH':'/opt/pipeline'})
             .add_local_dir(str(root), remote_path='/opt/pipeline/cloud'))
    models = modal.Volume.from_name(spec['models_volume'], create_if_missing=False).with_mount_options(read_only=True)
    results = modal.Volume.from_name(spec['results_volume'], create_if_missing=False)
    app = modal.App(spec['app_name'])
    app.function(image=image, gpu=spec['gpu'], cpu=(spec['cpu'], spec['cpu_limit']),
                  memory=(spec['memory_mib'], spec['memory_limit_mib']),
                  startup_timeout=spec['startup_timeout_seconds'],
                  timeout=spec['timeout_seconds'], retries=spec['retries'],
                  max_containers=spec['max_containers'], min_containers=spec['min_containers'],
                  buffer_containers=spec['buffer_containers'], scaledown_window=spec['scaledown_window_seconds'],
                  volumes={spec['models_mount']:models, spec['results_mount']:results},
                  name=spec['function_name'])(generate_clip)
    return app
