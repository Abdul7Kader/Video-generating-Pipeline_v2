"""Controlled test processes only; never selected by the production worker."""

import hashlib
import os
from pathlib import Path
import sys
import time

from app import production_stages


def fixture_stage(name, context):
    scenario = context['script']['title']
    if name == 'SPEECH':
        if scenario in ('interrupt', 'timeout') and context['attempt'] == 1:
            time.sleep(60)
        if scenario == 'transient' and context['attempt'] == 1:
            raise production_stages.StageFailure('TEST_TRANSIENT', 'Kontrollierter vorübergehender Testfehler.', True)
        if scenario == 'persistent':
            raise production_stages.StageFailure('TEST_TRANSIENT', 'Kontrollierter wiederholter Testfehler.', True)
        if scenario == 'ui-resume' and context['attempt'] == 1:
            raise production_stages.StageFailure('TEST_RETRY_REQUIRED', 'Kontrollierte Unterbrechung für die Browser-Wiederaufnahme.')
    relative = f"{context['project_id']}/{context['run_id']}/{name.lower()}.fixture"
    if name == 'STORAGE':
        relative = f"projects/{context['project_id']}/versions/{context['script']['version']}/runs/{context['run_id']}/storage/master.mp4"
    root = Path(os.environ['TEST_ARTIFACT_ROOT'])
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"controlled fixture: {name}, {context['step_id']}".encode()
    # Stable step/key output, atomically replaced, never another copy on retry.
    pending = target.with_suffix('.partial')
    pending.write_bytes(content)
    pending.replace(target)
    artifact = dict(key=name.lower(), kind='SOURCE' if name == 'SCENES' else 'FINAL' if name == 'STORAGE' else 'INTERMEDIATE',
                    media_type=context['media_type'] if name == 'SCENES' else 'FINAL_VIDEO',
                    storage_path=relative, checksum_sha256=hashlib.sha256(content).hexdigest())
    if scenario == 'mixed' and name == 'SCENES':
        artifact['media_type'] = 'AI_GENERATED_VIDEO' if context['mode'] == 'LOKAL' else 'STOCK_VIDEO'
    result = {'artifacts': [artifact]}
    if name == 'STORAGE':
        artifact['key'] = 'master_video'
        result['storage'] = dict(project_id=context['project_id'], run_id=context['run_id'],
            script_version=context['script']['version'], manifest_path=relative.replace('master.mp4','manifest.json'),
            manifest_sha256='a'*64)
    return result


def worker_main(queue_name, burst=False, idle_seconds=30):
    from redis import Redis
    from rq import Queue
    from app import production_jobs
    from app.test_script_generation import ControlledWorker
    from app.worker import RedisReconnectMixin
    class FixtureWorker(RedisReconnectMixin, ControlledWorker):
        pass
    production_jobs.stage_command = lambda: [sys.executable, '-m', 'app.test_production_fixture', 'stage']
    connection = Redis.from_url(os.environ['REDIS_URL'])
    worker = FixtureWorker([Queue(queue_name, connection=connection)], connection=connection)
    worker.production_recovery_enabled = True
    worker.worker_ttl = 20
    worker.work(burst=burst, max_idle_time=idle_seconds, logging_level='WARNING')


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        worker_main(sys.argv[2], burst='burst' in sys.argv[3:])
    else:
        production_stages.execute_stage = fixture_stage
        production_stages.main()
