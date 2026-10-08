'use client';
import { useEffect, useState } from 'react';
import { getJson } from '@/lib/api';

type Status = { environment: string; expected_closed_session: string; items: { instrument_id: string; last_session: string; freshness: string }[];
  jobs: { job_id: string; state: string; attempts: number; error_code: string | null; symbol: string; next_attempt_at: string;
    result?: { completed_at: string; stored: number; duplicates: number; quarantined: number } | null }[] };

export default function OperationalStatus() {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    getJson<Status>('operations/status').then(value => { if (active) { setData(value); setError(''); } })
      .catch(() => { if (active) setError('Operational diagnostics unavailable. Check the local API and database.'); });
    return () => { active = false; };
  }, [revision]);
  return <section className="panel mb14"><div className="panel-head"><div><h2>Daily refresh operations</h2>
    <span className="sub">Latest catalog status · independent of pinned historical research</span></div>
    <button className="btn" onClick={() => setRevision(v => v + 1)}>Refresh diagnostics</button></div>
    <div className="panel-body">{error ? <p role="alert">{error}</p> : !data ? <p>Loading operational diagnostics…</p> : <>
      <p>{data.environment} · Expected closed Binance UTC session: {data.expected_closed_session} · {data.items.filter(x => x.freshness === 'FRESH').length}/{data.items.length} instruments fresh.</p>
      <p className="sub">Scheduling is optional. This screen reads recorded jobs; it does not start ingestion or install a background service.</p>
      {!data.jobs.length ? <p>No daily refresh jobs recorded in this environment.</p> : <table><thead><tr><th>Symbol</th><th>State</th><th>Attempts</th><th>Last success / retry</th><th>Stored / duplicate / quarantine</th><th>Diagnostic</th></tr></thead>
        <tbody>{data.jobs.slice(0, 10).map(j => <tr key={j.job_id}><td>{j.symbol}</td><td>{j.state}</td><td>{j.attempts}</td>
          <td>{j.result?.completed_at ?? j.next_attempt_at}</td><td>{j.result ? `${j.result.stored} / ${j.result.duplicates} / ${j.result.quarantined}` : 'Unavailable'}</td>
          <td>{j.error_code ?? 'None'}</td></tr>)}</tbody></table>}
    </>}</div></section>;
}
