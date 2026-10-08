"""Loopback Host and Origin checks, including DNS-rebinding protection."""
from urllib.parse import urlsplit

LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def local_request_allowed(host: str, origin: str | None, *, test_client: bool = False) -> bool:
    try:
        target = urlsplit("http://" + host)
        _ = target.port
        allowed = LOOPBACK | ({"testserver"} if test_client else set())
        if (target.hostname not in allowed or target.username or target.password
                or target.path or target.query or target.fragment):
            return False
        if origin is None:
            return True  # local CLI/server clients do not send browser Origin
        source = urlsplit(origin)
        _ = source.port
        return (source.scheme == "http" and source.hostname in LOOPBACK
                and not source.username and not source.password
                and source.path in {"", "/"} and not source.query and not source.fragment)
    except ValueError:
        return False
