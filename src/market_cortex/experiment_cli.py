"""CLI dispatch through the same bounded domain services as the local API."""
import json
from uuid import UUID
from pathlib import Path


def add_commands(sub):
    for name in ('hypothesis', 'register', 'compare', 'analogue', 'proposal', 'govern', 'mission', 'query', 'attach-edge'):
        command = sub.add_parser('experiment-'+name, help='Typed experimental research; no executable inputs')
        command.add_argument('--input', type=Path, required=True)
    for name in ('inspect', 'run', 'replay', 'result', 'history', 'governance'):
        command = sub.add_parser('experiment-'+name, help='Inspect or run a frozen registered experiment')
        command.add_argument('experiment_id', type=UUID)
    for name in ('list', 'ledger', 'models'): sub.add_parser('experiment-'+name, help='Inspect experimental research registry')


def dispatch(args, settings):
    from .storage import PostgresCatalog, ArtifactStore
    from .experiments import ExperimentService
    from .experiment_contracts import (ResearchHypothesis, ExperimentDefinition, ExperimentComparison, AnalogueRequest,
        ExperimentProposal, PromotionDecision, ExperimentMissionInput, ExperimentQuestion, ExperimentEdgeInput, MODELS)
    from .experiment_tools import mission, explain
    if not settings.database_url: raise ValueError('DATABASE_NOT_CONFIGURED')
    s = ExperimentService(PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root)), settings)
    op = args.command.removeprefix('experiment-')
    if hasattr(args, 'input'):
        if args.input.stat().st_size > 8192: raise ValueError('EXPERIMENT_INPUT_TOO_LARGE')
        models = {'hypothesis': ResearchHypothesis, 'register': ExperimentDefinition, 'compare': ExperimentComparison,
            'analogue': AnalogueRequest, 'proposal': ExperimentProposal, 'govern': PromotionDecision,
            'mission': ExperimentMissionInput, 'query': ExperimentQuestion, 'attach-edge': ExperimentEdgeInput}
        request = models[op].model_validate_json(args.input.read_text(encoding='utf-8-sig'))
        if op == 'hypothesis': result = s.store.hypothesis(request)
        elif op == 'govern': result = s.store.govern(request, settings.environment)
        elif op == 'mission': result = mission(s, request)
        elif op == 'query': result = explain(s, request)
        else: result = getattr(s, {'attach-edge': 'attach_edge'}.get(op, op))(request)
    elif op in ('list', 'ledger', 'models'):
        result = {'items': s.store.recent() if op == 'list' else s.store.ledger() if op == 'ledger' else list(MODELS)}
    elif op in ('inspect', 'result', 'history', 'governance'):
        result = getattr(s.store, {'inspect': 'get'}.get(op, op))(args.experiment_id)
    else: result = getattr(s, op)(args.experiment_id)
    print(json.dumps(result, default=str, allow_nan=False))
    return 0
