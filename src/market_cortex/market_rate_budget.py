"""Conservative process-shared budgets for independent market-data GETs only.

All transports in one process share the provider budget, including retries.
This is not cross-process or account-wide coordination. Deployment must keep
one broker service per account; external applications consume separate quotas.
"""
from collections import deque
from dataclasses import dataclass
import threading
import time

from .providers import ProviderFailure


@dataclass(frozen=True)
class RequestPolicy:
    windows: tuple[tuple[float, int], ...]
    minimum_spacing: float
    maximum_wait: float = 2.0


POLICIES = {
    'upstox':RequestPolicy(((60,40),(1800,1000)),1.0),
    'alpaca':RequestPolicy(((60,60),),1.0),
    'binance':RequestPolicy(((60,30),),1.0),
}
HOST_PROVIDER = {
    'api.upstox.com':'upstox', 'data.alpaca.markets':'alpaca',
    'api.alpaca.markets':'alpaca', 'paper-api.alpaca.markets':'alpaca',
    'data-api.binance.vision':'binance',
}


class RequestBudget:
    def __init__(self, policy, *, clock=time.monotonic, sleep=time.sleep):
        self.policy, self.clock, self.sleep = policy, clock, sleep
        self.attempts, self.lock = deque(), threading.Lock()
        self.cooldown_until = 0.0

    def acquire(self):
        with self.lock:
            now = self.clock()
            horizon = max(window for window,_ in self.policy.windows)
            while self.attempts and self.attempts[0]<=now-horizon:
                self.attempts.popleft()
            ready = max(now,self.cooldown_until)
            if self.attempts:
                ready = max(ready,self.attempts[-1]+self.policy.minimum_spacing)
            for window,limit in self.policy.windows:
                within = [at for at in self.attempts if at>now-window]
                if len(within)>=limit:
                    ready = max(ready,within[-limit]+window)
            wait = ready-now
            if wait>self.policy.maximum_wait:
                raise ProviderFailure('LOCAL_PROVIDER_RATE_BUDGET_EXHAUSTED',retryable=True)
            if wait>0:
                self.sleep(wait)
            self.attempts.append(self.clock())

    def cooldown(self, seconds):
        with self.lock:
            self.cooldown_until = max(self.cooldown_until,self.clock()+seconds)


_BUDGETS = {provider:RequestBudget(policy) for provider,policy in POLICIES.items()}


def budget_for(host):
    provider = HOST_PROVIDER.get(host)
    if provider is None:
        raise ProviderFailure('INDEPENDENT_RATE_POLICY_REQUIRED')
    return _BUDGETS[provider]
