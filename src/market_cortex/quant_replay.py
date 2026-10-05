"""Frozen evidence catalog: recorded replay or explicitly assumed reconstruction.

The latter NEVER changes source envelopes and is not historical observed knowledge.
Only first revisions are eligible; a corrected initial record is unavailable.
"""
from datetime import date, datetime, time, timedelta, timezone
from dataclasses import replace
from uuid import UUID

from .contracts import Bar, Instrument, IdentifierMapping, Venue
from .database import connect
from .identity import IdentityRegistry, IdentityError
from .opportunity import OpportunityService
from .storage import filter_known_identity, logical_key, visible_bars
from .calendar import SessionCalendar
from .market_state import PILOT_SYMBOLS
from .market_state import MarketStateEngine
from .features import FeatureEngine
from .quality import freshness


def capture(catalog, manifest_id, as_of):
    with connect(catalog.dsn) as c:
        chain = c.execute("""WITH RECURSIVE chain AS (
            SELECT manifest_id,parent_manifest_id,created_at FROM dataset_manifests WHERE manifest_id=%s
            UNION ALL SELECT m.manifest_id,m.parent_manifest_id,m.created_at FROM dataset_manifests m
            JOIN chain ON m.manifest_id=chain.parent_manifest_id) SELECT manifest_id,created_at FROM chain""",(manifest_id,)).fetchall()
    if not chain:
        raise LookupError("MANIFEST_NOT_FOUND")
    if dict(chain)[manifest_id] > as_of:
        raise ValueError("SOURCE_MANIFEST_NOT_AVAILABLE")
    instruments,mappings=catalog.load_identity()
    artifacts=catalog.artifacts_for(manifest_id)
    bars=[]
    for a in artifacts:
        if catalog.artifacts.verify(catalog.artifacts.root/a.relative_path)!=a.content_hash:
            raise ValueError("SOURCE_CHECKSUM_MISMATCH")
        bars.extend(catalog.artifacts.read_bars(a))
    selected=[b for b in bars if b.envelope.provider_id=="binance" and b.interval=="P1D"
              and b.envelope.adjustment_basis=="raw" and b.envelope.ingested_at<=as_of]
    if not selected:
        raise LookupError("NO_SOURCE_BARS")
    with connect(catalog.dsn) as c:
        observation_manifests=dict(c.execute("SELECT observation_id,manifest_id FROM observations WHERE observation_id=ANY(%s)",
                                            ([b.envelope.observation_id for b in selected],)).fetchall())
    start=min(b.start_at for b in selected)-timedelta(days=2)
    end=max(b.end_at for b in selected)+timedelta(days=2)
    calendars={}
    for venue_id in {b.envelope.venue_id for b in selected}:
        cal=catalog.load_calendar(venue_id,start,end)
        if cal.venue.session_kind!="24x7":
            raise ValueError("QUANT_REQUIRES_VERIFIED_24X7_CRYPTO_CALENDAR")
        calendars[venue_id]={"venue":cal.venue.model_dump(mode="json"),"calendar_id":cal.calendar_id,"version":cal.version}
    from .intelligence_store import ContextStore
    contextual = ContextStore(catalog).freeze(as_of)
    return {"manifest_id":str(manifest_id),"source_as_of":as_of.isoformat(), 'contextual': contextual,
            "manifest_times":{str(k):v.isoformat() for k,v in chain},
            "observation_manifests":{str(k):str(v) for k,v in observation_manifests.items()},
            "files":[{"path":a.relative_path,"hash":a.content_hash} for a in artifacts],
            "instruments":[i.model_dump(mode="json") for i in instruments],
            "mappings":[m.model_dump(mode="json") for m in mappings],"calendars":calendars,
            "bars":[b.model_dump(mode="json") for b in sorted(selected,key=lambda b:str(b.envelope.observation_id))]}


class ReplayCatalog:
    def __init__(self, source: dict, policy: str, lag: int=60):
        self.source=source
        self.policy=policy
        self.lag=lag
        self.instruments=[Instrument.model_validate(i) for i in source["instruments"]]
        self.mappings=[IdentifierMapping.model_validate(m) for m in source["mappings"]]
        self.records=[Bar.model_validate(b) for b in source["bars"]]
        ids={b.envelope.instrument_id for b in self.records}
        if any(i.asset_class!="crypto_spot" or i.trading_currency!="USDT" for i in self.instruments if i.instrument_id in ids):
            raise ValueError("QUANT_PILOT_REQUIRES_RAW_USDT_CRYPTO_SPOT; EQUITY_ACTIONS_DEFERRED")
        self.pinned=UUID(source["manifest_id"])
        self.manifest_times={k:datetime.fromisoformat(v) for k,v in source["manifest_times"].items()}
        self.originals={}
        self._calendars={}
        for b in sorted(self.records,key=lambda b:(b.envelope.ingested_at,str(b.envelope.observation_id))):
            if b.envelope.supersedes_observation_id is None and b.envelope.quality_state=="valid":
                self.originals.setdefault(logical_key(b),b)
        self.by_instrument={i.instrument_id:[b for b in self.records if b.envelope.instrument_id==i.instrument_id]
                            for i in self.instruments}

    def head(self):
        return self.pinned

    def load_identity(self):
        if self.policy=="AS_RECORDED":
            return self.instruments,self.mappings
        # An assumed mapping is a separate in-memory view. Actual discovery is frozen in source.
        return self.instruments,[m.model_copy(update={"available_at":m.valid_from}) for m in self.mappings]

    def load_calendar(self, venue_id, start, end):
        item=self.source["calendars"][venue_id]
        if venue_id not in self._calendars:
            self._calendars[venue_id]=SessionCalendar(Venue.model_validate(item["venue"]),item["calendar_id"],item["version"])
        return self._calendars[venue_id]

    def bars(self, *, instrument_id, start, end, as_of, adjustment_basis="raw", provider_id=None, manifest_id=None):
        if manifest_id is not None and manifest_id!=self.pinned:
            raise ValueError("REPLAY_MANIFEST_MISMATCH")
        if adjustment_basis!="raw" or provider_id not in (None,"binance"):
            raise ValueError("REPLAY_RAW_BINANCE_ONLY")
        if self.policy=="AS_RECORDED":
            records=[b for b in self.by_instrument.get(instrument_id,[]) if b.envelope.ingested_at<=as_of
                     and b.end_at<=as_of and self.manifest_times.get(str(self._manifest(b)),datetime.max.replace(tzinfo=timezone.utc))<=as_of]
            selected=visible_bars(records,instrument_id=instrument_id,start=start,end=end,as_of=as_of,
                                  adjustment_basis=adjustment_basis,provider_id=provider_id)
            return self.pinned,filter_known_identity(selected,self.instruments,self.mappings,as_of)
        records=[b for b in self.originals.values() if b.envelope.instrument_id==instrument_id
                 and start<=b.start_at<end and b.end_at+timedelta(seconds=self.lag)<=as_of and b.envelope.is_final]
        identities,mappings=self.load_identity()
        return self.pinned,filter_known_identity(sorted(records,key=lambda b:b.start_at),identities,mappings,as_of)

    def _manifest(self,b):
        # First immutable file membership is captured explicitly by source preparation.
        return self.source.get("observation_manifests",{}).get(str(b.envelope.observation_id),self.pinned)

    def execution_bars(self, definition):
        # Later observations are outcome data, never passed to a historical detector.
        result={s:{} for s in definition.symbols}
        registry=IdentityRegistry(*self.load_identity())
        for symbol in definition.symbols:
            for day in days(definition.start,definition.end):
                at=datetime.combine(day,time.min,timezone.utc)
                try:
                    i=registry.resolve(provider_id="binance",identifier_type="exchange_pair",identifier_value=symbol,
                                       at=at,known_at=definition.source_as_of)
                except IdentityError:
                    continue
                cutoff=at+timedelta(days=1,seconds=self.lag)
                if self.policy=="AS_RECORDED":
                    _,bars=self.bars(instrument_id=i.instrument_id,start=at,end=at+timedelta(days=1),
                                     as_of=min(cutoff,definition.source_as_of),manifest_id=self.pinned)
                else:
                    _,bars=self.bars(instrument_id=i.instrument_id,start=at,end=at+timedelta(days=1),as_of=cutoff)
                if bars:
                    result[symbol][day]=bars[-1]
        return result


def days(start: date, end: date):
    return [start+timedelta(days=i) for i in range((end-start).days+1)]


class ReplayOpportunityService(OpportunityService):
    """Only context discovery changes. All rules/features/state use Phase 2/5 code."""
    def __init__(self,catalog):
        super().__init__(catalog)
        self.features=ReplayFeatureEngine(catalog)
    def _context(self, request):
        cutoff=request.as_of
        registry=IdentityRegistry(*self.catalog.load_identity())
        members=[]
        self.visible_inputs={}
        self.last_state=None
        for symbol in PILOT_SYMBOLS:
            try:
                instrument=registry.resolve(provider_id="binance",identifier_type="exchange_pair",identifier_value=symbol,
                                            at=cutoff,known_at=cutoff)
            except IdentityError:
                members.append({"symbol":symbol,"instrument_id":None,"first_session":None,"last_session":None})
                continue
            _,bars=self.catalog.bars(instrument_id=instrument.instrument_id,
                start=cutoff-timedelta(days=5000),end=cutoff,as_of=cutoff,manifest_id=self.catalog.pinned)
            self.visible_inputs[symbol]=bars
            members.append({"symbol":symbol,"instrument_id":str(instrument.instrument_id),
                "first_session":str(bars[0].session_date) if bars else None,
                "last_session":str(bars[-1].session_date) if bars else None})
        first=[m["first_session"] for m in members if m["first_session"]]
        last=[m["last_session"] for m in members if m["last_session"]]
        return {"members":members,"evaluation_date":min(last) if len(last)==5 else None,
                "history_start":min(first) if first else None},self.catalog.pinned,cutoff

    def compute_state(self,request):
        engine=MarketStateEngine(self.catalog)
        engine.features=self.features
        self.last_state=engine.compute(request)
        return self.last_state


class ReplayFeatureEngine(FeatureEngine):
    """Canonical numerical engine; reconstruction freshness has an explicit assumption.

    Source bars and FeaturePoint timestamps remain original. A transient proxy is
    used only by the existing freshness classifier, never returned as evidence.
    """
    def load(self,**kwargs):
        series=super().load(**kwargs)
        if self.catalog.policy=="HISTORICAL_RECONSTRUCTION":
            latest=next((b for b in reversed(series.bars) if b),None)
            proxy=None
            if latest:
                proxy=latest.model_copy(update={"envelope":latest.envelope.model_copy(update={
                    "available_at":latest.end_at+timedelta(seconds=self.catalog.lag),
                    "availability_basis":"conservative_proxy"})})
            series=replace(series,freshness_state=freshness(latest=proxy,as_of=series.as_of,calendar=series.calendar))
        return series
