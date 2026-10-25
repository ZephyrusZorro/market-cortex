'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChartBar, ChartFeature } from '@/lib/api';

type ChartOptions = Record<string, unknown>;

function CanvasChart({ option, height = 320, label }: { option: ChartOptions; height?: number; label: string }) {
  const element = useRef<HTMLDivElement>(null);
  const active = useRef<import('echarts').ECharts | undefined>(undefined);
  const latest = useRef(option);
  useEffect(() => {
    let disposed = false;
    let chart: import('echarts').ECharts | undefined;
    let observer: ResizeObserver | undefined;
    import('echarts').then((echarts) => {
      if (disposed || !element.current) return;
      chart = echarts.init(element.current, undefined, { renderer: 'canvas' });
      active.current = chart;
      chart.setOption(latest.current);
      observer = new ResizeObserver(() => chart?.resize());
      observer.observe(element.current);
    });
    return () => { disposed = true; observer?.disconnect(); chart?.dispose(); active.current=undefined; };
  }, []);
  useEffect(()=>{latest.current=option;active.current?.setOption(option);},[option]);
  return <div ref={element} role="img" aria-label={label} style={{ width: '100%', height }} />;
}

const palette = { text: '#98aaa8', grid: '#263431', up: '#7ccfa8', down: '#e68f82',
  cyan: '#78b9c5', lime: '#d2de9a', orange: '#e6b97a', violet: '#a7a0cc' };

export function SourcePriceChart({bars}:{bars:ChartBar[]}) {
  const [windowSize,setWindowSize]=useState<number|null>(null);
  const [offset,setOffset]=useState(0);
  const size=Math.min(windowSize ?? bars.length,bars.length);
  const boundedOffset=Math.min(offset,Math.max(0,bars.length-size));
  const visible=useMemo(()=>bars.slice(bars.length-boundedOffset-size,bars.length-boundedOffset),[bars,boundedOffset,size]);
  const option=useMemo(()=>({animation:false,backgroundColor:'transparent',
    tooltip:{trigger:'axis',axisPointer:{type:'cross'},backgroundColor:'#182320',textStyle:{color:'#e3e9df'}},
    grid:[{left:45,right:75,top:20,height:'65%'},{left:45,right:75,top:'72%',height:'16%'}],
    xAxis:[0,1].map(gridIndex=>({type:'category',gridIndex,data:visible.map(b=>b.session_date),axisLabel:{color:palette.text,show:gridIndex===1},axisLine:{lineStyle:{color:palette.grid}}})),
    yAxis:[0,1].map(gridIndex=>({type:'value',gridIndex,scale:true,position:'right',axisLabel:{color:palette.text},splitLine:{lineStyle:{color:palette.grid}}})),
    series:[{name:'Source OHLC',type:'candlestick',data:visible.map(b=>[b.open,b.close,b.low,b.high]),itemStyle:{color:palette.up,color0:palette.down,borderColor:palette.up,borderColor0:palette.down}},
      {name:'Source volume',type:'bar',xAxisIndex:1,yAxisIndex:1,data:visible.map(b=>({value:b.volume,itemStyle:{color:b.close>=b.open?palette.up:palette.down}}))}]}),[visible]);
  return <div>
    <div aria-label="Chart navigation">
      <button disabled={size<=2} onClick={()=>setWindowSize(Math.max(2,Math.floor(size/2)))}>Zoom in</button>{' '}
      <button disabled={size===bars.length} onClick={()=>{const next=Math.min(bars.length,size*2);setWindowSize(next);setOffset(Math.min(boundedOffset,bars.length-next));}}>Zoom out</button>{' '}
      <button disabled={boundedOffset>=bars.length-size} onClick={()=>setOffset(Math.min(bars.length-size,boundedOffset+Math.max(1,Math.floor(size/4))))}>Pan earlier</button>{' '}
      <button disabled={boundedOffset===0} onClick={()=>setOffset(Math.max(0,boundedOffset-Math.max(1,Math.floor(size/4))))}>Pan later</button>{' '}
      <button onClick={()=>{setWindowSize(null);setOffset(0);}}>Reset view</button>
    </div>
    <p aria-label="Chart viewport">{visible.length} of {bars.length} source candles · {visible[0]?.session_date} through {visible.at(-1)?.session_date}</p>
    <CanvasChart option={option} height={600} label="Provider OHLC candlesticks and volume with pan and zoom"/>
  </div>;
}

export function QuantChart({points,benchmarkAvailable=true}:{points:{session:string;net:number;gross:number;benchmark:number;drawdown:number}[];benchmarkAvailable?:boolean}) {
  const option=useMemo(()=>({animation:false,backgroundColor:'transparent',
    legend:{top:5,left:65,data:['Net after costs','Gross same quantities',...(benchmarkAvailable?['Gross benchmark']:[]),'Drawdown'],textStyle:{color:palette.text,fontSize:11}},
    tooltip:{trigger:'axis',backgroundColor:'#182320',borderColor:palette.grid,textStyle:{color:'#e3e9df'}},grid:[{left:65,right:25,top:45,height:'58%'},{left:65,right:25,top:'76%',height:'15%'}],
    xAxis:[0,1].map(gridIndex=>({type:'category',gridIndex,data:points.map(p=>p.session),axisLabel:{color:palette.text,show:gridIndex===1,fontSize:10}})),
    yAxis:[0,1].map(gridIndex=>({type:'value',gridIndex,scale:true,splitNumber:gridIndex===1?3:5,
      axisLabel:{color:palette.text,fontSize:10,formatter:(v:number)=>gridIndex===1?`${(v*100).toFixed(0)}%`:Intl.NumberFormat('en').format(v)},splitLine:{lineStyle:{color:palette.grid}}})),
    series:[['Net after costs','net',palette.up],['Gross same quantities','gross',palette.cyan],['Gross benchmark','benchmark',palette.orange],['Drawdown','drawdown',palette.down]].filter(([,key])=>benchmarkAvailable||key!=='benchmark').map(([name,key,color])=>({
      name,type:'line',showSymbol:false,xAxisIndex:key==='drawdown'?1:0,yAxisIndex:key==='drawdown'?1:0,
      data:points.map(p=>p[key as keyof typeof p]),lineStyle:{color,width:1.5},itemStyle:{color}}))}),[points,benchmarkAvailable]);
  return <CanvasChart option={option} height={400} label={`Quant equity: net, gross${benchmarkAvailable?', benchmark':''} and drawdown`}/>;
}

export function PriceChart({ bars, features, visibleFrom, visibleTo }: {
  bars: ChartBar[]; features: Record<string, ChartFeature>; visibleFrom?: string; visibleTo?: string
}) {
  const option = useMemo(() => {
    const dates = bars.map((bar) => bar.session_date);
    const byDate = (key: string) => {
      const lookup = new Map(features[key]?.points.map((point) => [point.session_date, point.value]) ?? []);
      return dates.map((date) => lookup.get(date) ?? null);
    };
    const xAxis = [0, 1, 2, 3].map((gridIndex) => ({ type: 'category', gridIndex, data: dates,
      boundaryGap: true, axisLine: { lineStyle: { color: palette.grid } },
      axisLabel: { color: palette.text, fontSize: 10, show: gridIndex === 3 },
      axisTick: { show: false }, splitLine: { show: false } }));
    const yAxis = [0, 1, 2, 3].map((gridIndex) => ({ type: 'value', gridIndex, scale: gridIndex !== 2,
      min: gridIndex === 2 ? 0 : undefined, max: gridIndex === 2 ? 100 : undefined,
      position: 'right', axisLabel: { color: palette.text, fontSize: 10, formatter: (v: number) =>
        gridIndex === 1 ? Intl.NumberFormat('en', { notation: 'compact' }).format(v) : Number(v.toFixed(2)).toString() },
      splitLine: { lineStyle: { color: palette.grid, type: 'dashed' } }, axisLine: { show: false } }));
    const line = (name: string, key: string, color: string, gridIndex = 0) => ({
      name, type: 'line', xAxisIndex: gridIndex, yAxisIndex: gridIndex,
      data: byDate(key), showSymbol: false, connectNulls: false, lineStyle: { width: 1.5, color },
      itemStyle: { color }, emphasis: { focus: 'series' }
    });
    return {
      animation: false, backgroundColor: 'transparent', textStyle: { color: palette.text, fontFamily: 'var(--font-mono)' },
      legend: { top: 0, left: 4, icon: 'roundRect', textStyle: { color: palette.text, fontSize: 11 },
        data: ['OHLC', 'SMA 20', 'SMA 50', 'EMA 20', 'Bollinger upper', 'Bollinger lower'] },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross', crossStyle: { color: '#6e938e' } },
        backgroundColor: '#182320', borderColor: '#33423e', textStyle: { color: '#e3e9df' } },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [{ left: 14, right: 72, top: 38, height: '44%' },
        { left: 14, right: 72, top: '55%', height: '9%' },
        { left: 14, right: 72, top: '69%', height: '9%' },
        { left: 14, right: 72, top: '83%', height: '9%' }],
      xAxis, yAxis,
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1, 2, 3], startValue: visibleFrom, endValue: visibleTo,
        zoomOnMouseWheel: true, moveOnMouseMove: true },
        { type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 3, height: 14,
          startValue: visibleFrom, endValue: visibleTo, borderColor: palette.grid,
          fillerColor: '#354b43', backgroundColor: '#101817', handleStyle: { color: palette.lime },
          textStyle: { color: palette.text } }],
      series: [
        { name: 'OHLC', type: 'candlestick', data: bars.map((b) => [b.open, b.close, b.low, b.high]),
          itemStyle: { color: palette.up, color0: palette.down, borderColor: palette.up, borderColor0: palette.down } },
        line('SMA 20', 'sma_20', palette.lime), line('SMA 50', 'sma_50', palette.cyan),
        line('EMA 20', 'ema_20', palette.orange),
        line('Bollinger upper', 'bollinger_upper_20', palette.violet),
        line('Bollinger lower', 'bollinger_lower_20', palette.violet),
        { name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
          data: bars.map((b) => ({ value: b.volume, itemStyle: { color: b.close >= b.open ? '#527d69' : '#8e5d56' } })) },
        line('RSI 14', 'rsi_14', palette.cyan, 2),
        { name: 'MACD histogram', type: 'bar', xAxisIndex: 3, yAxisIndex: 3,
          data: byDate('macd_histogram').map((value) => ({ value,
            itemStyle: { color: value != null && value >= 0 ? palette.up : palette.down } })) }
      ]
    };
  }, [bars, features, visibleFrom, visibleTo]);
  return <CanvasChart option={option} height={690} label="OHLC candlesticks with backend moving averages, volume, RSI, MACD histogram and session zoom" />;
}

export function SeriesChart({ series, unit, height = 280 }: {
  series: { name: string; points: { session_date: string; value: number | null }[]; color?: string }[];
  unit?: string; height?: number
}) {
  const option = useMemo(() => {
    const dates = [...new Set(series.flatMap((item) => item.points.map((p) => p.session_date)))].sort();
    return { animation: false, backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: '#182320', borderColor: '#33423e', textStyle: { color: '#e3e9df' } },
      legend: { top: 0, textStyle: { color: palette.text } },
      grid: { top: 37, bottom: 40, left: 16, right: 62 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: palette.text, fontSize: 10 },
        axisLine: { lineStyle: { color: palette.grid } } },
      yAxis: { type: 'value', scale: true, name: unit, nameTextStyle: { color: palette.text },
        axisLabel: { color: palette.text }, splitLine: { lineStyle: { color: palette.grid, type: 'dashed' } } },
      dataZoom: [{ type: 'inside' }],
      series: series.map((item, index) => {
        const lookup = new Map(item.points.map((p) => [p.session_date, p.value]));
        return { name: item.name, type: 'line', data: dates.map((date) => lookup.get(date) ?? null),
          showSymbol: false, connectNulls: false, lineStyle: { width: 2, color: item.color ??
            [palette.lime, palette.cyan, palette.orange, palette.violet, palette.up][index % 5] } };
      }) };
  }, [series, unit]);
  return <CanvasChart option={option} height={height} label={`Backend-derived time series: ${series.map((s) => s.name).join(', ')}`} />;
}
