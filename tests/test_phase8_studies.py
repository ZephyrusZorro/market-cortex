"""Frozen temporal searches, seeded path research and cache identities."""
from datetime import date,datetime,timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from market_cortex.quant import QuantService
from market_cortex.quant_contracts import (CompareRequest,GridRequest,MonteCarloRequest,StrategyParameters,
    WalkForwardDefinition)
from market_cortex.quant_store import digest
from test_phase8_quant import definition,synthetic_source


class MemoryStore:
    def __init__(self):
        self.rows={};self.hashes={}
    def save(self,kind,value,content_hash=None,artifact_id=None):
        from uuid import uuid5,NAMESPACE_URL
        key=artifact_id or uuid5(NAMESPACE_URL,kind+(content_hash or digest(value)))
        self.rows[key]=value;self.hashes[kind,content_hash or digest(value)]=value
        return key
    def get(self,key,kind=None,as_of=None):
        return self.rows[key]
    def by_hash(self,kind,value):
        return self.hashes.get((kind,value))


@pytest.fixture(scope="module")
def service():
    s=QuantService(SimpleNamespace(dsn=""),"PILOT_TEST")
    s.store=MemoryStore()
    source=synthetic_source(150)
    s.source=lambda d:(source,digest(source))
    d=definition(manifest_id=UUID(source["manifest_id"]),source_as_of=datetime(2025,7,1,tzinfo=timezone.utc),
        start=date(2025,2,25),end=date(2025,5,29),parameters=StrategyParameters(holding_sessions=3,stop_fraction=.1),
        replay_policy="AS_RECORDED",classification="SYNTHETIC_TEST")
    return s,d,source


def test_replay_hash_after_new_head_and_cost_version_identity(service):
    s,d,source=service
    original=s.run(d,source)
    s.catalog.head=lambda:UUID(int=1234)
    assert s.replay(original.run_id)["status"]=="MATCH"
    changed=s.run(d.model_copy(update={"costs":d.costs.model_copy(update={"slippage_bps":50})}),source)
    assert changed.run_id!=original.run_id and changed.manifest.input_hash!=original.manifest.input_hash
    assert changed.metrics["total_return"]<=original.metrics["total_return"]


def test_grid_whole_surface_walk_forward_no_overlap_parameter_freeze(service):
    s,d,source=service
    grid=GridRequest(definition=d,holding_sessions=[2,4],stop_fraction=[.08])
    result=s.sensitivity(grid)
    assert len(result["result"]["rows"])==2
    wf=s.walk_forward(WalkForwardDefinition(definition=d,holding_sessions=[2,4],stop_fraction=[.08],
        train_sessions=60,validation_sessions=10,step_sessions=10,max_folds=2))
    folds=wf["result"]["folds"]
    assert len(folds)==2 and wf["result"]["parameter_combinations_tested"]==4
    for f in folds:
        assert f["train_end"]<f["validation_start"]
        training=[s.store.get(UUID(row["run_id"])) for row in f["search_results"]]
        assert all(r["definition"]["end"]==f["train_end"] for r in training)
        assert all(r["definition"]["start"]==f["train_start"] for r in training)
        chosen=max(f["search_results"],key=lambda row:row["metrics"]["total_return"])
        assert f["selected_parameters"]==chosen["parameters"]
        oos=s.store.get(UUID(f["oos_run_id"]))
        assert oos["definition"]["parameters"]==f["selected_parameters"]
    assert folds[0]["validation_end"]<folds[1]["validation_start"]


def test_seeded_monte_carlo_permutation_terminal_invariant_and_comparison(service):
    s,d,source=service
    run=s.run(d,source)
    assert len(run.trades)>=2
    assert {'overall_regime','trend','volatility','market_participation'}<=set(row['dimension'] for row in run.regime_performance)
    request=MonteCarloRequest(run_id=run.run_id,seed=123,simulations=40)
    a=s.monte_carlo(request);b=s.monte_carlo(request)
    assert a["result"]==b["result"] and a["study_id"]==b["study_id"]
    c=s.monte_carlo(request.model_copy(update={"method":"permutation"}))
    p=c["result"]["terminal_return"]
    assert max(p.values())==pytest.approx(min(p.values()))
    second=s.run(d.model_copy(update={"parameters":d.parameters.model_copy(update={"holding_sessions":7})}),source)
    comparison=s.compare(CompareRequest(run_ids=[run.run_id,second.run_id]))
    assert comparison["result"]["directly_comparable"]
    assert all("N" in row["metrics"] for row in comparison["result"]["rows"])


def test_robustness_is_sample_labelled_never_auto_supported(service):
    s,d,_=service
    result=s.robustness(d)
    assert {row["dimension"] for row in result["result"]["rows"]}>={"asset:BTCUSDT","cost:stress","timing:close","timing:delay"}
    assert result["result"]["classification"] in ("INSUFFICIENT_EVIDENCE","MIXED","FRAGILE")
