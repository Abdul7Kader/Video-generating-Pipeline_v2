"""Durable storage changes on the native installation worker."""
from datetime import datetime, timedelta, timezone
from app.database import database
from app.production_jobs import try_lock
from app.production_stages import StageFailure
from app.media import media_root
from app.storage_settings import activate_store, chosen_path, copy_store, initialize_store, storage_lock


def dispatch_change(conn, row, queue):
    number=row['dispatch_number']
    job_id=f"storage-{row['id']}-{number}"
    job=queue.fetch_job(job_id)
    if job:
        state=job.get_status(refresh=True)
        if state in ('queued','scheduled','deferred'): return
        if state == 'started' and job.started_at and job.started_at > datetime.now(timezone.utc)-timedelta(seconds=30): return
        number+=1
        conn.execute('UPDATE storage_changes SET dispatch_number=%s WHERE id=%s',(number,row['id']))
        job_id=f"storage-{row['id']}-{number}"
    queue.enqueue('app.storage_jobs.change_storage',str(row['id']),job_id=job_id,
                  job_timeout=1200,result_ttl=86400,failure_ttl=86400)


def recover_storage_changes(queue):
    with database() as conn:
        rows=conn.execute("SELECT * FROM storage_changes WHERE state IN ('QUEUED','RUNNING') ORDER BY created_at LIMIT 1").fetchall()
    for row in rows:
        with database() as conn:
            if not try_lock(conn,'storage-'+str(row['id'])): continue
            row=conn.execute('SELECT * FROM storage_changes WHERE id=%s FOR UPDATE',(row['id'],)).fetchone()
            if row['state'] not in ('QUEUED','RUNNING'): continue
            if row['attempts'] >= 3:
                conn.execute("UPDATE storage_changes SET state='FAILED', error_code='STORAGE_INTERRUPTED', "
                             "error_message='Die Übernahme wurde dreimal unterbrochen. Bitte erneut starten.', updated_at=now() WHERE id=%s",(row['id'],))
                continue
            if row['state']=='RUNNING':
                conn.execute("UPDATE storage_changes SET state='QUEUED',updated_at=now() WHERE id=%s",(row['id'],))
            dispatch_change(conn,row,queue)


def change_storage(change_id):
    with database() as conn:
        conn.autocommit=True
        if not try_lock(conn,'storage-'+str(change_id)) or not storage_lock(conn): return
        row=conn.execute('SELECT * FROM storage_changes WHERE id=%s',(change_id,)).fetchone()
        if not row or row['state']!='QUEUED': return
        conn.execute("UPDATE storage_changes SET state='RUNNING', attempts=attempts+1, updated_at=now() WHERE id=%s",(change_id,))
        try:
            identity=initialize_store()
            root=media_root()
            target=chosen_path(row['new_path'])
            if root==target:
                # Config was activated immediately before a process interruption.
                conn.execute("UPDATE storage_changes SET state='COMPLETED', updated_at=now() WHERE id=%s",(change_id,))
                return
            if root != chosen_path(row['old_path']):
                raise StageFailure('STORAGE_CHANGED','Der Speicher wurde inzwischen geändert. Bitte neu laden.')
            def progress(total,done):
                conn.execute('UPDATE storage_changes SET total_bytes=%s, verified_bytes=%s,updated_at=now() WHERE id=%s',(total,done,change_id))
            copy_store(root,target,identity,progress)
            activate_store(target,identity)
            conn.execute("UPDATE storage_changes SET state='COMPLETED', updated_at=now() WHERE id=%s",(change_id,))
        except (StageFailure,OSError,ValueError,KeyError) as exc:
            code=exc.code if isinstance(exc,StageFailure) else 'STORAGE_COPY_FAILED'
            message=str(exc) if isinstance(exc,StageFailure) else 'Die Übernahme ist fehlgeschlagen. Schreibrechte und freien Speicher prüfen.'
            conn.execute("UPDATE storage_changes SET state='FAILED', error_code=%s,error_message=%s,updated_at=now() WHERE id=%s",(code,message,change_id))
