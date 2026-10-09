import { useEffect, useState, useCallback, useMemo, useRef } from "react";
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
import DeviceReader from "./components/DeviceReader";
import MeterCheck from "./components/MeterCheck";
import ScaleUp from "./components/ScaleUp";
import { VIEWS } from "./navigation";
import { AlertTriangle, RefreshCw, Zap } from "lucide-react";

const viewFromHash = () => {
  const id = window.location.hash.slice(1);
  return VIEWS[id] ? id : "dashboard";
};

export default function App() {
  const [rawData, setRawData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState(viewFromHash);
  const [dateRange, setDateRange] = useState("30d");
  const [liveReading, setLiveReading] = useState(null);
  const [demoSpike, setDemoSpike] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [system, setSystem] = useState(null);
  const mainRef = useRef(null);
  // Read by fetchData so a refresh keeps the selected window without re-creating the callback.
  const dateRangeRef = useRef(dateRange);
  dateRangeRef.current = dateRange;

  const effectiveLiveReading = useMemo(() => {
    if (!liveReading) return null;
    if (!demoSpike) return liveReading;
    // Components are {watts, source}; the spike adds 485.4 W split across GPU, CPU and RAM.
    const parts = liveReading.components || {};
    const bump = (key, w) => ({ ...parts[key], watts: Math.round(((parts[key]?.watts || 0) + w) * 10) / 10,
                                source: parts[key]?.source || "estimated" });
    return {
      ...liveReading,
      watts: Math.round(((liveReading.watts || 12) + 485.4) * 10) / 10,
      ai_watts: Math.round(((liveReading.ai_watts || 0) + 485.4) * 10) / 10,
      components: { ...parts, gpu: bump("gpu", 382.5), cpu: bump("cpu", 91.2), memory: bump("memory", 11.7) },
      apps: [
        { name: "ollama (llama3:70b)", kind: "local", cpu_percent: 780, watts: 452.0 },
        { name: "python (stable-diffusion-xl)", kind: "local", cpu_percent: 120, watts: 33.4 },
        ...(liveReading.apps || []),
      ],
      spike_simulated: true,
    };
  }, [liveReading, demoSpike]);

  // The user's rate, bills, budget and billing cycle. Starts from the backend's .env values.
  const [customParams, setCustomParams] = useState(null);
  const [defaultParams, setDefaultParams] = useState(null);

  const fetchData = useCallback(async (params, isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [usage, forecast, recs, impact] = await Promise.all([
        api.usage(params, dateRangeRef.current),
        api.forecast(params),
        api.recommendations(params),
        api.impact(params),
      ]);
      setRawData({ usage, forecast, recs, impact });
      if (!params) {
        const fromServer = {
          rate: usage.rate_per_kwh,
          baseline: forecast.baseline_bill,
          currentBill: impact.current_bill,
          budget: forecast.budget,
          cycleStartDay: forecast.cycle?.start_day ?? 1,
        };
        setCustomParams(fromServer);
        setDefaultParams(fromServer);
      }
    } catch (e) {
      setError(e.message || "Failed to communicate with telemetry backend.");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData(null);
  }, [fetchData]);

  // The detected OS and hardware, for the header. Detection runs once on the backend.
  useEffect(() => {
    api.system().then((d) => setSystem(d.system)).catch(() => {});
  }, []);

  const refresh = useCallback(() => fetchData(customParams, true), [fetchData, customParams]);

  // Keep the dashboard current as readings come in.
  useEffect(() => {
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  // Poll live power here so it keeps updating whichever view is open.
  useEffect(() => {
    let isMounted = true;
    const poll = async () => {
      try {
        const data = await api.live();
        if (isMounted) setLiveReading(data);
      } catch {
        // Keep the last reading
      }
    };
    poll();
    const timer = setInterval(poll, 2000);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  // Each sidebar item is its own view; "settings" opens the tariff modal instead.
  const handleSelectTab = (tabId) => {
    if (tabId === "settings") {
      setSettingsOpen(true);
      return;
    }
    setActiveTab(tabId);
    window.history.replaceState(null, "", `#${tabId}`);
    mainRef.current?.scrollTo({ top: 0 });
  };

  useEffect(() => {
    const onHashChange = () => setActiveTab(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // 7D / 30D / MTD: only usage depends on the window; the forecast and bill follow the billing cycle.
  const usageRequest = useRef(0);
  useEffect(() => {
    if (!rawData) return;
    const id = ++usageRequest.current;
    setIsRefreshing(true);
    api
      .usage(customParams, dateRange)
      .then((usage) => {
        if (id === usageRequest.current) setRawData((d) => ({ ...d, usage }));
      })
      .catch((e) => setError(e.message || "Failed to load usage for this window."))
      .finally(() => {
        if (id === usageRequest.current) setIsRefreshing(false);
      });
    // Runs only when the window changes; settings changes refetch everything through fetchData.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateRange]);

  // Header alerts: the budget warning and the biggest saving, straight from the recommendations.
  const alerts = useMemo(() => {
    const recs = rawData?.recs?.recommendations || [];
    const budget = recs.find((r) => r.rule === "budget");
    const top = recs.find((r) => r.rule !== "budget" && r.scope === "bill" && !r.alternative);
    const list = [];
    if (demoSpike) {
      list.push({
        level: "warn",
        title: "CRITICAL LOAD SURGE: +485.4W",
        text: "Local Ollama Llama-3-70B + Stable Diffusion active on GPU. Projected cost: +₱5.82 / hr at ₱12/kWh.",
      });
    }
    if (budget) list.push({ level: "warn", title: "Budget overrun projected", text: budget.message });
    if (top) list.push({ level: "opt", title: `${top.action}: ${top.model}`, text: top.message });
    return list;
  }, [rawData, demoSpike]);

  const badges = { recommendations: rawData?.recs?.recommendations?.length || 0 };

  // Loading Skeleton State
  if (loading) {
    return (
      <div className="flex h-screen bg-darkBg text-slate-100 overflow-hidden font-sans">
        <Sidebar activeTab={activeTab} setActiveTab={handleSelectTab} badges={badges} />
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
        <Sidebar activeTab={activeTab} setActiveTab={handleSelectTab} badges={badges} />
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
          <TopBar
            dateRange={dateRange}
            setDateRange={setDateRange}
            onRefresh={refresh}
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
                onClick={() => fetchData(customParams, true)}
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

  const renderView = () => {
    switch (activeTab) {
      case "device":
        return (
          <>
            <DeviceReader params={customParams} onDataChanged={refresh} />
            <LiveWattage reading={effectiveLiveReading} />
            <MeterCheck />
          </>
        );
      case "analytics":
        return (
          <>
            <ForecastChart forecast={rawData.forecast} recs={rawData.recs} />
            <BillImpact impact={rawData.impact} />
          </>
        );
      case "models":
        return <UsageBreakdown usage={rawData.usage} />;
      case "recommendations":
        return <Recommendations recs={rawData.recs} liveReading={liveReading} onApplied={refresh} />;
      default:
        return (
          <>
            <BillSummary
              forecast={rawData.forecast}
              recs={rawData.recs}
              liveReading={effectiveLiveReading}
              usage={rawData.usage}
              rate={customParams?.rate}
            />
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-w-0">
              <div className="lg:col-span-5 flex flex-col min-w-0">
                <LiveWattage reading={effectiveLiveReading} />
              </div>
              <div className="lg:col-span-7 flex flex-col min-w-0">
                <ForecastChart forecast={rawData.forecast} recs={rawData.recs} />
              </div>
            </div>
            <ScaleUp
              liveReading={liveReading}
              forecast={rawData.forecast}
              recs={rawData.recs}
              rate={customParams?.rate ?? rawData.usage.rate_per_kwh}
            />
          </>
        );
    }
  };

  return (
    <div className="flex h-screen bg-darkBg text-slate-100 overflow-hidden font-sans">
      {/* 1. Left Sidebar (With responsive mobile drawer support) */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={handleSelectTab}
        mobileOpen={mobileMenuOpen}
        setMobileOpen={setMobileMenuOpen}
        badges={badges}
        liveReading={effectiveLiveReading}
      />

      {/* 2. Main Viewport Container */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        {/* Top Navigation Bar */}
        <TopBar
          dateRange={dateRange}
          setDateRange={setDateRange}
          onRefresh={refresh}
          isRefreshing={isRefreshing}
          electricityRate={customParams?.rate}
          monthlyBudget={customParams?.budget}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          system={system}
          liveReading={effectiveLiveReading}
          alerts={alerts}
          demoSpike={demoSpike}
          onToggleDemoSpike={() => setDemoSpike((p) => !p)}
        />

        {/* Scrollable View */}
        <main ref={mainRef} className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6 space-y-5 min-w-0">
          <ViewHeader view={VIEWS[activeTab]} />

          <div key={activeTab} className="space-y-5 min-w-0 animate-view-in">
            {renderView()}
          </div>

          {/* Dashboard Footer */}
          <footer className="pt-3 pb-2 border-t border-white/5 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 gap-2 select-none">
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
              <span>WATT-TELEMETRY SCADA CONSOLE // ENGINE V1.4</span>
            </div>
            <div>
              THIS DEVICE · SAMPLING: 2000MS · TARIFF: ₱{customParams?.rate?.toFixed(2)} / KWH · CAP: ₱{customParams?.budget} · CYCLE STARTS DAY {customParams?.cycleStartDay ?? 1}
            </div>
          </footer>
        </main>
      </div>

      {/* Interactive Tariff & Hardware Settings Modal */}
      <TariffSettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        currentRate={customParams?.rate}
        currentBudget={customParams?.budget}
        currentBaseline={customParams?.baseline}
        currentBill={customParams?.currentBill}
        currentCycleStartDay={customParams?.cycleStartDay}
        defaults={defaultParams}
        onSave={(newParams) => {
          setCustomParams(newParams);
          fetchData(newParams, true);
        }}
      />
    </div>
  );
}

function ViewHeader({ view }) {
  if (!view) return null;
  const Icon = view.icon;
  return (
    <div className="flex items-center gap-3 min-w-0">
      <div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/25 flex items-center justify-center text-sky-400 shrink-0">
        <Icon className="w-4 h-4" />
      </div>
      <div className="min-w-0">
        <h2 className="text-base sm:text-lg font-bold font-mono tracking-tight text-white uppercase truncate">
          {view.title}
        </h2>
        <p className="text-xs text-slate-400 truncate">{view.description}</p>
      </div>
    </div>
  );
}
