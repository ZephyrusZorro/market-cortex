"""Launch the existing API with an explicitly validated environment profile."""
import argparse
from pathlib import Path
import uvicorn
from .api import create_app
from .operations import load_profile, preflight


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    if not 1024 <= args.port <= 65535:
        p.error('PORT_OUT_OF_RANGE')
    _, settings = load_profile(args.profile)
    report = preflight(settings)
    if report['status'] != 'VALIDATED':
        raise SystemExit('PREFLIGHT_FAILED')
    uvicorn.run(create_app(settings), host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
