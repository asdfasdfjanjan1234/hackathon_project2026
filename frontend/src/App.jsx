import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "./api/client";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import LiveWattage from "./components/LiveWattage";
import BillSummary from "./components/BillSummary";
import UsageBreakdown from "./components/UsageBreakdown";
import ForecastChart from "./components/ForecastChart";
import Recommendations from "./components/Recommendations";
import BillImpact from "./components/BillImpact";
import TariffSettingsModal from "./components/TariffSettingsModal";
import { AlertTriangle, RefreshCw, Zap } from "lucide-react";

export default function App() {
  const [rawData, setRawData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [dateRange, setDateRange] = useState("30d");
  const [liveReading, setLiveReading] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Dynamic user-customizable parameters
  const [customParams, setCustomParams] = useState({
    rate: 12.0,
    budget: 2000,
    baseline: 1500,
  });

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [usage, forecast, recs] = await Promise.all([
        api.usage(),
        api.forecast(),
        api.recommendations(),
      ]);

      const impact = await api.impact(forecast, usage);

      setRawData({ usage, forecast, recs, impact });
      if (usage?.rate_per_kwh) {
        setCustomParams((prev) => ({
          ...prev,
          rate: usage.rate_per_kwh,
          baseline: forecast?.baseline_bill || prev.baseline,
        }));
      }
    } catch (e) {
      setError(e.message || "Failed to communicate with telemetry backend.");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle Tab navigation & section scrolling
  const handleSelectTab = (tabId) => {
    setActiveTab(tabId);
    if (tabId === "settings") {
      setSettingsOpen(true);
      return;
    }
    const sectionMap = {
      dashboard: "section-overview",
      analytics: "section-forecast",
      models: "section-models",
      recommendations: "section-directives",
    };
    const targetId = sectionMap[tabId];
    if (targetId) {
      const el = document.getElementById(targetId);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Dynamically compute calibrated data according to dateRange and customParams
  const processedData = useMemo(() => {
    if (!rawData) return null;

    const rate = customParams.rate;
    const baseline = customParams.baseline;
    const budget = customParams.budget;

    // Time scaling multiplier
    let timeScale = 1.0;
    if (dateRange === "7d") timeScale = 7 / 30;
    else if (dateRange === "month") timeScale = 22 / 30;

    // Recalibrate usage
    const calibratedByModel = (rawData.usage?.by_model || []).map((m) => {
      const scaledKwh = Number((m.kwh * timeScale).toFixed(2));
      const scaledCost = Number((scaledKwh * rate).toFixed(2));
      return {
        ...m,
        kwh: scaledKwh,
        cost: scaledCost,
      };
    });

    const totalAiKwh = calibratedByModel.reduce((s, m) => s + m.kwh, 0);
    const totalAiCost = Number((totalAiKwh * rate).toFixed(2));
    const forecastBill = Number((baseline + totalAiCost).toFixed(2));

    // Recalibrate recommendations
    const totalSavings = rawData.recs?.recommendations?.reduce((s, r) => s + (r.monthly_savings || 0), 0) || 520;
    const billWithRecs = Math.max(baseline, forecastBill - totalSavings);

    // Recalibrate impact
    const increase = Math.max(0, forecastBill - baseline);
    const aiEffect = Math.min(increase, totalAiCost);
    const otherEffect = Math.max(0, increase - aiEffect);
    const aiShare = increase > 0 ? aiEffect / increase : 0;

    let verdict = "minor";
    if (increase <= 0) verdict = "no_increase";
    else if (aiShare >= 0.5) verdict = "major";
    else if (aiShare >= 0.2) verdict = "contributing";

    return {
      usage: {
        ...rawData.usage,
        rate_per_kwh: rate,
        by_model: calibratedByModel,
      },
      forecast: {
        ...rawData.forecast,
        baseline_bill: baseline,
        forecast_bill: forecastBill,
        ai_cost: totalAiCost,
        by_model: calibratedByModel,
      },
      recs: {
        ...rawData.recs,
        bill_with_recommendations: billWithRecs,
      },
      impact: {
        ...rawData.impact,
        baseline_bill: baseline,
        current_bill: forecastBill,
        increase,
        ai_effect: aiEffect,
        rate_effect: 0,
        other_effect: otherEffect,
        ai_share: aiShare,
        verdict,
        local_ai_kwh: Number((totalAiKwh * 0.95).toFixed(1)),
      },
    };
  }, [rawData, customParams, dateRange]);

  // Loading Skeleton State
  if (loading) {
    return (
      <div className="flex h-screen bg-darkBg text-slate-100 overflow-hidden font-sans">
        <Sidebar activeTab={activeTab} setActiveTab={handleSelectTab} />
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
          <TopBar
            dateRange={dateRange}
            setDateRange={setDateRange}
            onRefresh={() => {}}
            onOpenMobileMenu={() => setMobileMenuOpen(true)}
            onOpenSettings={() => setSettingsOpen(true)}
          />
          <main className="flex-1 overflow-y-auto p-4 sm:p-5 lg:p-6 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="stat-card h-32 animate-pulse bg-white/[0.02]" />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-5 h-80 rounded-lg bg-white/[0.02] border border-white/5 animate-pulse" />
              <div className="lg:col-span-7 h-80 rounded-lg bg-white/[0.02] border border-white/5 animate-pulse" />
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Error State with Retry
  if (error) {
    return (
      <div className="flex h-screen bg-darkBg text-slate-100 overflow-hidden font-sans">
        <Sidebar activeTab={activeTab} setActiveTab={handleSelectTab} />
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
          <TopBar
            dateRange={dateRange}
            setDateRange={setDateRange}
            onRefresh={() => fetchData(true)}
            onOpenMobileMenu={() => setMobileMenuOpen(true)}
            onOpenSettings={() => setSettingsOpen(true)}
          />
          <main className="flex-1 flex items-center justify-center p-6">
            <div className="max-w-md w-full p-6 rounded-lg bg-slate-900 border border-rose-500/30 text-center space-y-4 shadow-2xl font-mono">
              <div className="w-10 h-10 rounded bg-rose-500/10 border border-rose-500/25 text-rose-400 flex items-center justify-center mx-auto">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Telemetry Link Failure</h2>
              <p className="text-xs text-slate-400 leading-relaxed font-sans">
                Could not connect to localhost:5001 telemetry daemon. Verify that the Python backend process is listening.
              </p>
              <div className="p-2.5 rounded bg-black/50 text-rose-300 text-[11px] break-all border border-white/5">
                {error}
              </div>
              <button
                onClick={() => fetchData(true)}
                className="w-full py-2 px-4 rounded bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors uppercase tracking-wider"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-establish Telemetry Link</span>
              </button>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-darkBg text-slate-100 overflow-hidden font-sans">
      {/* 1. Left Sidebar (With responsive mobile drawer support) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={handleSelectTab}
        mobileOpen={mobileMenuOpen}
        setMobileOpen={setMobileMenuOpen}
      />

      {/* 2. Main Viewport Container */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        {/* Top Navigation Bar */}
        <TopBar
          dateRange={dateRange}
          setDateRange={setDateRange}
          onRefresh={() => fetchData(true)}
          isRefreshing={isRefreshing}
          electricityRate={customParams.rate}
          monthlyBudget={customParams.budget}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        {/* Scrollable Dashboard Grid */}
        <main className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6 space-y-5 min-w-0">
          {/* Section A: KPI Stat Cards & Trajectory Ribbon */}
          <div id="section-overview">
            <BillSummary
              forecast={processedData.forecast}
              recs={processedData.recs}
              liveReading={liveReading}
              usage={processedData.usage}
            />
          </div>

          {/* Section B: Primary Visual Panels */}
          <div id="section-forecast" className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-w-0">
            {/* Live Power Monitor */}
            <div className="lg:col-span-5 flex flex-col min-w-0">
              <LiveWattage onReadingChange={setLiveReading} />
            </div>

            {/* Bill Forecast Projection Area Chart */}
            <div className="lg:col-span-7 flex flex-col min-w-0">
              <ForecastChart
                forecast={processedData.forecast}
                recs={processedData.recs}
              />
            </div>
          </div>

          {/* Section C: Capacity & Model Status */}
          <div id="section-models" className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-w-0">
            {/* Bill Impact Donut Chart */}
            <div className="lg:col-span-5 flex flex-col min-w-0">
              <BillImpact impact={processedData.impact} />
            </div>

            {/* AI Model Breakdown & Efficiency Ratings */}
            <div className="lg:col-span-7 flex flex-col min-w-0">
              <UsageBreakdown usage={processedData.usage} />
            </div>
          </div>

          {/* Section D: Alerts & Recommendations */}
          <div id="section-directives">
            <Recommendations recs={processedData.recs} />
          </div>

          {/* Dashboard Footer */}
          <footer className="pt-3 pb-2 border-t border-white/5 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 gap-2 select-none">
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
              <span>WATT-TELEMETRY SCADA CONSOLE // ENGINE V1.4</span>
            </div>
            <div>
              SAMPLING: 2000MS · TARIFF: ₱{customParams.rate.toFixed(2)} / KWH · CAP: ₱{customParams.budget}
            </div>
          </footer>
        </main>
      </div>

      {/* Interactive Tariff & Hardware Settings Modal */}
      <TariffSettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        currentRate={customParams.rate}
        currentBudget={customParams.budget}
        currentBaseline={customParams.baseline}
        onSave={(newParams) => setCustomParams(newParams)}
      />
    </div>
  );
}
