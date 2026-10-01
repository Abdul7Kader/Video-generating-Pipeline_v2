"""Controlled visual sourcing only; actual Piper and Remotion in isolated tests."""

from app import production_stages
from app.test_production_fixture import fixture_stage

real_stage = production_stages.execute_stage


def graphics_fixture(name, context):
    if name == 'SCENES':
        return fixture_stage(name, context)
    if name == 'GRAPHICS' and context['script']['title'] == 'changed-audio':
        context['previous_results']['SPEECH']['speech'][0]['text'] = 'Unfreigegeben'
    return real_stage(name, context)


if __name__ == '__main__':
    production_stages.execute_stage = graphics_fixture
    production_stages.main()
