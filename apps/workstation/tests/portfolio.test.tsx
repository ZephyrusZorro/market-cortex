import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PortfolioPane from '../components/PortfolioPane';

const id = 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa';
const manifest = '8b5bbfd6-699d-4c40-8f9f-3377604a61ea';
const context = { source_manifest_id: manifest, as_of: '2026-10-03T12:00:00Z',
  members: ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'].map((symbol) =>
    ({ symbol, instrument_id: id })) };
const portfolio = { portfolio_id:id, name:'SYNTHETIC_TEST_PORTFOLIO', base_currency:'USDT',
  capital:'10000', classification:'SYNTHETIC_TEST_PORTFOLIO', version:2,
  updated_at:context.as_of, positions:[{position_id:id, instrument_id:id, quantity:'1',
    average_cost:'95', native_currency:'USDT', opened_at:context.as_of, closed_at:null,
    thesis_id:null, invalidation_price:'90', target_price:null, note:'', source_type:'synthetic_fixture'}] };
const risk = { snapshot_id:id, portfolio_version:2, portfolio_classification:portfolio.classification,
  source_manifest_id:manifest, as_of:context.as_of, calculation_version:'portfolio_risk_daily_v1',
  capital:'10000', base_currency:'USDT', market_regime:'insufficient_data',
  portfolio_market_value:'100', unrealized_pnl:'5',
  positions:[{ position_id:id, symbol:'BTCUSDT', quantity:'1', native_currency:'USDT',
    reference_price:'100', market_value:'100', unrealized_pnl:'0', annualized_volatility:.4,
    atr14:5, drawdown:-.1, risk_to_invalidation:null, one_r:null, current_r:null,
    invalidation_price:null, freshness:'stale', thesis_id:null, warnings:['INVALIDATION_MISSING'] }],
  exposure:{ gross:'100', net:'100', by_instrument:{ BTCUSDT:'100' },
    by_currency:{ USDT:'100' }, by_strategy:{ unlinked:'100' },
    by_asset_class:{'crypto_spot:USDT':'100'}, by_provider:{binance:'100'},
    concentration_weights:{ BTCUSDT:'1' }, concentration_flags:['BTCUSDT'],
    concentration_threshold:'0.35' }, heat_amount:null, heat_percent:null,
  btc_sensitivity_proxy:'0.01', portfolio_drawdown:null, correlation_cluster_flags:[],
  correlations:[], coverage:1, price_freshness:'stale',
  feature_freshness:'stale', market_state_freshness:'unknown',
  warnings:['RISK_UNBOUNDED_OR_UNKNOWN','PRICE_OR_FEATURE_DATA_STALE'] };

describe('Phase 6 Portfolio & Risk workspace', () => {
  it('shows backend risk, unknown heat and explicit what-if assumptions', async () => {
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
      const path = new URL(url, 'http://local').pathname;
      const payload = path.endsWith('/risk/portfolios') ? {items:[portfolio]} :
        path.endsWith('/opportunities/theses') ? {items:[{thesis_id:id,symbol:'BTCUSDT',
          detector_id:'momentum',status:'WATCHING'}]} :
        path.endsWith('/versions') ? {items:[{version:2,action:'position_added',
          reason:'Synthetic fixture', recorded_at:context.as_of}]} :
        path.endsWith('/calculate') ? risk :
        path.endsWith('/theses/'+id+'/risk') ? {label:'HYPOTHETICAL_RESEARCH_OVERLAY',
          delta_gross_exposure:'100', delta_heat:null, delta_btc_sensitivity_proxy:'0.01',
          before:risk, after:risk, before_scenario:{portfolio_pnl:'-10'},
          after_scenario:{portfolio_pnl:'-20'}} :
        path.endsWith('/scenario') ? {portfolio_pnl:'-10', portfolio_change_percent:'-0.001',
          position_pnl:{[id]:'-10'}, coverage:1, warnings:['WHAT_IF_NOT_FORECAST']} : {};
      return {ok:true,status:200,json:async () => payload};
    });
    vi.stubGlobal('fetch', fetcher);
    render(<PortfolioPane context={context as never} />);
    expect(await screen.findByText('Position risk')).toBeInTheDocument();
    expect(screen.getByText('Portfolio heat')).toBeInTheDocument();
    expect(screen.getByText('Unrealized P/L')).toBeInTheDocument();
    expect(screen.getByText(/Portfolio drawdown: unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/RISK_UNBOUNDED_OR_UNKNOWN/)).toBeInTheDocument();
    expect(screen.getByText('unknown', { selector: '.metric-value' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'Run what-if'}));
    expect(await screen.findByText(/What-if P\/L/)).toBeInTheDocument();
    const request = fetcher.mock.calls.find(([url]) => String(url).endsWith('/scenario'))!;
    expect(JSON.parse(String(request[1]?.body)).scenario).toMatchObject({
      kind:'broad_crypto_shock', shocks:{BTCUSDT:'-0.1',ETHUSDT:'-0.1'} });
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/calculate'))).toBe(true));
    fireEvent.change(screen.getByRole('combobox', {name:'Thesis for overlay'}), {target:{value:id}});
    fireEvent.change(screen.getByRole('spinbutton', {name:'Hypothetical entry USDT'}),
      {target:{value:'100'}});
    fireEvent.click(screen.getByRole('button', {name:'Compare before / after'}));
    expect(await screen.findByText(/Concentration before:/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'Edit'}));
    expect(screen.getByRole('button', {name:'Save correction'})).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'Save correction'}));
    await waitFor(() => expect(fetcher.mock.calls.some(([url, options]) =>
      String(url).endsWith('/positions') && JSON.parse(String(options?.body)).action === 'update')).toBe(true));
    await waitFor(() => expect(screen.getByRole('button', {name:'Close research position'})).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', {name:'Close research position'}));
    await waitFor(() => expect(fetcher.mock.calls.some(([url, options]) =>
      String(url).endsWith('/positions') && JSON.parse(String(options?.body)).action === 'close')).toBe(true));
  });
});
