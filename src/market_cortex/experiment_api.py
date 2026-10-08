"""Typed loopback experiment routes and durable, cancellable bounded jobs."""
import re
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, HTTPException
from .database import connect
from .jobs import JobQueue
from .experiment_contracts import (ResearchHypothesis, ExperimentDefinition, AnalogueRequest, ExperimentComparison,
    ExperimentProposal, PromotionDecision, ExperimentEdgeInput, ExperimentQuestion, ExperimentMissionInput, MODELS, FEATURES)
from .experiments import ExperimentService, IMPLEMENTATION_HASH, DEPENDENCIES
from .experiment_tools import execute, metadata, explain, mission, replay_dossier
from .quant_store import digest


def run_job(service, job_id):
    queue = JobQueue(service.catalog.dsn); job = queue.claim(3600, kind='experimental_research', job_id=job_id)
    if not job: return
    try:
        result = service.run(UUID(job.payload['experiment_id']), job=job)
        with connect(service.catalog.dsn) as c:
            row = c.execute("UPDATE jobs SET result_ref=%s WHERE job_id=%s AND state='leased' AND attempts=%s RETURNING job_id",
                (UUID(result['study_id']), job.job_id, job.attempts)).fetchone()
        if row: queue.finish(job.job_id, job.attempts)
    except Exception as e:
        code = str(e) if isinstance(e, (ValueError, LookupError)) and re.fullmatch('[A-Z0-9_]{1,90}', str(e)) else 'EXPERIMENT_RESEARCH_FAILED'
        with connect(service.catalog.dsn) as c:
            row = c.execute("SELECT 1 FROM jobs WHERE job_id=%s AND state='leased' AND attempts=%s", (job.job_id, job.attempts)).fetchone()
        if row: queue.finish(job.job_id, job.attempts, code, max_attempts=1)


def router_for(catalog, settings):
    router = APIRouter(prefix='/api/v1/experimental', tags=['experimental quant research'])
    service = ExperimentService(catalog, settings)
    def call(fn):
        try: return fn()
        except (ValueError, LookupError, KeyError) as e:
            code = str(e) if re.fullmatch('[A-Z0-9_]{1,90}', str(e)) else 'EXPERIMENT_REQUEST_FAILED'
            raise HTTPException(404 if isinstance(e, LookupError) else 422, detail={'code': code}) from None
    @router.get('/registry')
    def registry():
        return {'models': [{'registry_id': m, 'version': 'numpy_cpu_v1', 'format': 'restricted_json_v1', 'experimental': True} for m in MODELS],
            'features': list(FEATURES), 'concurrent_experiments': 1, 'maximum_training_iterations': 100,
            'maximum_grid_variants': 4, 'maximum_folds': 6, 'maximum_rows': 15000, 'maximum_artifact_bytes': 16000000,
            'implementation_hash': IMPLEMENTATION_HASH, 'dependencies': DEPENDENCIES, 'deployment': False, 'privacy': 'LOCAL_ONLY'}
    @router.get('/hypotheses')
    def hypotheses(): return call(lambda: {'items': service.store.recent(hypotheses=True)})
    @router.post('/hypotheses', status_code=201)
    def hypothesis(request: ResearchHypothesis): return call(lambda: service.store.hypothesis(request))
    @router.get('/hypotheses/{hypothesis_id}')
    def hypothesis_read(hypothesis_id: UUID): return call(lambda: service.store.get_hypothesis(hypothesis_id))
    @router.get('/experiments')
    def experiments(): return call(lambda: {'items': service.store.recent()})
    @router.post('/experiments', status_code=201)
    def register(request: ExperimentDefinition): return call(lambda: service.register(request))
    @router.get('/experiments/{experiment_id}')
    def inspect(experiment_id: UUID): return call(lambda: service.store.get(experiment_id))
    @router.get('/experiments/{experiment_id}/history')
    def history(experiment_id: UUID): return call(lambda: {'items': service.store.history(experiment_id)})
    @router.get('/experiments/{experiment_id}/result')
    def result(experiment_id: UUID): return call(lambda: service.store.result(experiment_id))
    @router.get('/experiments/{experiment_id}/dataset')
    def dataset(experiment_id: UUID):
        def get():
            ref = service.store.result(experiment_id)['result']['dataset_ref']['artifact_id']
            return service.store.quant.get(UUID(ref), 'experiment_dataset')
        return call(get)
    @router.get('/experiments/{experiment_id}/reports/{report}')
    def report(experiment_id: UUID, report: str): return call(lambda: execute(service, 'experiment.'+report, experiment_id))
    @router.post('/experiments/{experiment_id}/replay')
    def replay(experiment_id: UUID): return call(lambda: service.replay(experiment_id))
    @router.get('/artifacts/{artifact_id}')
    def artifact(artifact_id: UUID):
        def get():
            payload = service.store.quant.get(artifact_id)
            if not payload['kind'].startswith('experiment_'): raise LookupError('EXPERIMENT_ARTIFACT_NOT_FOUND')
            return payload
        return call(get)
    @router.post('/experiments/{experiment_id}/jobs', status_code=202)
    def enqueue(experiment_id: UUID, background: BackgroundTasks):
        record = call(lambda: service.store.get(experiment_id))
        if record['status'] in ('ARCHIVED', 'REJECTED'): raise HTTPException(422, detail={'code': 'EXPERIMENT_CLOSED_BY_GOVERNANCE'})
        job_id = JobQueue(catalog.dsn).enqueue('experimental_research', 'experimental:'+digest({'id': str(experiment_id), 'hash': record['content_hash']}), {'experiment_id': str(experiment_id)})
        background.add_task(run_job, service, job_id)
        return {'job_id': str(job_id), 'status': 'queued'}
    @router.get('/jobs/{job_id}')
    def status(job_id: UUID):
        with connect(catalog.dsn) as c:
            row = c.execute("SELECT state,error_code,result_ref,attempts FROM jobs WHERE job_id=%s AND kind='experimental_research'", (job_id,)).fetchone()
        if not row: raise HTTPException(404, detail={'code': 'EXPERIMENT_JOB_NOT_FOUND'})
        return {'job_id': str(job_id), 'status': 'cancelled' if row[1] == 'EXPERIMENT_CANCELLED' else
            {'ready': 'queued', 'leased': 'running', 'done': 'completed', 'dead': 'failed'}[row[0]],
            'error_code': row[1], 'result_ref': str(row[2]) if row[2] else None, 'attempts': row[3]}
    @router.post('/jobs/{job_id}/cancel')
    def cancel(job_id: UUID):
        with connect(catalog.dsn) as c:
            c.execute("UPDATE jobs SET state='dead',error_code='EXPERIMENT_CANCELLED',lease_until=NULL,result_ref=NULL WHERE job_id=%s AND kind='experimental_research' AND state IN ('ready','leased')", (job_id,))
        return status(job_id)
    @router.post('/jobs/{job_id}/retry', status_code=202)
    def retry(job_id: UUID, background: BackgroundTasks):
        with connect(catalog.dsn) as c:
            row = c.execute("UPDATE jobs SET state='ready',error_code=NULL,next_attempt_at=now() WHERE job_id=%s AND kind='experimental_research' AND state='dead' RETURNING job_id", (job_id,)).fetchone()
        if not row: raise HTTPException(422, detail={'code': 'ONLY_FAILED_OR_CANCELLED_EXPERIMENT_CAN_RETRY'})
        background.add_task(run_job, service, job_id); return {'job_id': str(job_id), 'status': 'queued'}
    @router.get('/ledger')
    def ledger(): return call(lambda: {'items': service.store.ledger(), 'clean_unseen_status': 'NOT_ESTABLISHED'})
    @router.post('/compare')
    def compare(request: ExperimentComparison): return call(lambda: service.compare(request))
    @router.post('/analogues')
    def analogue(request: AnalogueRequest): return call(lambda: service.analogue(request))
    @router.post('/proposals')
    def proposal(request: ExperimentProposal): return call(lambda: service.proposal(request))
    @router.post('/governance')
    def govern(request: PromotionDecision): return call(lambda: service.store.govern(request, settings.environment))
    @router.get('/experiments/{experiment_id}/governance')
    def governance(experiment_id: UUID): return call(lambda: {'items': service.store.governance(experiment_id)})
    @router.post('/edges/evidence')
    def edge(request: ExperimentEdgeInput): return call(lambda: service.attach_edge(request))
    @router.get('/edges/evidence')
    def edges(edge_id: UUID | None = None): return call(lambda: {'items': service.edge_links(edge_id)})
    @router.get('/tools')
    def tools(): return {'items': metadata()}
    @router.post('/query')
    def query(request: ExperimentQuestion): return call(lambda: explain(service, request))
    @router.post('/missions')
    def investigate(request: ExperimentMissionInput): return call(lambda: mission(service, request))
    @router.post('/dossiers/{artifact_id}/replay')
    def dossier_replay(artifact_id: UUID): return call(lambda: replay_dossier(service, artifact_id))
    return router
