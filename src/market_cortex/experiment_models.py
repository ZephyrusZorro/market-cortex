"""Small NumPy models with training-only transforms and restricted JSON artifacts."""
from datetime import datetime, timedelta
import numpy as np
from .experiment_contracts import ModelArtifact
from .experiment_datasets import stamp


def sigmoid(x):
    return 1/(1+np.exp(-np.clip(x, -35, 35)))


def matrix(rows, features):
    return np.array([[r['features'][f] for f in features] for r in rows], dtype=float)


def targets(rows):
    return np.array([r['label']['value'] for r in rows], dtype=float)


def complete(rows, features):
    return [r for r in rows if all(r['features'].get(f) is not None and np.isfinite(r['features'][f]) for f in features)]


def purge(rows, boundary, embargo=0):
    cutoff = stamp(boundary-timedelta(days=embargo+1))
    return [r for r in rows if r['label']['end'] < str(boundary-timedelta(days=embargo)) and
            datetime.fromisoformat(r['label']['known_at']) <= cutoff]


def fit(rows, features, registry_id, alpha, task, top_k, iterations, check=lambda: None):
    if not rows: raise ValueError('INSUFFICIENT_TRAINING_ROWS')
    check(); x = matrix(rows, features); y = targets(rows)
    # Selection is computed on this exact training subset, never validation/OOS.
    ranks = []
    for j, f in enumerate(features):
        corr = abs(float(np.corrcoef(x[:, j], y)[0, 1])) if np.std(x[:, j]) > 1e-12 and np.std(y) > 1e-12 else 0.
        ranks.append((corr, f, j))
    selected = [j for _, _, j in sorted(ranks, key=lambda z: (-z[0], z[1]))[:top_k]]
    names = [features[j] for j in selected]; x = x[:, selected]
    means = x.mean(axis=0); scales = x.std(axis=0); scales[scales < 1e-12] = 1.
    z = (x-means)/scales; coef = np.zeros(len(names)); intercept = float(y.mean())
    if registry_id == 'momentum':
        if 'momentum_5' not in names: raise ValueError('MOMENTUM_BASELINE_REQUIRES_MOMENTUM_5')
    elif registry_id in ('ridge', 'ensemble'):
        centered = y-y.mean()
        coef = np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]), z.T@centered)
        if registry_id == 'ensemble': coef *= .5  # fixed equal ridge + training mean ensemble
    elif registry_id == 'logistic':
        if task != 'classification': raise ValueError('LOGISTIC_REQUIRES_DIRECTION_LABEL')
        intercept = float(np.log(np.clip(y.mean(), .001, .999)/(1-np.clip(y.mean(), .001, .999))))
        lr = 1/(.25*(float(np.linalg.norm(z, ord=2))**2/len(z)+1)+alpha/len(z))
        for _ in range(iterations):
            check(); residual = sigmoid(z@coef+intercept)-y
            coef -= lr*(z.T@residual+alpha*coef)/len(z); intercept -= lr*float(residual.mean())
    return ModelArtifact(registry_id=registry_id, features=names, means=means.tolist(), scales=scales.tolist(),
        coefficients=coef.tolist(), intercept=intercept, alpha=alpha, task=task,
        training_cutoff=max(datetime.fromisoformat(r['label']['known_at']) for r in rows), training_rows=len(rows))


def predict(model, rows, calibrated=False):
    model = ModelArtifact.model_validate(model)  # reject uploaded types, nonfinite or malformed coefficients
    x = matrix(rows, model.features); z = (x-np.array(model.means))/np.array(model.scales)
    if model.registry_id == 'momentum':
        values = x[:, model.features.index('momentum_5')]
        result = (values > 0).astype(float) if model.task == 'classification' else values
    else:
        result = z@np.array(model.coefficients)+model.intercept
        if model.registry_id == 'logistic': result = sigmoid(result)
        elif model.task == 'classification': result = np.clip(result, 0, 1)
    if calibrated and model.calibration:
        result = sigmoid(model.calibration[0]*result+model.calibration[1])
    return result


def calibrate(model, rows, iterations, check=lambda: None):
    y = targets(rows)
    if len(y) < 100 or np.sum(y == 1) < 20 or np.sum(y == 0) < 20:
        return model
    if min(datetime.fromisoformat(r['feature_at']) for r in rows) <= model.training_cutoff:
        raise ValueError('CALIBRATION_OVERLAPS_TRAINING_LABELS')
    p = predict(model, rows); a, b = 1., 0.
    for _ in range(iterations):
        check(); residual = sigmoid(a*p+b)-y
        a -= .3*float(np.mean(residual*p)); b -= .3*float(residual.mean())
    return model.model_copy(update={'calibration': (a, b), 'calibration_rows': len(rows)})


def score(y, prediction, task):
    if not len(y): return {'N': 0, 'mae': None, 'rmse': None, 'directional_accuracy': None}
    res = {'N': len(y), 'mae': float(np.mean(np.abs(y-prediction))),
        'rmse': float(np.sqrt(np.mean((y-prediction)**2))),
        'directional_accuracy': float(np.mean((y > .5) == (prediction > .5))) if task == 'classification'
                                  else float(np.mean((y > 0) == (prediction > 0)))}
    if task == 'classification':
        p = np.clip(prediction, 1e-9, 1-1e-9)
        res.update(brier=float(np.mean((p-y)**2)), log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))))
    return res


def folds(rows, protocol):
    sessions = sorted({r['session'] for r in rows})
    for n in range(protocol.max_folds):
        boundary = protocol.train_sessions+n*protocol.test_sessions
        test_start = boundary+protocol.embargo_sessions
        test_end = test_start+protocol.test_sessions
        if test_end > len(sessions): break
        start = 0 if protocol.mode == 'expanding' else boundary-protocol.train_sessions
        train_dates = set(sessions[start:boundary]); test_dates = set(sessions[test_start:test_end])
        test = [r for r in rows if r['session'] in test_dates]
        train_unpurged = [r for r in rows if r['session'] in train_dates]
        train = purge(train_unpurged, datetime.fromisoformat(sessions[test_start]).date(), protocol.embargo_sessions)
        yield n+1, train, test, len(train_unpurged)-len(train)


def evaluate(rows, definition, hypothesis, check=lambda: None, record_trial=lambda row: None):
    features = hypothesis.features; original_n = len(rows); rows = complete(rows, features)
    p = definition.validation; task = 'classification' if hypothesis.target == 'direction' else 'regression'
    if definition.model.registry_id == 'logistic' and task != 'classification': raise ValueError('LOGISTIC_REQUIRES_DIRECTION_LABEL')
    outputs = []; predictions = []; models = []; search = []
    for fold, train, test, purged in folds(rows, p):
        check()
        dates = sorted({r['session'] for r in train})
        if len(dates) <= p.calibration_sessions+p.inner_validation_sessions+10: continue
        calibration_start = datetime.fromisoformat(dates[-p.calibration_sessions]).date()
        cal = [r for r in train if r['session'] >= str(calibration_start)]
        core = purge([r for r in train if r['session'] < str(calibration_start)], calibration_start, p.embargo_sessions)
        core_dates = sorted({r['session'] for r in core})
        if len(core_dates) <= p.inner_validation_sessions+5: continue
        inner_start = datetime.fromisoformat(core_dates[-p.inner_validation_sessions]).date()
        inner_validation = [r for r in core if r['session'] >= str(inner_start)]
        inner_train = purge([r for r in core if r['session'] < str(inner_start)], inner_start, p.embargo_sessions)
        if min(len(core), len(inner_train)) < p.minimum_train_rows or not inner_validation: continue
        candidates = []
        for alpha in definition.model.alphas:
            check(); candidate = fit(inner_train, features, definition.model.registry_id, alpha, task,
                p.feature_selection.top_k, definition.model.max_iterations, check)
            metric = score(targets(inner_validation), predict(candidate, inner_validation), task)
            objective = metric['brier'] if task == 'classification' else metric['rmse']
            candidates.append((objective, alpha)); search.append({'fold': fold, 'alpha': alpha,
                'objective': objective, 'window': [inner_validation[0]['session'], inner_validation[-1]['session']],
                'stage': 'INNER_TRAINING_VALIDATION', 'train_N': len(inner_train), 'validation_N': len(inner_validation)})
            record_trial(search[-1])
        alpha = min(candidates)[1]
        model = fit(core, features, definition.model.registry_id, alpha, task, p.feature_selection.top_k, definition.model.max_iterations, check)
        if task == 'classification': model = calibrate(model, cal, definition.model.max_iterations, check)
        pred = predict(model, test, calibrated=True); y = targets(test)
        mean = fit(core, features, 'mean', alpha, task, len(features), 10, check)
        baseline = predict(mean, test)
        momentum = None
        if 'momentum_5' in features:
            momentum = predict(fit(core, features, 'momentum', alpha, task, len(features), 10, check), test)
        metric = score(y, pred, task); baseline_metric = score(y, baseline, task)
        objective = 'brier' if task == 'classification' else 'rmse'
        metric['baseline_skill'] = 1-metric[objective]/baseline_metric[objective] if baseline_metric[objective] else None
        outputs.append({'fold': fold, 'training_window': [core[0]['session'], core[-1]['session']],
            'inner_validation_window': [inner_validation[0]['session'], inner_validation[-1]['session']],
            'calibration_window': [cal[0]['session'], cal[-1]['session']], 'test_window': [test[0]['session'], test[-1]['session']],
            'purged_outer_rows': purged, 'embargo_sessions': p.embargo_sessions,
            'train_N': len(core), 'test_N': len(test), 'selected_alpha': alpha, 'selected_features': model.features,
            'metrics': metric, 'mean_baseline': baseline_metric,
            'momentum_baseline': score(y, momentum, task) if momentum is not None else None,
            'probability_status': 'EXPERIMENTAL_CALIBRATED' if model.calibration and len(test) >= 100 else 'PROBABILITY_UNAVAILABLE',
            'training_label_cutoff': model.training_cutoff.isoformat(), 'model': model.model_dump(mode='json')})
        models.append(model.model_dump(mode='json'))
        for r, prediction, b in zip(test, pred, baseline):
            predictions.append({'fold': fold, 'session': r['session'], 'symbol': r['symbol'], 'regime': r['regime'],
                'feature_at': r['feature_at'], 'label_end': r['label']['end'], 'target': r['label']['value'],
                'prediction': float(prediction), 'baseline': float(b)})
    return {'folds': outputs, 'predictions': predictions, 'models': models, 'search': search,
        'complete_case_N': len(rows), 'excluded_incomplete_N': original_n-len(rows)}
