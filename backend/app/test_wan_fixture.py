"""Local fixtures only. Never imported/selected by a production provider factory."""
import hashlib
import json
import os
from pathlib import Path
from app.wan_contract import RAW_FRAMES, RAW_FPS


class FixtureProvider:
    execution = 'CONTROLLED_TEST'

    def __init__(self, folder, scenario='success'):
        self.folder = Path(folder)
        self.scenario = scenario
        self.calls = []

    def ensure_clip(self, request, *, timeout_seconds):
        jobs = self.folder/'jobs'
        jobs.mkdir(exist_ok=True)
        path = jobs/f'{request.job_id}.json'
        payload = request.model_dump(mode='json')
        if path.exists():
            if json.loads(path.read_text(encoding='utf-8')) != payload:
                raise ValueError('same intent with changed body')
        else:
            # Atomic fixture claim; no external side effect.
            with path.open('x',encoding='utf-8') as out:
                json.dump(payload,out)
        self.calls.append(str(request.job_id))
        content = (self.folder/'raw.mp4').read_bytes()
        response = dict(request=payload,execution=self.execution,result_path=f'wan/{request.job_id}/clip.mp4',
            checksum_sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content),
            duration_seconds=RAW_FRAMES/RAW_FPS)
        if self.scenario == 'wrong-provider': response['request']['provider'] = 'PEXELS'
        if self.scenario == 'wrong-job': response['request']['seed'] += 1
        if self.scenario == 'escape': response['result_path'] = '../secret.mp4'
        if self.scenario == 'live': response['execution'] = 'WAN_INFERENCE'
        if self.scenario == 'broken-file':
            content = b'not an MP4'; response.update(checksum_sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content))
        return response

    def read_clip(self, response, *, timeout_seconds):
        content = (self.folder/'raw.mp4').read_bytes()
        if self.scenario == 'timeout':
            yield content[:20]
            raise TimeoutError('controlled transport interruption')
        if self.scenario == 'corrupt': content = bytes([content[0]^1])+content[1:]
        if self.scenario == 'broken-file': content = b'not an MP4'
        yield content


def stage(name, context):
    from app.wan import collect_scenes
    from app.production_stages import StageFailure
    if name != 'SCENES':
        raise StageFailure('TEST_STOP_AFTER_SCENES', 'Kurze Prüfung endet nach dem CLOUD-Rücktransfer.')
    scenario = os.environ.get('WAN_FIXTURE_SCENARIO',context['script']['title'])
    return collect_scenes(context, FixtureProvider(os.environ['WAN_FIXTURE_ROOT'],scenario))


if __name__ == '__main__':
    from app import production_stages
    production_stages.execute_stage = stage
    production_stages.main()
