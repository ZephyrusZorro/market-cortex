"""Append-only research registry, search exposure, governance and Quant artifacts."""
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from psycopg.types.json import Jsonb
from .database import connect
from .quant_store import QuantStore, digest


def now(): return datetime.now(timezone.utc)
def key(kind, value): return uuid5(NAMESPACE_URL, 'experimental:'+kind+':'+digest(value))


class ExperimentStore:
    def __init__(self, dsn):
        self.dsn = dsn; self.quant = QuantStore(dsn)

    def hypothesis(self, request):
        payload = request.model_dump(mode='json'); h = digest(payload); k = key('hypothesis', payload)
        with connect(self.dsn) as c:
            c.execute('INSERT INTO research_hypotheses VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING', (k, h, now(), Jsonb(payload)))
        return self.get_hypothesis(k)

    def get_hypothesis(self, k, as_of=None):
        with connect(self.dsn) as c:
            row = c.execute('SELECT content_hash,recorded_at,payload FROM research_hypotheses WHERE hypothesis_id=%s AND recorded_at<=%s', (k, as_of or now())).fetchone()
        if row is None: raise LookupError('HYPOTHESIS_NOT_AVAILABLE')
        if digest(row[2]) != row[0]: raise ValueError('HYPOTHESIS_CHECKSUM_MISMATCH')
        return {'hypothesis_id': str(k), 'content_hash': row[0], 'recorded_at': row[1].isoformat(), 'hypothesis': row[2]}

    def register(self, definition, implementation, dependencies, source_hash):
        hypothesis = self.get_hypothesis(definition.hypothesis_id)
        identity = {'definition': definition.model_dump(mode='json'), 'hypothesis_hash': hypothesis['content_hash'],
            'code_hash': implementation, 'dependencies': dependencies, 'source_hash': source_hash}
        k = key('definition', identity); h = digest(identity)
        with connect(self.dsn) as c:
            inserted = c.execute('INSERT INTO experiment_definitions VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING experiment_id',
                (k, definition.hypothesis_id, h, now(), Jsonb(identity))).fetchone()
        if inserted:
            self.event(k, 'PROPOSED', {'definition_hash': h})
            self.event(k, 'VALIDATED', {'registry_and_bounds': 'PASS'})
            self.event(k, 'READY', {'no_deployment': True})
        return self.get(k)

    def get(self, k, as_of=None):
        with connect(self.dsn) as c:
            row = c.execute('SELECT content_hash,recorded_at,payload FROM experiment_definitions WHERE experiment_id=%s AND recorded_at<=%s', (k, as_of or now())).fetchone()
            event = c.execute('SELECT status,payload,revision,recorded_at FROM experiment_events WHERE experiment_id=%s AND recorded_at<=%s ORDER BY revision DESC LIMIT 1', (k, as_of or now())).fetchone()
        if row is None: raise LookupError('EXPERIMENT_NOT_AVAILABLE')
        if digest(row[2]) != row[0]: raise ValueError('EXPERIMENT_CHECKSUM_MISMATCH')
        return {'experiment_id': str(k), 'content_hash': row[0], 'recorded_at': row[1].isoformat(), **row[2],
            'status': event[0] if event else 'PROPOSED', 'event': event[1] if event else {}, 'revision': event[2] if event else 0}

    def event(self, k, status, payload):
        with connect(self.dsn) as c:
            c.execute('SELECT experiment_id FROM experiment_definitions WHERE experiment_id=%s FOR UPDATE', (k,))
            n = c.execute('SELECT coalesce(max(revision),0)+1 FROM experiment_events WHERE experiment_id=%s', (k,)).fetchone()[0]
            c.execute('INSERT INTO experiment_events VALUES (%s,%s,%s,%s,%s)', (k, n, now(), status, Jsonb(payload)))
        return n

    def history(self, k):
        self.get(k)
        with connect(self.dsn) as c:
            return [{'revision': n, 'recorded_at': at.isoformat(), 'status': s, **p} for n, at, s, p in
                c.execute('SELECT revision,recorded_at,status,payload FROM experiment_events WHERE experiment_id=%s ORDER BY revision', (k,)).fetchall()]

    def recent(self, hypotheses=False, as_of=None):
        table, column = ('research_hypotheses', 'hypothesis_id') if hypotheses else ('experiment_definitions', 'experiment_id')
        # These SQL identifiers are a private constant pair, never user input.
        with connect(self.dsn) as c:
            ids = c.execute(f'SELECT {column} FROM {table} WHERE recorded_at<=%s ORDER BY recorded_at DESC LIMIT 100', (as_of or now(),)).fetchall()
        return [self.get_hypothesis(k, as_of) if hypotheses else self.get(k, as_of) for (k,) in ids]

    def artifact(self, kind, definition, result, max_bytes=16_000_000):
        import json
        core = {'schema_version': 'experimental_artifact_v1', 'kind': kind, 'definition': definition, 'result': result}
        h = digest(core); k = uuid5(NAMESPACE_URL, f'quant:{kind}:{h}')
        if len(json.dumps(core, allow_nan=False).encode()) > max_bytes: raise ValueError('ARTIFACT_SIZE_LIMIT')
        payload = {**core, 'study_id': str(k), 'created_at': now().isoformat()}
        self.quant.save(kind, payload, h, k)
        return {'artifact_id': str(k), 'content_hash': h}

    def result(self, k, as_of=None):
        record = self.get(k, as_of); ref = record['event'].get('result_ref')
        if not ref:
            for event in reversed(self.history(k)):
                if event.get('result_ref') and (not as_of or datetime.fromisoformat(event['recorded_at']) <= as_of):
                    ref = event['result_ref']; break
        if not ref: raise LookupError('EXPERIMENT_RESULT_NOT_AVAILABLE')
        result = self.quant.get(UUID(ref), 'experiment_result', as_of=as_of)
        saved = result['result']
        if (saved['experiment_id'] != str(k) or saved['manifest']['definition_hash'] != record['content_hash'] or
            saved['manifest']['source_hash'] != record['source_hash']):
            raise ValueError('EXPERIMENT_RESULT_LINEAGE_MISMATCH')
        return result

    def exposure(self, k, dataset, hypothesis, expected_variants):
        # Import every preexisting Quant evaluation window as examined. The Phase 8
        # negative walk-forward and full backfilled Binance history are not pristine.
        with connect(self.dsn) as c:
            legacy = c.execute("SELECT artifact_id,payload,created_at FROM quant_artifacts WHERE kind IN ('run','walk_forward','sensitivity','robustness')").fetchall()
            for aid, p, at in legacy:
                d = p.get('definition', {}); d = d.get('definition', d)
                if not all(t in d for t in ('start', 'end', 'symbols')): continue
                eid = key('legacy-exposure', str(aid))
                c.execute('INSERT INTO experiment_exposures VALUES (%s,NULL,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                    (eid, at, d['start'], d['end'], Jsonb(d['symbols']), Jsonb({'legacy_artifact_id': str(aid), 'status': 'PREVIOUSLY_EXAMINED'})))
            # Capture source history inspection itself, even if no prior trade run.
            prior = c.execute('SELECT symbols FROM experiment_exposures WHERE start_date<=%s AND end_date>=%s', (dataset.end, dataset.start)).fetchall()
            reused = any(set(hypothesis.symbols)&set(r[0]) for r in prior)
            status = 'PREVIOUSLY_EXAMINED' if reused else 'EXPLORATORY_FIRST_EXPOSURE'
            eid = key('exposure', str(k))
            p = {'status': status, 'registration': hypothesis.registration, 'expected_variants': expected_variants,
                 'objective': 'brier_or_rmse', 'clean_unseen_status': 'NOT_ESTABLISHED', 'recorded_before_evaluation': True}
            c.execute('INSERT INTO experiment_exposures VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (eid, k, now(), dataset.start, dataset.end, Jsonb(hypothesis.symbols), Jsonb(p)))
            saved = c.execute('SELECT payload FROM experiment_exposures WHERE exposure_id=%s', (eid,)).fetchone()[0]
        return saved

    def ledger(self):
        with connect(self.dsn) as c:
            return [{'exposure_id': str(k), 'experiment_id': str(e) if e else None, 'recorded_at': at.isoformat(),
                'start': str(start), 'end': str(end), 'symbols': symbols, **p} for k, e, at, start, end, symbols, p in
                c.execute('SELECT * FROM experiment_exposures ORDER BY recorded_at,exposure_id').fetchall()]

    def govern(self, request, environment):
        from psycopg.conninfo import conninfo_to_dict
        record = self.get(request.experiment_id)
        if request.decision == 'HUMAN_APPROVED_RESEARCH_BASELINE' and (not request.owner_confirmed or environment != 'OWNER_MAIN' or
            conninfo_to_dict(self.dsn).get('dbname', '').lower().endswith('_test')):
            raise ValueError('OWNER_MAIN_EXPLICIT_APPROVAL_REQUIRED')
        if request.decision in ('HUMAN_APPROVED_RESEARCH_BASELINE', 'CANDIDATE_FOR_REVIEW'):
            self.result(request.experiment_id)
        with connect(self.dsn) as c:
            c.execute('SELECT experiment_id FROM experiment_definitions WHERE experiment_id=%s FOR UPDATE', (request.experiment_id,))
            revision = c.execute('SELECT coalesce(max(revision),0) FROM experiment_governance WHERE experiment_id=%s', (request.experiment_id,)).fetchone()[0]
            if revision != request.expected_revision: raise ValueError('GOVERNANCE_REVISION_CONFLICT')
            p = {**request.model_dump(mode='json'), 'revision': revision+1, 'definition_hash': record['content_hash'],
                'recorded_at': now().isoformat(), 'scope': 'RESEARCH_BASELINE_ONLY; NO_DEPLOYMENT; NO_SUPPORTED_EDGE_CLAIM'}
            c.execute('INSERT INTO experiment_governance VALUES (%s,%s,%s,%s,%s)',
                (request.experiment_id, revision+1, now(), Jsonb(p), digest(p)))
        if request.decision in ('REJECTED', 'ARCHIVED'): self.event(request.experiment_id, request.decision, {'governance_revision': revision+1})
        elif request.decision == 'CANDIDATE_FOR_REVIEW': self.event(request.experiment_id, 'REVIEW_REQUIRED', {'governance_revision': revision+1})
        return p

    def governance(self, k):
        with connect(self.dsn) as c:
            rows = c.execute('SELECT payload,content_hash FROM experiment_governance WHERE experiment_id=%s ORDER BY revision', (k,)).fetchall()
        for p, h in rows:
            if digest(p) != h: raise ValueError('GOVERNANCE_CHECKSUM_MISMATCH')
        return [p for p, _ in rows]
