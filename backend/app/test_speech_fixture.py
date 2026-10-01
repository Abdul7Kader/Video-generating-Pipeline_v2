"""Controlled visual input and speech failures for isolated integration only."""

from unittest.mock import patch
from app import production_stages
from app.test_production_fixture import fixture_stage
from app.test_speech import ControlledVoice

real_stage = production_stages.execute_stage


def speech_fixture(name, context):
    if name == 'SCENES':
        return fixture_stage(name, context)
    scenario = context['script']['title']
    if name == 'SPEECH' and scenario in ('silent-speech', 'failed-speech', 'empty-speech'):
        voice = ControlledVoice()
        voice.silent = scenario == 'silent-speech'
        voice.failure = scenario == 'failed-speech'
        if scenario == 'empty-speech':
            context['scenes'][0]['narration'] = ' '
        with patch('app.speech.load_voice', return_value=voice):
            return real_stage(name, context)
    return real_stage(name, context)


if __name__ == '__main__':
    production_stages.execute_stage = speech_fixture
    production_stages.main()
