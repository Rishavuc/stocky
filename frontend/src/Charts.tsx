import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  ColorType,
  type Time,
} from "lightweight-charts";
import type { Candle } from "./api";
export function Spark({
  values,
  color = "#62dfb0",
}: {
  values: number[];
  color?: string;
}) {
  if (values.length < 2) return null;
  const lo = Math.min(...values),
    range = Math.max(...values) - lo || 1;
  const path = values
    .map(
      (v, i) =>
        `${(i * 100) / (values.length - 1)},${36 - ((v - lo) / range) * 30}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 40"
      role="img"
      aria-label="Recent closing prices"
      className="spark"
    >
      <polyline fill="none" stroke={color} strokeWidth="1.8" points={path} />
    </svg>
  );
}
export function PriceChart({ candles, overlays = [], chartType = "candles" }: { candles: Candle[]; overlays?: string[]; chartType?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !candles.length) return;
    const chart = createChart(ref.current, {
      height: 340,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8795a9",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "#192331" },
        horzLines: { color: "#192331" },
      },
      rightPriceScale: { borderColor: "#243040" },
      timeScale: {
        borderColor: "#243040",
        timeVisible: candles[0]?.date.includes("T") || false,
      },
      crosshair: {
        vertLine: { color: "#60748e" },
        horzLine: { color: "#60748e" },
      },
    });
    const time = (date:string) => (date.includes("T") ? Math.floor(Date.parse(date)/1000) : date) as Time;
    if(chartType==='line')chart.addSeries(LineSeries,{color:'#62dfb0',lineWidth:2}).setData(candles.map(x=>({time:time(x.date),value:x.close})));
    else chart.addSeries(CandlestickSeries,{upColor:'#62dfb0',downColor:'#f2818c',borderVisible:false,wickUpColor:'#62dfb0',wickDownColor:'#f2818c'}).setData(candles.map(x=>({time:time(x.date),open:x.open,high:x.high,low:x.low,close:x.close})));
    const moving=(kind:string)=>{let ema=candles[0].close;return candles.flatMap((x,i)=>{ema=i===0?x.close:x.close*(2/21)+ema*(19/21);if(i<19)return [];const window=candles.slice(i-19,i+1).map(c=>c.close);const mean=window.reduce((a,b)=>a+b,0)/20;const std=Math.sqrt(window.reduce((a,b)=>a+(b-mean)**2,0)/20);return [{time:time(x.date),value:kind==='EMA20'?ema:kind==='upper'?mean+2*std:kind==='lower'?mean-2*std:mean}];});};
    overlays.forEach(kind=>{if(kind==='BOLLINGER'){['upper','lower'].forEach(k=>chart.addSeries(LineSeries,{color:'#7186b5',lineWidth:1,priceLineVisible:false,lastValueVisible:false}).setData(moving(k)));}else chart.addSeries(LineSeries,{color:kind==='EMA20'?'#f3bb66':'#9294ed',lineWidth:2,priceLineVisible:false,title:kind}).setData(moving(kind));});
    chart.timeScale().fitContent();
    const observer = new ResizeObserver((entries) =>
      chart.applyOptions({ width: entries[0].contentRect.width }),
    );
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [candles, overlays, chartType]);
  return (
    <div
      ref={ref}
      className="price-chart"
      aria-label="Historical candlestick price chart"
    />
  );
}
export function ComparisonChart({
  points,
  labels = ["Portfolio", "Buy and hold"],
}: {
  points: { date: string; value: number; benchmark: number }[];
  labels?: string[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !points.length) return;
    const chart = createChart(ref.current, {
      height: 250,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8795a9",
      },
      grid: {
        vertLines: { color: "#192331" },
        horzLines: { color: "#192331" },
      },
      rightPriceScale: { borderColor: "#243040" },
      timeScale: { borderColor: "#243040" },
    });
    chart.addSeries(LineSeries, { color: "#62dfb0", lineWidth: 2 }).setData(
      points.map((x) => ({
        time: (x.date.includes("T")
          ? Math.floor(new Date(x.date).getTime() / 1000)
          : x.date) as Time,
        value: x.value,
      })),
    );
    chart
      .addSeries(LineSeries, { color: "#9294ed", lineWidth: 2, lineStyle: 2 })
      .setData(
        points.map((x) => ({
          time: (x.date.includes("T")
            ? Math.floor(new Date(x.date).getTime() / 1000)
            : x.date) as Time,
          value: x.benchmark,
        })),
      );
    chart.timeScale().fitContent();
    const ro = new ResizeObserver((e) =>
      chart.applyOptions({ width: e[0].contentRect.width }),
    );
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [points]);
  return (
    <>
      <div className="chart-key">
        <span>
          <i />
          {labels[0]}
        </span>
        <span>
          <i className="purple" />
          {labels[1]}
        </span>
      </div>
      <div ref={ref} aria-label="Performance comparison chart" />
    </>
  );
}
