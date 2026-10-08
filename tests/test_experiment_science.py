"""Golden research fixtures and adversarial temporal/model isolation checks."""
from datetime import date, timedelta
from uuid import uuid4
import numpy as np
import pytest
from pydantic import ValidationError
from market_cortex.experiment_contracts import (ExperimentDefinition, ExperimentDataset, ResearchHypothesis,
    ValidationProtocol, ModelDefinition, ModelArtifact, FeatureSelectionDefinition, AnalogueRequest)
from market_cortex.experiment_datasets import stamp, eligible_context
from market_cortex.experiment_models import fit, predict, evaluate, purge, folds
from market_cortex.experiment_analysis import analogues, block_bootstrap, diagnostics


def rows(n=420, noise=0., seed=5):
    rng = np.random.default_rng(seed); result = []
    for i in range(n):
        day = date(2024, 1, 1)+timedelta(days=i); a, b = rng.normal(size=2)
        value = .2*a-.3*b+rng.normal()*noise
        result.append({'session': str(day), 'symbol': 'BTCUSDT', 'feature_at': stamp(day).isoformat(),
            'features': {'momentum_5': float(a), 'volatility_20': float(b)}, 'regime': 'up' if a > 0 else 'down',
            'observation_id': str(uuid4()), 'label': {'value': float(value), 'start': str(day+timedelta(days=1)),
                'end': str(day+timedelta(days=5)), 'known_at': stamp(day+timedelta(days=5)).isoformat()}})
    return result


def definition(model='ridge', folds_n=1):
    return ExperimentDefinition(hypothesis_id=uuid4(), dataset=ExperimentDataset(manifest_id=uuid4(),
        source_as_of=stamp(date(2026, 1, 1)), start=date(2024, 1, 1), end=date(2025, 1, 1)),
        validation=ValidationProtocol(train_sessions=240, test_sessions=90, max_folds=folds_n),
        model=ModelDefinition(registry_id=model, alphas=[.001, 10.]))


def hypothesis(target='return'):
    return ResearchHypothesis(question='Does a linear causal feature predict the label?', rationale='Synthetic golden controlled association.',
        relationship='The target is a fixed linear combination.', falsification='No held temporal error improvement.',
        features=['momentum_5', 'volatility_20'], symbols=['BTCUSDT'], target=target)


def test_golden_linear_train_only_scaler_and_safe_roundtrip():
    data = rows(); model = fit(data[:200], list(data[0]['features']), 'ridge', .001, 'regression', 2, 30)
    assert np.sqrt(np.mean((predict(model, data[300:])-np.array([r['label']['value'] for r in data[300:]]))**2)) < 1e-4
    assert np.allclose(model.means, [np.mean([r['features'][f] for r in data[:200]]) for f in model.features])
    assert np.array_equal(predict(ModelArtifact.model_validate_json(model.model_dump_json()), data), predict(model, data))


def test_noise_has_no_supported_edge_and_negative_skill_retained():
    data = rows(noise=10, seed=31); d = definition(); h = hypothesis()
    result = evaluate(data, d, h); report = diagnostics({'rows': data, 'missingness': {}}, result, d, h)
    assert report['metrics']['baseline_skill'] < .02
    assert report['multiple_testing']['fdr'].startswith('STATISTICAL_METHOD_UNAVAILABLE')
    assert report['calibration']['status'] == 'PROBABILITY_UNAVAILABLE'


def test_future_oos_target_and_feature_changes_cannot_change_training_or_tuning():
    data = rows(); d = definition(); h = hypothesis(); first = evaluate(data, d, h)
    changed = [{**r, 'features': dict(r['features']), 'label': dict(r['label'])} for r in data]
    for r in changed[245:]: r['label']['value'] = 1000.; r['features']['momentum_5'] = -999.
    second = evaluate(changed, d, h)
    assert first['models'] == second['models'] and first['search'] == second['search']
    assert first['predictions'] != second['predictions']


def test_purge_embargo_and_label_knowledge_boundaries():
    data = rows(); d = definition()
    for _, train, test, purged in folds(data, d.validation):
        boundary = date.fromisoformat(test[0]['session'])
        assert purged >= 5
        assert all(date.fromisoformat(r['label']['end']) < boundary-timedelta(days=5) for r in train)
    leaked = [{**r, 'label': {**r['label'], 'known_at': stamp(date(2030, 1, 1)).isoformat()}} for r in data[:100]]
    assert not purge(leaked, date(2025, 1, 1))


def test_top_k_selection_is_train_only():
    data = rows(); train = data[:200]
    model = fit(train, list(train[0]['features']), 'ridge', .1, 'regression', 1, 30)
    assert model.features == ['volatility_20'] and len(model.coefficients) == 1


@pytest.mark.parametrize('bad', [{'registry_id': 'pickle'}, {'coefficients': [float('nan')]},
    {'coefficients': [1, 2, 3]}, {'scales': [-1, 1]}, {'path': 'C:/secret'}, {'code': 'import os'}])
def test_safe_artifact_rejects_types_paths_nonfinite_and_shape(bad):
    model = fit(rows()[:80], ['momentum_5', 'volatility_20'], 'ridge', 1, 'regression', 2, 10).model_dump(mode='json')
    with pytest.raises(ValidationError): ModelArtifact.model_validate({**model, **bad})


def test_context_late_publication_ingest_manifest_and_revision_cannot_leak():
    cutoff = stamp(date(2025, 1, 1)); early = stamp(date(2024, 12, 31)).isoformat(); late = stamp(date(2025, 1, 2)).isoformat()
    f = {'logical_key': 'macro', 'revision_number': 1, 'domain': 'macro', 'series_id': 'avg_interest_rate_amt', 'value': '4',
        'validation_state': 'validated', 'classification_scope': 'LIVE_SOURCE',
        'envelope': {'observation_id': 'old', 'available_at': early, 'ingested_at': early, 'event_at': early, 'quality_state': 'valid'}}
    base = {'created_at': early, 'facts': [f], 'recorded_at': {'old': early}}
    assert eligible_context(base, cutoff, 'BTCUSDT')['macro_rate']['value'] == 4
    for field in ('available_at', 'ingested_at'):
        changed = {**f, 'envelope': {**f['envelope'], field: late}}
        assert not eligible_context({**base, 'facts': [changed]}, cutoff, 'BTCUSDT')
    assert not eligible_context({**base, 'created_at': late}, cutoff, 'BTCUSDT')
    revised = {**f, 'value': '99', 'revision_number': 2, 'envelope': {**f['envelope'], 'observation_id': 'new', 'available_at': late}}
    visible = eligible_context({**base, 'facts': [f, revised], 'recorded_at': {'old': early, 'new': late}}, cutoff, 'BTCUSDT')
    assert visible['macro_rate']['value'] == 4


def test_analogue_outcomes_never_influence_selection_and_future_never_selected():
    data = rows(); request = AnalogueRequest(experiment_id=uuid4(), reference_date=date.fromisoformat(data[300]['session']))
    first = analogues({'rows': data}, request)
    changed = [{**r, 'label': {**r['label'], 'value': 10000.}} for r in data]
    second = analogues({'rows': changed}, request)
    assert [(m['session'], m['distance']) for m in first['matches']] == [(m['session'], m['distance']) for m in second['matches']]
    assert all(m['session'] < str(request.reference_date) and m['historical_outcome']['end'] < str(request.reference_date) for m in first['matches'])
    assert 'label' not in first['reference']


def test_block_uncertainty_seeded_and_not_forecast_probability():
    result = evaluate(rows(), definition(), hypothesis())['predictions']
    first = block_bootstrap(result, 5, 100, 1, 'regression'); second = block_bootstrap(result, 5, 100, 1, 'regression')
    assert first == second and first['conditional_95pct_interval'][1] < 0
    assert 'NOT_PRICE_FORECAST_PROBABILITY' in first['warning']


def test_missing_context_is_inconclusive_not_zero_or_imputed():
    data = rows(); h = hypothesis().model_copy(update={'features': ['momentum_5', 'funding']})
    for r in data: r['features']['funding'] = None
    output = evaluate(data, definition(), h)
    assert output['complete_case_N'] == 0 and not output['models'] and not output['predictions']


def test_logistic_and_calibration_separate_temporal_windows():
    data = rows(n=500)
    for r in data: r['label']['value'] = float(r['label']['value'] > 0)
    d = definition('logistic'); d = d.model_copy(update={'validation': d.validation.model_copy(update={'calibration_sessions': 100})})
    output = evaluate(data, d, hypothesis('direction'))
    fold = output['folds'][0]
    assert fold['training_window'][1] < fold['calibration_window'][0] < fold['test_window'][0]
    assert all(0 <= p['prediction'] <= 1 for p in output['predictions'])
    assert fold['metrics']['brier'] < fold['mean_baseline']['brier']


def test_resource_and_arbitrary_configuration_rejection():
    with pytest.raises(ValidationError): ModelDefinition(registry_id='shell')
    with pytest.raises(ValidationError): ModelDefinition(max_iterations=100000)
    with pytest.raises(ValidationError): ModelDefinition(alphas=list(range(100)))
    with pytest.raises(ValidationError): ResearchHypothesis(**{**hypothesis().model_dump(), 'features': ['label']})
    with pytest.raises(ValidationError): ResearchHypothesis(**{**hypothesis().model_dump(), 'benchmark': 'cash'})


def test_regime_shift_is_visible_without_automatic_retraining():
    data = rows(); d = definition(); h = hypothesis()
    d = d.model_copy(update={'validation': d.validation.model_copy(update={'test_sessions': 120})})
    for r in data[245:]: r['features']['volatility_20'] += 20
    evaluation = evaluate(data, d, h)
    report = diagnostics({'rows': data, 'missingness': {}}, evaluation, d, h)
    assert report['drift'][0]['status'] == 'DEGRADED'
    assert report['drift'][0]['max_absolute_shift'] > 2


def test_golden_known_analogue_selects_features_before_outcome():
    data = rows(); data[300]['features'] = dict(data[100]['features'])
    result = analogues({'rows': data}, AnalogueRequest(experiment_id=uuid4(), reference_date=date.fromisoformat(data[300]['session'])))
    assert result['matches'][0]['session'] == data[100]['session'] and result['matches'][0]['distance'] == 0


def test_analogue_latest_reference_needs_no_future_label():
    data = rows(); reference = {k: v for k, v in data[-1].items() if k != 'label'}
    result = analogues({'rows': data[:-10], 'reference_rows': [reference]},
        AnalogueRequest(experiment_id=uuid4(), reference_date=date.fromisoformat(reference['session'])))
    assert result['matches'] and 'label' not in result['reference']


def test_later_context_manifest_does_not_hide_an_earlier_known_fact():
    early = stamp(date(2024, 12, 31)).isoformat(); late = stamp(date(2025, 1, 10)).isoformat()
    f = {'logical_key': 'macro', 'revision_number': 1, 'domain': 'macro', 'series_id': 'avg_interest_rate_amt', 'value': '4',
        'validation_state': 'validated', 'classification_scope': 'LIVE_SOURCE',
        'envelope': {'observation_id': 'old', 'available_at': early, 'ingested_at': early, 'event_at': early, 'quality_state': 'valid'}}
    frozen = {'created_at': late, 'facts': [f], 'recorded_at': {'old': early}, 'fact_manifest_times': {'old': early}}
    assert eligible_context(frozen, stamp(date(2025, 1, 1)), 'BTCUSDT')['macro_rate']['value'] == 4
    f['classification_scope'] = 'SYNTHETIC_TEST'
    assert not eligible_context(frozen, stamp(date(2025, 1, 1)), 'BTCUSDT')


def test_overlapping_test_folds_never_repeat_rows():
    data = rows(n=700); output = evaluate(data, definition(folds_n=4), hypothesis())
    keys = [(p['session'], p['symbol']) for p in output['predictions']]
    assert len(keys) == len(set(keys)) and len(output['folds']) == 4
