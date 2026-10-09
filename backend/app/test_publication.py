import unittest
from app.publication_contract import Metadata,ReleaseInput,profile,digest,source_provenance
from uuid import uuid4


class PublicationFunctionsTest(unittest.TestCase):
    def test_profiles_keep_sources_and_force_cloud_disclosure(self):
        metadata=Metadata(title='Garten',made_for_kids=False,targets={'youtube':{'visibility':'private'},'tiktok':{'visibility':'SELF_ONLY'}})
        yt=profile('youtube',metadata,'Pexels: Author https://www.pexels.com/video/1/','CLOUD')
        self.assertTrue(yt['status']['containsSyntheticMedia'])
        self.assertIn('Pexels:',yt['snippet']['description'])
        self.assertEqual(yt['snippet']['categoryId'],'22')
        self.assertTrue(profile('tiktok',metadata,'','CLOUD')['post_info']['is_aigc'])
        self.assertFalse(profile('youtube',metadata,'','LOKAL')['status']['containsSyntheticMedia'])

    def test_invalid_profile_and_utf16_limit_fail(self):
        data=dict(title='😀'*100,description='😀'*1100,made_for_kids=False,targets={'tiktok':{'visibility':'SELF_ONLY'}})
        with self.assertRaises(ValueError): profile('tiktok',Metadata(**data),'','LOKAL')
        metadata=Metadata(title='Ad',made_for_kids=False,paid_partnership=True,targets={'tiktok':{'visibility':'SELF_ONLY'}})
        with self.assertRaises(ValueError): profile('tiktok',metadata,'','LOKAL')
        with self.assertRaises(ValueError): Metadata(title='  ',made_for_kids=False)
        with self.assertRaises(ValueError): Metadata(title='<script>',made_for_kids=False)

    def test_review_confirmation_is_explicit_and_digest_covers_all_metadata(self):
        value=dict(expected_revision=1,checksum_sha256='a'*64,reviewed_metadata=True,reviewed_sources=True,consent_to_publish=True)
        for invalid in (False,1,'true'):
            with self.assertRaises(ValueError): ReleaseInput(**{**value,'consent_to_publish':invalid})
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        self.assertNotEqual(digest(value),digest({**value,'checksum_sha256':'b'*64}))

    def test_cloud_provenance_rejects_missing_mixed_and_wrong_scenes_and_marks_test_clips(self):
        clip=dict(request=dict(job_id=str(uuid4()),scene_position=1,clip_index=1,models_lock_sha256='a'*64,prompt='Controlled fixture',seed=1),
            execution='CONTROLLED_TEST',result_path='clip.mp4',checksum_sha256='b'*64,size_bytes=100,duration_seconds=5.0625)
        source=dict(scene_position=1,artifact_key='scene_1',scene_duration_seconds=5,duration_seconds=5,clips=[clip])
        value={'wan_sources':[source]}
        self.assertTrue(source_provenance('CLOUD',[1],value)['controlled_test'])
        for bad in ({},{**value,'sources':[{}]},{'wan_sources':[{**source,'scene_position':2}]}):
            with self.assertRaises(ValueError): source_provenance('CLOUD',[1],bad)
