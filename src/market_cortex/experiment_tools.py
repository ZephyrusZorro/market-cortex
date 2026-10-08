"""Approved Phase 12 CORTEX extension. Inputs never become instructions or code."""
from uuid import UUID
from .experiment_contracts import ExperimentQuestion, ExperimentMissionInput
from .experiment_store import now

REPORTS = {'experiment.validation': 'folds', 'experiment.models': 'metrics',
    'experiment.features': 'feature_importance', 'experiment.regimes': 'regime_research',
    'experiment.calibration': 'calibration', 'experiment.drift': 'drift', 'experiment.robustness': 'robustness',
    'experiment.search': 'multiple_testing'}


def metadata():
    return [{'tool_id': t, 'version': '1.0.0', 'deterministic': True, 'access': 'READ_ONLY',
        'privacy': 'LOCAL_ONLY', 'cost_class': 'FREE_LOCAL', 'side_effects': 'none'} for t in
        ['experiment.inspect', 'experiment.hypothesis', 'experiment.ledger', *REPORTS]] + [
        {'tool_id': 'experiment.run_registered', 'version': '1.0.0', 'access': 'BOUNDED_RESEARCH_ARTIFACT_WRITE',
         'authorization': 'EXPLICIT_MISSION_AUTHORIZE_RUN', 'deployment': False, 'cost_class': 'FREE_LOCAL'}]


def execute(service, tool_id, experiment_id):
    if tool_id == 'experiment.inspect': return service.store.get(experiment_id)
    if tool_id == 'experiment.hypothesis':
        d = service.store.get(experiment_id); return service.store.get_hypothesis(UUID(d['definition']['hypothesis_id']))
    if tool_id == 'experiment.ledger': return {'items': service.store.ledger()}
    if tool_id not in REPORTS: raise ValueError('EXPERIMENT_TOOL_NOT_ALLOWED')
    saved = service.store.result(experiment_id)['result']
    return {'experiment_id': str(experiment_id), 'result_hash': saved['result_hash'],
        'report': saved['result']['reports'][REPORTS[tool_id]], 'warnings': saved['result']['warnings']}


def explain(service, request: ExperimentQuestion):
    record = service.store.get(request.experiment_id); saved = service.store.result(request.experiment_id)['result']
    result = saved['result']; reports = result['reports']; m = reports['metrics']
    # The question is private untrusted prose. No model/tool/code is selected from it.
    return {'experiment_id': str(request.experiment_id), 'privacy': 'LOCAL_ONLY', 'provider': 'deterministic', 'paid_api_cost_inr': 0,
        'answer': f"{result['conclusion']}. Evaluated {m['N']} dependent temporal test rows; baseline skill {m.get('baseline_skill')}. "
            f"Robustness: {reports['robustness']['classification']}. {saved['manifest']['holdout_status']}; no genuinely unseen validation. "
            'No supported edge exists based on the available evidence.',
        'metrics': m, 'frozen_criteria': {'definition_hash': record['content_hash'], 'hypothesis_hash': record['hypothesis_hash']},
        'skeptic': ['Small/dependent cells can invalidate apparent improvements.', 'Selected survivors and reconstructed historical availability limit generalization.',
            'Permutation importance is noncausal; all test outcomes are now examined.', 'Prior momentum OOS -7.82%, N=82 remains negative evidence.'],
        'warnings': result['warnings'], 'evidence': [{'source': 'experiment_result', 'id': saved['experiment_id'], 'hash': saved['result_hash']}]}


def mission(service, request: ExperimentMissionInput):
    from .missions import MissionService
    from .mission_contracts import MissionRequest, MissionBudget
    record = service.store.get(request.experiment_id)
    budget = request.max_tool_calls; used = 0; activity = []
    def call(t):
        nonlocal used
        if used >= budget: raise ValueError('EXPERIMENT_TOOL_BUDGET_EXHAUSTED')
        used += 1; activity.append({'tool_id': t, 'sequence': used})
    if request.authorize_run:
        call('experiment.run_registered'); service.run(request.experiment_id)
    call('experiment.inspect'); execute(service, 'experiment.inspect', request.experiment_id)
    call('experiment.models'); execute(service, 'experiment.models', request.experiment_id)
    call('experiment.search'); execute(service, 'experiment.search', request.experiment_id)
    call('experiment.ledger'); ledger = execute(service, 'experiment.ledger', request.experiment_id)
    preference = {'history_state': 'INSUFFICIENT_HISTORY', 'owner_record_N': 0, 'influences': 'QUESTION_PRIORITY_ONLY; SCIENTIFIC_CRITERIA_FROZEN'}
    if request.personalization_snapshot_id:
        from .personalization import PersonalizationService
        personal = PersonalizationService(service.catalog, service.settings)
        snapshot = personal.store.snapshot(request.personalization_snapshot_id)
        if snapshot.as_of > now(): raise ValueError('FUTURE_PERSONALIZATION_FORBIDDEN')
        if snapshot.audience != 'OWNER_RESEARCH': raise ValueError('SYNTHETIC_PROFILE_CANNOT_PRIORITIZE_OWNER_RESEARCH')
        preference.update(snapshot_id=str(snapshot.snapshot_id), snapshot_hash=snapshot.content_hash,
            history_state=snapshot.observed_behavior['history_state'], owner_record_N=snapshot.observed_behavior['genuine_owner_record_N'])
    d = record['definition']['dataset']; base = None
    remaining = budget-used
    if remaining >= 2:
        s = MissionService(service.catalog, service.settings)
        input = MissionRequest(goal='Inspect the pinned market evidence and challenge experimental research claims.',
            mode='QUICK_RESEARCH', manifest_id=UUID(d['manifest_id']), as_of=d['source_as_of'], symbol='BTCUSDT',
            approved_domains=['market'], required_domains=['market'], budgets=MissionBudget(max_tool_calls=remaining, timeout_seconds=60))
        base = s.run(s.create(input).mission_id)
        used += base.usage.tool_calls
    answer = explain(service, ExperimentQuestion(experiment_id=request.experiment_id, question='Challenge the frozen experimental evidence.'))
    saved = service.store.result(request.experiment_id)['result']
    dossier = {'experiment_id': str(request.experiment_id), 'experiment_result_hash': saved['result_hash'],
        'canonical_mission_id': str(base.mission_id) if base else None, 'canonical_mission_hash': base.content_hash if base else None,
        'canonical_mission_status': base.status if base else 'TOOL_BUDGET_UNAVAILABLE', 'activity': activity,
        'usage': {'tool_calls': used, 'limit': budget, 'model_calls': 0, 'paid_api_cost_inr': 0},
        'personalization': preference, 'report': answer, 'prior_research_records_N': len(ledger['items']),
        'governance': 'EXPERIMENTAL; NO_DEPLOYMENT; NO_AUTONOMOUS_PROMOTION'}
    return service.store.artifact('experiment_dossier', request.model_dump(mode='json'), dossier)


def replay_dossier(service, artifact_id):
    from .missions import MissionService
    saved = service.store.quant.get(artifact_id, 'experiment_dossier')['result']
    result = service.store.result(UUID(saved['experiment_id']))['result']
    base = MissionService(service.catalog, service.settings).replay(UUID(saved['canonical_mission_id'])) if saved['canonical_mission_id'] else None
    personal_ok = True
    if saved['personalization'].get('snapshot_id'):
        from .personalization import PersonalizationService
        p = PersonalizationService(service.catalog, service.settings)
        snapshot = p.store.snapshot(UUID(saved['personalization']['snapshot_id']))
        personal_ok = p.verify_snapshot(snapshot)['matched'] and snapshot.content_hash == saved['personalization']['snapshot_hash']
    return {'status': 'MATCH' if result['result_hash'] == saved['experiment_result_hash'] and
        (not base or base.get('matched')) and personal_ok else 'MISMATCH', 'canonical_mission_replay': base,
        'personalization_verified': personal_ok, 'experiment_result_hash': result['result_hash']}
