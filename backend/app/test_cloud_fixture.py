"""Explicit test subprocess: controlled Wan transfer, real CPU adapters.

Never imported or selected by the normal worker or a production environment flag.
"""
import os

from app import production_stages
from app.test_wan_fixture import FixtureProvider
from app.wan import collect_scenes

real_stage = production_stages.execute_stage


def cloud_fixture(name, context):
    if context.get('mode') != 'CLOUD':
        raise production_stages.StageFailure('MODE_MISMATCH', 'Testadapter akzeptiert nur CLOUD.')
    if name == 'SCENES':
        return collect_scenes(context, FixtureProvider(os.environ['WAN_FIXTURE_ROOT']))
    return real_stage(name, context)


if __name__ == '__main__':
    production_stages.execute_stage = cloud_fixture
    production_stages.main()
