"use client";
import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";
import type { KlineBar } from "@/lib/api";

interface Props {
  data: KlineBar[];
}

type TimeStr = `${number}-${number}-${number}`;

export default function StockChart({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mainChartRef = useRef<HTMLDivElement>(null);
  const rsiChartRef = useRef<HTMLDivElement>(null);

  const [tooltipData, setTooltipData] = useState<any>(null);

  useEffect(() => {
    if (!mainChartRef.current || !rsiChartRef.current || !data.length) return;

    const commonOptions = {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(240,240,245,0.5)",
        fontFamily: "Inter, sans-serif",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      localization: {
        timeFormatter: (time: any) => {
          if (typeof time === "string") {
            const parts = time.split("-");
            if (parts.length === 3) return `${parts[1]}/${parts[2]}`;
          }
          return time.toString();
        },
      },
    };

    // ── Create Main Chart ──────────────────────────────────────────────
    const mainChart = createChart(mainChartRef.current, {
      ...commonOptions,
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true, visible: false },
      width: mainChartRef.current.clientWidth,
      height: mainChartRef.current.clientHeight,
    });

    // ── Create RSI Chart ───────────────────────────────────────────────
    const rsiChart = createChart(rsiChartRef.current, {
      ...commonOptions,
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true },
      width: rsiChartRef.current.clientWidth,
      height: rsiChartRef.current.clientHeight,
    });

    // ── Series Setup ───────────────────────────────────────────────────
    const candleSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: "#ff4d6a", downColor: "#00e5a0",
      borderUpColor: "#ff4d6a", borderDownColor: "#00e5a0",
      wickUpColor: "#ff4d6a", wickDownColor: "#00e5a0",
    });

    const volumeSeries = mainChart.addSeries(HistogramSeries, {
      color: "rgba(59,139,255,0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    mainChart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 }, visible: false });

    const macdSeries = mainChart.addSeries(HistogramSeries, {
      priceScaleId: "macd",
    });
    mainChart.priceScale("macd").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, visible: false });

    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: "#a855f7",
      lineWidth: 2,
    });

    // ── Data Mapping ───────────────────────────────────────────────────
    candleSeries.setData(data.map(d => ({ time: d.time as TimeStr, open: d.open, high: d.high, low: d.low, close: d.close })));
    volumeSeries.setData(data.map(d => ({ time: d.time as TimeStr, value: d.volume, color: d.close >= d.open ? "rgba(255,77,106,0.3)" : "rgba(0,229,160,0.3)" })));
    macdSeries.setData(data.map(d => ({ time: d.time as TimeStr, value: d.macd_hist ?? 0, color: (d.macd_hist ?? 0) >= 0 ? "rgba(255,77,106,0.6)" : "rgba(0,229,160,0.6)" })));
    rsiSeries.setData(data.map(d => ({ time: d.time as TimeStr, value: d.rsi ?? 50 })));

    // ── Markers ────────────────────────────────────────────────────────
    createSeriesMarkers(candleSeries, data.filter(d => d.signal !== 0).map(d => ({
      time: d.time as TimeStr,
      position: (d.signal === 1 ? "belowBar" : "aboveBar") as "belowBar" | "aboveBar",
      color: d.signal === 1 ? "#ff4d6a" : "#00e5a0",
      shape: (d.signal === 1 ? "arrowUp" : "arrowDown") as "arrowUp" | "arrowDown",
      text: d.signal === 1 ? "買" : "賣",
      size: 1.5,
    })));

    mainChart.timeScale().fitContent();

    // ── Sync TimeScale ─────────────────────────────────────────────────
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (range) rsiChart.timeScale().setVisibleLogicalRange(range);
    });
    rsiChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (range) mainChart.timeScale().setVisibleLogicalRange(range);
    });

    // ── Crosshair & Tooltip Sync ───────────────────────────────────────
    const handleCrosshair = (param: any, target: IChartApi, targetSeries: ISeriesApi<any>) => {
      if (!param.point || !param.time) {
        setTooltipData(null);
        target.clearCrosshairPosition();
        return;
      }

      // Extract data for tooltip
      const time = param.time;
      // time can be a string or a BusinessDay object. For find to work, we need a string match.
      const timeStr = typeof time === 'string' ? time : `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
      
      const bar = data.find(d => d.time === timeStr);
      if (bar) setTooltipData(bar);

      // Sync crosshair to the other chart by using a dummy price (0) and the shared time
      // The first parameter is the price, the second is the time index.
      target.setCrosshairPosition(0, time, targetSeries);
    };

    mainChart.subscribeCrosshairMove(p => handleCrosshair(p, rsiChart, rsiSeries));
    rsiChart.subscribeCrosshairMove(p => handleCrosshair(p, mainChart, candleSeries));

    // Initial tooltip state (last candle)
    setTooltipData(data[data.length - 1]);

    // ── Resize Observer ────────────────────────────────────────────────
    if (!containerRef.current) return;
    const currentContainer = containerRef.current;
    const ro = new ResizeObserver(() => {
      if (mainChartRef.current) {
        mainChart.applyOptions({ width: mainChartRef.current.clientWidth, height: mainChartRef.current.clientHeight });
      }
      if (rsiChartRef.current) {
        rsiChart.applyOptions({ width: rsiChartRef.current.clientWidth, height: rsiChartRef.current.clientHeight });
      }
    });
    ro.observe(currentContainer);

    return () => {
      ro.disconnect();
      mainChart.remove();
      rsiChart.remove();
    };
  }, [data]);

  return (
    <div ref={containerRef} className="w-full h-full flex flex-col relative" style={{ background: "var(--bg-surface)" }}>
      {/* Absolute Legend Overlay */}
      {tooltipData && (
        <div className="absolute top-2 left-4 z-10 flex gap-4 text-xs font-mono font-bold pt-1 pointer-events-none">
          <span className="text-[var(--text-secondary)] bg-black/40 px-2 border border-white/5 rounded backdrop-blur-sm">
            {tooltipData.time.split("-").slice(1).join("/")}
          </span>
          <span className="text-[var(--text-primary)]">O <span className="text-[var(--accent-blue)]">{typeof tooltipData.open === 'number' ? tooltipData.open.toFixed(2) : '-'}</span></span>
          <span className="text-[var(--text-primary)]">H <span className="text-[#ff4d6a]">{typeof tooltipData.high === 'number' ? tooltipData.high.toFixed(2) : '-'}</span></span>
          <span className="text-[var(--text-primary)]">L <span className="text-[#00e5a0]">{typeof tooltipData.low === 'number' ? tooltipData.low.toFixed(2) : '-'}</span></span>
          <span className="text-[var(--text-primary)]">C <span className={tooltipData.close >= tooltipData.open ? "text-[#ff4d6a]" : "text-[#00e5a0]"}>{typeof tooltipData.close === 'number' ? tooltipData.close.toFixed(2) : '-'}</span></span>
          <span className="text-[var(--text-primary)]">V <span className="text-[#a855f7]">{typeof tooltipData.volume === 'number' ? tooltipData.volume.toLocaleString() : '-'}</span></span>
          <span className="text-[var(--text-primary)]">MACD <span className={typeof tooltipData.macd_hist === 'number' && tooltipData.macd_hist >= 0 ? "text-[#ff4d6a]" : "text-[#00e5a0]"}>{typeof tooltipData.macd_hist === 'number' ? tooltipData.macd_hist.toFixed(3) : '-'}</span></span>
          <span className="text-[var(--text-primary)]">RSI <span className="text-[#a855f7]">{typeof tooltipData.rsi === 'number' ? tooltipData.rsi.toFixed(2) : '-'}</span></span>
        </div>
      )}

      {/* Main Chart (75%) */}
      <div ref={mainChartRef} className="flex-[3] min-h-0 relative" />
      
      {/* Divider */}
      <div className="h-px bg-[var(--border)] opacity-50 z-10" />
      
      {/* RSI Chart (25%) */}
      <div ref={rsiChartRef} className="flex-1 min-h-0 relative">
        <div className="absolute top-1 left-2 z-10 text-[10px] text-[#a855f7]/70 font-bold pointer-events-none">RSI (14)</div>
      </div>
    </div>
  );
}
