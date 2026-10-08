"""Experimental Quant Lab extension; shares data, replay, storage and jobs."""
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID
import platform
import re
import time
import numpy as np
from psycopg.types.json import Jsonb
from .database import connect
from .quant import QuantService, code_hash as quant_hash
from .quant_store import digest
from .experiment_contracts import ExperimentDefinition, ResearchHypothesis, ExperimentManifest, ExperimentResult, ExperimentRun
from .experiment_datasets import build_dataset
from .experiment_models import evaluate
from .experiment_analysis import diagnostics, analogues
from .experiment_store import ExperimentStore, now, key


def implementation_hash():
    paths = [Path(__file__), *Path(__file__).parent.glob('experiment_*.py')]
    return digest({'extension': {p.name: p.read_bytes().replace(b'\r\n', b'\n').decode() for p in sorted(paths)}, 'canonical_quant': quant_hash()})


IMPLEMENTATION_HASH = implementation_hash()
DEPENDENCIES = {'python': platform.python_version(), 'numpy': np.__version__}
LOCK_KEY = 837_241_912


class ExperimentService:
    def __init__(self, catalog, settings):
        self.catalog = catalog; self.settings = settings; self.store = ExperimentStore(catalog.dsn)
        self.quant = QuantService(catalog, settings.environment)

    def register(self, d):
        if d.dataset.source_as_of > now(): raise ValueError('FUTURE_SOURCE_CUTOFF_FORBIDDEN')
        h = self.store.get_hypothesis(d.hypothesis_id)['hypothesis']
        if d.model.registry_id == 'logistic' and h['target'] != 'direction': raise ValueError('LOGISTIC_REQUIRES_DIRECTION_LABEL')
        if d.model.registry_id == 'momentum' and 'momentum_5' not in h['features']: raise ValueError('MOMENTUM_BASELINE_REQUIRES_MOMENTUM_5')
        # Preregistered future protocols may still encounter previously examined
        # history. Registration does not grant a pristine holdout automatically.
        source, _ = self.quant.source(d.dataset)
        # Enrich the canonical frozen source without changing its engine or old
        # artifacts: each contextual fact also needs a known manifest membership.
        context = source.get('contextual', {})
        with connect(self.catalog.dsn) as c:
            ids = [UUID(f['envelope']['observation_id']) for f in context.get('facts', [])]
            manifests = [UUID(m) for m in context.get('manifest_times', {})]
            rows = c.execute('SELECT f.fact_id,min(m.created_at) FROM context_manifest_facts f JOIN context_manifests m USING(manifest_id) WHERE f.fact_id=ANY(%s) AND m.manifest_id=ANY(%s) GROUP BY f.fact_id', (ids, manifests)).fetchall()
        frozen = {**source, 'contextual': {**context, 'fact_manifest_times': {str(k): at.isoformat() for k, at in rows}}}
        source_hash = digest(frozen); self.store.quant.save('source', frozen, source_hash)
        self.canonical_evidence(d)
        return self.store.register(d, IMPLEMENTATION_HASH, DEPENDENCIES, source_hash)

    def canonical_evidence(self, d):
        rows = []
        for k in d.quant_run_ids+d.quant_study_ids:
            artifact = self.store.quant.get(k)
            if artifact.get('kind', 'run') not in ('run', 'walk_forward', 'robustness', 'sensitivity', 'monte_carlo'):
                raise ValueError('UNREGISTERED_CANONICAL_STUDY_REFERENCE')
            definition = artifact['definition']; definition = definition.get('definition', definition)
            if str(definition.get('manifest_id')) != str(d.dataset.manifest_id):
                raise ValueError('CANONICAL_EVIDENCE_MANIFEST_MISMATCH')
            rows.append({'artifact_id': str(k), 'kind': artifact.get('kind', 'run'),
                'content_hash': digest(artifact), 'metrics': artifact.get('metrics'),
                'result': artifact.get('result'), 'warnings': artifact.get('warnings', []),
                'interpretation': 'CANONICAL_BAR_BACKTEST; SEPARATE_FROM_FORECAST_LABEL_METRICS'})
        return rows

    def compute(self, record, source, check=lambda: None, record_trial=lambda row: None):
        d = ExperimentDefinition.model_validate(record['definition'])
        hypothesis = self.store.get_hypothesis(d.hypothesis_id)
        h = ResearchHypothesis.model_validate(hypothesis['hypothesis'])
        dataset = build_dataset(source, d, h, check)
        evaluation = evaluate(dataset['rows'], d, h, check, record_trial)
        reports = diagnostics(dataset, evaluation, d, h, check)
        reports['canonical_quant_evidence'] = self.canonical_evidence(d)
        n = reports['metrics']['N']; improvement = reports['metrics'].get('baseline_skill')
        conclusion = 'INSUFFICIENT_EVIDENCE' if n < h.minimum_oos_rows else 'HYPOTHESIS_FALSIFIED' if improvement is None or improvement < h.minimum_improvement else 'EXPLORATORY_IMPROVEMENT'
        status = 'INCONCLUSIVE' if n < h.minimum_oos_rows else 'COMPLETED'
        warnings = dataset['warnings']+['NO_SUPPORTED_EDGE; NO_GENUINELY_UNSEEN_VALIDATION',
            'PRIOR_PHASE8_MOMENTUM_OOS_MINUS_7_82_PERCENT_N_82_PRESERVED; PREVIOUSLY_EXAMINED',
            'STATISTICAL_METHOD_UNAVAILABLE_WHERE_ASSUMPTIONS_FAIL', 'NO_AUTOMATIC_PROMOTION; NO_ORDER_EXECUTION']
        result = ExperimentResult(status=status, conclusion=conclusion,
            reports={**reports, 'folds': evaluation['folds'], 'search': evaluation['search'], 'predictions': evaluation['predictions']}, warnings=warnings)
        return dataset, evaluation, result

    def run(self, experiment_id, job=None):
        record = self.store.get(experiment_id)
        if record['status'] in ('REJECTED', 'ARCHIVED'): raise ValueError('EXPERIMENT_CLOSED_BY_GOVERNANCE')
        if record['code_hash'] != IMPLEMENTATION_HASH or record['dependencies'] != DEPENDENCIES:
            raise ValueError('EXPERIMENT_VERSION_UNAVAILABLE')
        if record['status'] in ('COMPLETED', 'INCONCLUSIVE', 'REVIEW_REQUIRED'):
            return self.store.result(experiment_id)
        d = ExperimentDefinition.model_validate(record['definition']); h = ResearchHypothesis.model_validate(self.store.get_hypothesis(d.hypothesis_id)['hypothesis'])
        deadline = time.monotonic()+d.configuration.timeout_seconds
        def check():
            if time.monotonic() > deadline: raise ValueError('EXPERIMENT_TIMEOUT')
            if job:
                with connect(self.catalog.dsn) as c:
                    row = c.execute("SELECT state,attempts,lease_until>now() FROM jobs WHERE job_id=%s AND kind='experimental_research'", (job.job_id,)).fetchone()
                if not row or row[0] != 'leased' or row[1] != job.attempts or not row[2]: raise ValueError('EXPERIMENT_CANCELLED_OR_LEASE_LOST')
        with connect(self.catalog.dsn) as lock:
            if not lock.execute('SELECT pg_try_advisory_lock(%s)', (LOCK_KEY,)).fetchone()[0]: raise ValueError('EXPERIMENT_CONCURRENCY_LIMIT')
            self.store.event(experiment_id, 'RUNNING', {'budget_seconds': d.configuration.timeout_seconds})
            try:
                check()
                exposure = self.store.exposure(experiment_id, d.dataset, h,
                    d.validation.max_folds*(len(d.model.alphas)+1+len(h.features)))
                sh = record['source_hash']; source = self.store.quant.by_hash('source', sh)
                if not source or digest(source) != sh: raise ValueError('EXPERIMENT_SOURCE_HASH_MISMATCH')
                dataset, evaluation, result = self.compute(record, source, check,
                    lambda trial: self.store.event(experiment_id, 'RUNNING', {'stage': 'INNER_SEARCH', 'trial': trial}))
                check(); limit = d.configuration.max_artifact_bytes
                ds = self.store.artifact('experiment_dataset', {'experiment_id': str(experiment_id), 'source_hash': sh}, dataset, limit)
                model_refs = [self.store.artifact('experiment_model', {'experiment_id': str(experiment_id), 'fold': i+1}, model, limit)
                              for i, model in enumerate(evaluation['models'])]
                manifest = ExperimentManifest(definition_hash=record['content_hash'], hypothesis_hash=record['hypothesis_hash'],
                    source_hash=sh, dataset_hash=ds['content_hash'], code_hash=IMPLEMENTATION_HASH, dependencies=DEPENDENCIES,
                    holdout_status=exposure['status'])
                run = ExperimentRun(experiment_id=experiment_id, manifest=manifest, result=result,
                    result_hash=digest(result.model_dump(mode='json')))
                ref = self.store.artifact('experiment_result', record['definition'],
                    {**run.model_dump(mode='json'), 'dataset_ref': ds, 'model_refs': model_refs, 'exposure': exposure}, limit)
                check(); self.store.event(experiment_id, result.status, {'result_ref': ref['artifact_id'], 'result_hash': run.result_hash})
                return self.store.result(experiment_id)
            except (ValueError, LookupError) as e:
                # Error codes only, never DSNs, provider bodies, owner prose or secrets.
                self.store.event(experiment_id, 'FAILED', {'error_code': str(e) if re.fullmatch('[A-Z0-9_]{1,90}', str(e)) else 'EXPERIMENT_FAILED'})
                raise

    def replay(self, experiment_id):
        record = self.store.get(experiment_id); saved = self.store.result(experiment_id)['result']
        if record['code_hash'] != IMPLEMENTATION_HASH or record['dependencies'] != DEPENDENCIES:
            return {'status': 'VERSION_UNAVAILABLE', 'saved_result_hash': saved['result_hash']}
        source = self.store.quant.by_hash('source', saved['manifest']['source_hash'])
        if not source or digest(source) != saved['manifest']['source_hash']: raise ValueError('EXPERIMENT_SOURCE_HASH_MISMATCH')
        deadline = time.monotonic()+ExperimentDefinition.model_validate(record['definition']).configuration.timeout_seconds
        def check():
            if time.monotonic() > deadline: raise ValueError('EXPERIMENT_TIMEOUT')
        dataset, _, result = self.compute(record, source, check)
        ds = self.store.quant.get(UUID(saved['dataset_ref']['artifact_id']), 'experiment_dataset')
        exact = dataset == ds['result'] and digest(result.model_dump(mode='json')) == saved['result_hash']
        return {'status': 'MATCH' if exact else 'MISMATCH', 'saved_result_hash': saved['result_hash'],
                'recomputed_result_hash': digest(result.model_dump(mode='json')), 'dataset_match': dataset == ds['result'],
                'comparison': 'EXACT_SAME_NUMPY_RUNTIME; CROSS_RUNTIME_RECOMPUTE_REQUIRES_RECORDED_VERSION'}

    def analogue(self, request):
        saved = self.store.result(request.experiment_id)['result']
        dataset = self.store.quant.get(UUID(saved['dataset_ref']['artifact_id']), 'experiment_dataset')['result']
        return self.store.artifact('experiment_analogue', request.model_dump(mode='json'), analogues(dataset, request))

    def compare(self, request):
        records = [self.store.get(k) for k in request.experiment_ids]
        results = [self.store.result(k)['result'] for k in request.experiment_ids]
        signatures = [{k: r['definition'][k] for k in ('dataset', 'validation', 'configuration')} | {'hypothesis_hash': r['hypothesis_hash']} for r in records]
        return self.store.artifact('experiment_comparison', request.model_dump(mode='json'), {'directly_comparable': all(x == signatures[0] for x in signatures),
            'rows': [{'experiment_id': r['experiment_id'], 'model': r['definition']['model'], 'status': result['result']['status'],
                'conclusion': result['result']['conclusion'], 'metrics': result['result']['reports']['metrics'],
                'holdout_status': result['manifest']['holdout_status'], 'folds': result['result']['reports']['folds']} for r, result in zip(records, results)],
            'warning': 'COMPARISON_INSPECTS_ALL_OUTCOMES; NO_OOS_WINNER_PROMOTION; DIFFERENT_HYPOTHESES_NOT_DIRECTLY_COMPARABLE'})

    def proposal(self, request):
        parent = self.store.get(request.parent_experiment_id); self.store.result(request.parent_experiment_id)
        child = self.register(request.definition)
        if child['experiment_id'] == parent['experiment_id']: raise ValueError('PROPOSAL_REQUIRES_A_NEW_DEFINITION')
        if child['status'] != 'READY': raise ValueError('PROPOSAL_MUST_PRECEDE_EVALUATION')
        p = {**request.model_dump(mode='json'), 'child_experiment_id': child['experiment_id'],
            'registration': 'EXPLORATORY_REVISION_AFTER_PRIOR_RESULT; HOLDOUT_REUSE_RECORDED', 'recorded_at': now().isoformat()}
        k = key('proposal', {**request.model_dump(mode='json'), 'child_experiment_id': child['experiment_id']})
        with connect(self.catalog.dsn) as c:
            c.execute('INSERT INTO experiment_proposals VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (k, request.parent_experiment_id, UUID(child['experiment_id']), now(), Jsonb(p), digest(p)))
            saved, sh = c.execute('SELECT payload,content_hash FROM experiment_proposals WHERE proposal_id=%s', (k,)).fetchone()
            if digest(saved) != sh: raise ValueError('PROPOSAL_CHECKSUM_MISMATCH')
        return {'proposal_id': str(k), **saved}

    def attach_edge(self, request):
        record = self.store.get(request.experiment_id); result = self.store.result(request.experiment_id)['result']
        h = self.store.get_hypothesis(UUID(record['definition']['hypothesis_id']))['hypothesis']
        if request.stance == 'SUPPORTING' and result['result']['conclusion'] != 'EXPLORATORY_IMPROVEMENT':
            raise ValueError('FALSIFIED_OR_INSUFFICIENT_EXPERIMENT_CANNOT_SUPPORT_EDGE')
        with connect(self.catalog.dsn) as c:
            edge = c.execute('SELECT payload FROM edge_library WHERE edge_id=%s', (request.edge_id,)).fetchone()
            if not edge: raise LookupError('EDGE_NOT_FOUND')
            if not set(edge[0].get('symbols', h['symbols'])) & set(h['symbols']): raise ValueError('UNRELATED_EDGE_UNIVERSE')
            p = {**request.model_dump(mode='json'), 'recorded_at': now().isoformat(), 'result_hash': result['result_hash'],
                'metrics': result['result']['reports']['metrics'], 'conclusion': result['result']['conclusion'],
                'robustness': result['result']['reports']['robustness']['classification'], 'holdout': result['manifest']['holdout_status'],
                'costs': record['definition']['configuration']['costs'], 'source_manifest': record['definition']['dataset']['manifest_id'],
                'search': result['result']['reports']['multiple_testing'], 'effect': 'ATTACH_EVIDENCE_ONLY; EDGE_STATUS_UNCHANGED'}
            k = key('edge-link', request.model_dump(mode='json'))
            c.execute('INSERT INTO experiment_edge_links VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (k, request.edge_id, request.experiment_id, now(), Jsonb(p), digest(p)))
            saved, sh = c.execute('SELECT payload,content_hash FROM experiment_edge_links WHERE link_id=%s', (k,)).fetchone()
            if digest(saved) != sh: raise ValueError('EDGE_LINK_CHECKSUM_MISMATCH')
        return {'link_id': str(k), **saved}

    def edge_links(self, edge_id=None):
        with connect(self.catalog.dsn) as c:
            rows = c.execute('SELECT payload,content_hash FROM experiment_edge_links WHERE (%s::uuid IS NULL OR edge_id=%s) ORDER BY recorded_at', (edge_id, edge_id)).fetchall()
        for p, h in rows:
            if digest(p) != h: raise ValueError('EDGE_LINK_CHECKSUM_MISMATCH')
        return [p for p, _ in rows]
