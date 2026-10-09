"""Small real CPU MP4s, controlled Wan replies; no network or GPU."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.media import checksum
from app.production_stages import StageFailure, StageResult, execute_stage
from app.test_wan_fixture import FixtureProvider
from app.wan import collect_scenes, plan_requests, validate_scene_manifest


def context(count=1):
    return dict(mode='CLOUD',media_type='AI_GENERATED_VIDEO',project_id=str(uuid4()),run_id=str(uuid4()),
        script={'version':1,'target_duration_seconds':36}, scenes=[dict(id=str(uuid4()),position=i,
        media_type='AI_GENERATED_VIDEO',duration_seconds=6,wan_prompt='A slow camera move through a garden')
        for i in range(1,count+1)])


class WanPlanTest(unittest.TestCase):
    def test_stable_intents_and_duration_coverage(self):
        body = context(2)
        first = plan_requests(body)
        self.assertEqual(first,plan_requests(body))
        self.assertEqual([len(c) for _,_,c in first],[2,2])
        self.assertEqual(len({r.job_id for _,_,clips in first for r in clips}),4)
        body['scenes'][0]['duration_seconds']=12
        self.assertEqual(len(plan_requests(body)[0][2]),3)
        for changed in ('mode','media_type','prompt','order'):
            bad=copy.deepcopy(body)
            if changed=='mode': bad['mode']='LOKAL'
            if changed=='media_type': bad['scenes'][0]['media_type']='STOCK_VIDEO'
            if changed=='prompt': bad['scenes'][0]['wan_prompt']=' '
            if changed=='order': bad['scenes'][0]['position']=2
            with self.subTest(changed=changed),self.assertRaises(StageFailure): plan_requests(bad)

    def test_default_and_live_provider_are_blocked_before_call(self):
        with self.assertRaisesRegex(StageFailure,'gesperrt'): execute_stage('SCENES',context())
        provider=FixtureProvider('/never-read');provider.execution='WAN_INFERENCE'
        with self.assertRaises(StageFailure) as caught: collect_scenes(context(),provider)
        self.assertEqual(caught.exception.code,'WAN_LIVE_DISABLED')
        self.assertEqual(provider.calls,[])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg and ffprobe required')
class WanTransferTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory()
        cls.fixture_root=Path(cls.fixture.name)
        subprocess.run([shutil.which('ffmpeg'),'-v','error','-f','lavfi','-i',
            'color=c=blue:s=720x1280:r=16','-frames:v','81','-c:v','libx264','-preset','ultrafast',
            '-pix_fmt','yuv420p',str(cls.fixture_root/'raw.mp4')],check=True,timeout=15)

    @classmethod
    def tearDownClass(cls): cls.fixture.cleanup()

    def setUp(self):
        self.files=tempfile.TemporaryDirectory(prefix='Wan Speicher Grüße ')
        self.addCleanup(self.files.cleanup)
        self.root=Path(self.files.name)
        self.provider_root=self.root/'provider';self.provider_root.mkdir()
        shutil.copyfile(self.fixture_root/'raw.mp4',self.provider_root/'raw.mp4')
        env=patch.dict(os.environ,{'MEDIA_ROOT':str(self.root/'chosen-media'),'WORKER_CONFIG_PATH':''})
        env.start();self.addCleanup(env.stop)
        self.provider=FixtureProvider(self.provider_root)
        self.body=context()

    def test_success_reuse_and_repair_without_duplicate_jobs(self):
        result=collect_scenes(self.body,self.provider)
        validated=StageResult.model_validate(result)
        self.assertFalse(validated.sources)
        self.assertEqual(len(validated.wan_sources[0].clips),2)
        self.assertEqual(validated.wan_sources[0].duration_seconds,6)
        self.assertEqual(validated.artifacts[0].media_type,'AI_GENERATED_VIDEO')
        self.assertEqual(len(self.provider.calls),2)
        self.assertEqual(collect_scenes(self.body,self.provider),result)
        self.assertEqual(len(self.provider.calls),2)
        clip=next((self.root/'chosen-media').rglob('clip-1.mp4'));clip.write_bytes(b'corrupt')
        self.assertEqual(collect_scenes(self.body,self.provider),result)
        self.assertEqual(len(list((self.provider_root/'jobs').glob('*.json'))),2)
        self.assertEqual(checksum(self.root/'chosen-media'/validated.artifacts[0].storage_path),validated.artifacts[0].checksum_sha256)
        manifest=next((self.root/'chosen-media').rglob('manifest.json'))
        self.assertEqual(json.loads(manifest.read_text(encoding='utf-8')),result)
        self.assertFalse(list(self.root.rglob('*.part')))
        for change in ('missing','wrong-position','wrong-type','mixed'):
            altered=copy.deepcopy(result)
            if change=='missing': altered['wan_sources'][0]['clips'].pop()
            if change=='wrong-position': altered['wan_sources'][0]['scene_position']=2
            if change=='wrong-type': altered['artifacts'][0]['media_type']='STOCK_VIDEO'
            if change=='mixed': altered['wan_sources'][0]['clips'][0]['request']['seed']+=1
            with self.subTest(change=change),self.assertRaises((ValueError,StageFailure)):
                validate_scene_manifest(self.body,StageResult.model_validate(altered))

    def test_timeout_corruption_origin_and_path_rejected_without_manifest(self):
        for scenario,code in [('timeout','WAN_TRANSFER_TIMEOUT'),('corrupt','WAN_CHECKSUM_MISMATCH'),
                ('wrong-provider','WAN_RESPONSE_INVALID'),('wrong-job','WAN_RESPONSE_INVALID'),
                ('escape','WAN_RESPONSE_INVALID'),('live','WAN_RESPONSE_INVALID'),('broken-file','WAN_MEDIA_INVALID')]:
            body=context();provider=FixtureProvider(self.provider_root,scenario)
            with self.subTest(scenario=scenario),self.assertRaises(StageFailure) as caught:
                collect_scenes(body,provider)
            self.assertEqual(caught.exception.code,code)
            folder=self.root/'chosen-media/projects'/body['project_id']/'versions/1/runs'/body['run_id']/'wan'
            self.assertFalse(list(folder.rglob('manifest.json')))
            self.assertFalse(list(folder.rglob('scene.mp4')))
            self.assertFalse(list(folder.rglob('*.part')))
            if scenario=='timeout':
                provider.scenario='success';collect_scenes(body,provider)
                self.assertEqual(len({*provider.calls}),2)  # same job after unknown outcome

    def test_cancel_and_changed_intent_never_publish(self):
        def cancel(): raise StageFailure('CANCELLED','Kontrollierter Abbruch')
        with self.assertRaises(StageFailure): collect_scenes(self.body,self.provider,check_cancelled=cancel)
        self.assertFalse(self.provider.calls)
        checks=0
        def cancel_during_transfer():
            nonlocal checks
            checks+=1
            if checks==3: raise StageFailure('CANCELLED','Abbruch während Transfer')
        with self.assertRaises(StageFailure):
            collect_scenes(self.body,self.provider,check_cancelled=cancel_during_transfer)
        self.assertFalse(list((self.root/'chosen-media').rglob('*.part')))
        self.assertFalse(list((self.root/'chosen-media').rglob('manifest.json')))
        collect_scenes(self.body,self.provider)
        self.body['scenes'][0]['wan_prompt']='Changed immutable intent'
        with self.assertRaises(StageFailure) as caught: collect_scenes(self.body,self.provider)
        self.assertEqual(caught.exception.code,'WAN_JOB_CONFLICT')
        self.assertEqual(len(set(self.provider.calls)),2)

    def test_run_and_clip_deadlines_stop_late_provider_before_transfer(self):
        for setting, code in [('WAN_MAX_RUN_SECONDS', 'WAN_RUNTIME_LIMIT'),
                              ('WAN_MAX_CLIP_SECONDS', 'WAN_TRANSFER_TIMEOUT')]:
            body = context()
            clock = [0.0]
            provider = FixtureProvider(self.provider_root)
            original = provider.ensure_clip
            observed = []
            def late(request, *, timeout_seconds):
                observed.append(timeout_seconds)
                response = original(request, timeout_seconds=timeout_seconds)
                clock[0] = 2.0
                return response
            with self.subTest(setting=setting), patch.dict(os.environ, {setting: '1'}), \
                 patch('app.wan.time.monotonic', side_effect=lambda: clock[0]), \
                 patch.object(provider, 'ensure_clip', side_effect=late), \
                 patch.object(provider, 'read_clip') as transfer:
                with self.assertRaises(StageFailure) as caught: collect_scenes(body, provider)
                self.assertEqual(caught.exception.code, code)
                self.assertLessEqual(observed[0], 1)
                transfer.assert_not_called()
            folder = self.root/'chosen-media/projects'/body['project_id']/'versions/1/runs'/body['run_id']/'wan'
            self.assertFalse(list(folder.rglob('manifest.json')))
            self.assertFalse(list(folder.rglob('*.part')))
        # Slot released by both exceptions; same installation can resume.
        collect_scenes(self.body, self.provider)

    def test_model_and_gpu_failures_remain_visible_without_sources(self):
        for code in ('WAN_MODEL_UNAVAILABLE', 'WAN_GPU_UNAVAILABLE'):
            body = context()
            with self.subTest(code=code), patch.object(self.provider, 'ensure_clip',
                    side_effect=StageFailure(code, 'Kontrollierter Providerfehler')):
                with self.assertRaises(StageFailure) as caught: collect_scenes(body, self.provider)
                self.assertEqual(caught.exception.code, code)
            folder = self.root/'chosen-media/projects'/body['project_id']/'versions/1/runs'/body['run_id']/'wan'
            self.assertFalse(list(folder.rglob('manifest.json')))
            self.assertFalse(list(folder.rglob('scene.mp4')))


if __name__=='__main__': unittest.main()
