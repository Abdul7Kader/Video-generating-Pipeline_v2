"""Controlled scene input; all subsequent adapters including STORAGE are real."""
from app import production_stages
from app.test_encoding_fixture import encoding_fixture, real_stage

def storage_fixture(name,context):
    return encoding_fixture(name,context) if name=='SCENES' else real_stage(name,context)

if __name__=='__main__':
    production_stages.execute_stage=storage_fixture
    production_stages.main()
