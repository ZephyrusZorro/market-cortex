"""Optional explicit source-fetch scope for a future approved installation.

Independent reads remain unrestricted; fetch approval never grants database
access, streaming, trading, scheduling or a wider provider-native identity.
"""
from dataclasses import dataclass
from datetime import datetime

from .contracts import utc
from .providers import ProviderFailure


@dataclass(frozen=True)
class FetchWindow:
    provider: str
    native_id: str
    interval: str
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.provider not in {'binance','upstox','alpaca'} or not self.native_id or self.interval!='1d':
            raise ValueError('invalid daily source scope')
        if utc(self.start)>=utc(self.end):raise ValueError('invalid source window')


@dataclass(frozen=True)
class FetchScope:
    windows: tuple[FetchWindow,...]

    def require(self,provider,native_id,interval,start,end):
        try:start,end=utc(start),utc(end)
        except ValueError:raise ProviderFailure('SOURCE_FETCH_NOT_APPROVED') from None
        if start>=end or not any(
                (w.provider,w.native_id,w.interval)==(provider,native_id,interval) and
                utc(w.start)<=start and end<=utc(w.end) for w in self.windows):
            raise ProviderFailure('SOURCE_FETCH_NOT_APPROVED')
