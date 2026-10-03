export type Mode = 'latest' | 'pinned' | 'historical';
export type ResearchSelection = { mode: Mode; manifestId?: string; asOf?: string };
export type Member = { symbol: string; instrument_id: string | null; currency: string | null; venue_id?: string;
  first_session: string | null; last_session: string | null; observed_sessions: number; status: string };
export type ManifestSummary = { manifest_id: string; parent_manifest_id: string | null; created_at: string };
export type Context = { universe_id: string; universe_label: string; source_manifest_id: string;
  head_manifest_id: string; as_of: string; evaluation_date: string | null; history_start: string | null;
  manifest: ManifestSummary & { schema_version: string; selection_policy_version: string };
  recent_manifests: ManifestSummary[]; members: Member[];
  providers: { provider_id: string; label: string; status: string; credential_state: string; interval: string }[];
  display: { primary_currency: string; secondary_currency: string; native_prices_only: boolean; timezone: string } };
export type FeatureValue = { feature_id: string; name: string; value: number | null; reason: string | null;
  unit: string; version: string; calculation_version: string; parameters: Record<string, number>;
  observed_sessions: number; expected_sessions: number; freshness: string; source_manifest_id: string };
export type OverviewItem = Member & { session_date: string; close: number | null; observation_id: string | null;
  quality: string; freshness: string; features: Record<string, FeatureValue> };
export type Dimension = { name: string; category: string; metrics: Record<string, number | null>;
  evidence_refs: string[]; scope: string; timeframe: string; source_manifest_id: string;
  rule_version: string; eligible_members: number; total_members: number; freshness: string; unknown_reason: string | null };
export type BreadthMetric = { eligible: number; positive: number; percentage: number | null; missing_members: string[] };
export type Breadth = { snapshot_id: string; universe_id: string; session_date: string; observed_members: number;
  total_members: number; above_sma: BreadthMetric; positive_lookback: BreadthMetric; new_high: BreadthMetric;
  new_low: BreadthMetric; advancing: number; declining: number; unchanged: number; advance_decline_eligible: number };
export type MarketState = { snapshot_id: string; source_manifest_id: string; calculation_version: string;
  request: { as_of: string; evaluation_date: string; history_start: string };
  dimensions: Dimension[]; breadth: Breadth | null;
  regime: { category: string; rules_fired: string[]; evidence_refs: string[]; rule_version: string;
    unknown_reason: string | null }; missing_members: string[] };
export type Overview = { context: Context; items: OverviewItem[]; state: MarketState | null; reason?: string };
export type ChartBar = { session_date: string; open: number; high: number; low: number; close: number;
  volume: number | null; observation_id: string; source_batch_id: string; available_at: string | null;
  quality: string; currency: string };
export type ChartFeature = { feature_id: string; unit: string; parameters: Record<string, number>; version: string;
  calculation_version: string; freshness: string; observed_sessions: number; expected_sessions: number;
  points: { session_date: string; value: number | null; reason: string | null }[] };
export type InstrumentView = { context: Context; instrument: Member; from: string; to: string;
  bars: ChartBar[]; features: Record<string, ChartFeature>; freshness: string; missing_sessions: string[] };
export type FeatureDefinition = { name: string; version: string; calculation_version: string;
  calculation_code_hash: string; description: string; required_inputs: string[];
  parameter_defaults: Record<string, number>; min_history: string; default_min_history: number;
  unit: string; supported_intervals: string[] };
export type FeatureSeries = { feature_id: string; definition: FeatureDefinition; source_manifest_id: string;
  as_of?: string; request: { as_of: string }; resolved_parameters: Record<string, number>;
  expected_sessions: number; observed_sessions: number; freshness: string; missing_sessions: string[];
  points: { session_date: string; value: number | null; reason: string | null;
    observation_id: string | null; input_quality: string | null }[] };
export type MatrixCell = { target: string; reference: string; value: number | null; count: number;
  coverage: number; missingness: number; stability: number | null; reason: string | null;
  result_id: string; version: string };
export type Comparison = { context: Context; members: string[]; window: number; from: string; to: string;
  alignment_policy: string; performance: Record<string, { session_date: string; value: number | null }[]>;
  matrix: MatrixCell[][] };
export type ManifestDetail = { manifest_id: string; parent_manifest_id: string | null; created_at: string;
  schema_version: string; selection_policy_version: string; file_count: number; rows_in_files: number;
  files: { sha256: string; rows: number; venue_id: string; min_event_at: string; max_event_at: string }[];
  providers: { provider_id: string; source_batches: number; observations: number }[];
  storage: { referenced: number; missing: string[]; corrupt: string[]; unreferenced: string[]; staged_count: number } };

export class ApiError extends Error {
  constructor(public code: string, public status: number) { super(code); }
}

export function contextParams(selection: ResearchSelection): URLSearchParams {
  const params = new URLSearchParams();
  if (selection.mode !== 'latest' && selection.manifestId) params.set('manifest_id', selection.manifestId);
  if (selection.mode === 'historical' && selection.asOf) params.set('as_of', selection.asOf);
  return params;
}

export function pinnedParams(context: Context): URLSearchParams {
  return new URLSearchParams({ manifest_id: context.source_manifest_id, as_of: context.as_of });
}

export function appendParams(base: URLSearchParams, values: Record<string, string | number | undefined>): URLSearchParams {
  const result = new URLSearchParams(base);
  for (const [key, value] of Object.entries(values)) if (value !== undefined) result.set(key, String(value));
  return result;
}

export async function getJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const url = `/api/v1/${path}${params?.size ? `?${params}` : ''}`;
  let response: Response;
  try { response = await fetch(url, { cache: 'no-store' }); }
  catch { throw new ApiError('BACKEND_UNAVAILABLE', 503); }
  let payload: unknown;
  try { payload = await response.json(); } catch { throw new ApiError('INVALID_BACKEND_RESPONSE', response.status); }
  if (!response.ok) {
    const body = payload as { code?: string; detail?: { code?: string } };
    throw new ApiError(body.detail?.code ?? body.code ?? 'REQUEST_FAILED', response.status);
  }
  return payload as T;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api/v1/${path}`, { method: 'POST', cache: 'no-store',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
  catch { throw new ApiError('BACKEND_UNAVAILABLE', 503); }
  let payload: unknown;
  try { payload = await response.json(); } catch { throw new ApiError('INVALID_BACKEND_RESPONSE', response.status); }
  if (!response.ok) {
    const result = payload as { code?: string; detail?: { code?: string } };
    throw new ApiError(result.detail?.code ?? result.code ?? 'REQUEST_FAILED', response.status);
  }
  return payload as T;
}

export function shortId(value: string | null | undefined): string { return value ? `${value.slice(0, 8)}…${value.slice(-4)}` : '—'; }
export function number(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value);
}
export function percent(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`;
}
export function category(name: string): string { return name.replaceAll('_', ' '); }
