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
import CarbonFootprint from "./components/CarbonFootprint";
import BestTime from "./components/BestTime";
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
      const [usage, forecast, recs, impact, carbon, bestTime] = await Promise.all([
        api.usage(params, dateRangeRef.current),
        api.forecast(params),
        api.recommendations(params),
        api.impact(params),
        api.carbon(params, dateRangeRef.current),
        api.bestTime(params),
      ]);
      setRawData({ usage, forecast, recs, impact, carbon, bestTime });
      if (!params) {
        const fromServer = {
          rate: usage.rate_per_kwh,
          baseline: forecast.baseline_bill,
          currentBill: impact.current_bill,
          budget: forecast.budget,
          cycleStartDay: forecast.cycle?.start_day ?? 1,
          carbonBudget: carbon.budget?.kg ?? 0,
          tariff: bestTime.tariff,
          peakRate: bestTime.peak_rate,
          offpeakRate: bestTime.offpeak_rate,
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

  // 7D / 30D / MTD: only usage and carbon depend on the window; the forecast and bill follow the billing cycle.
  const usageRequest = useRef(0);
  useEffect(() => {
    if (!rawData) return;
    const id = ++usageRequest.current;
    setIsRefreshing(true);
    Promise.all([api.usage(customParams, dateRange), api.carbon(customParams, dateRange)])
      .then(([usage, carbon]) => {
        if (id === usageRequest.current) setRawData((d) => ({ ...d, usage, carbon }));
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
        title: "Critical load surge: +485.4 W",
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
      <div className="flex h-screen bg-canvas text-ink overflow-hidden font-sans">
        <Sidebar activeTab={activeTab} setActiveTab={handleSelectTab} badges={badges} />
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
          <TopBar
            dateRange={dateRange}
            setDateRange={setDateRange}
            onRefresh={() => {}}
            onOpenMobileMenu={() => setMobileMenuOpen(true)}
            onOpenSettings={() => setSettingsOpen(true)}
          />
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="stat-card h-36 animate-pulse" />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5 h-80 dash-card animate-pulse" />
              <div className="lg:col-span-7 h-80 dash-card animate-pulse" />
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Error State with Retry
  if (error) {
    return (
      <div className="flex h-screen bg-canvas text-ink overflow-hidden font-sans">
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
            <div className="dash-card max-w-md w-full p-6 text-center space-y-4">
              <div className="w-10 h-10 rounded-full bg-neg/10 text-neg flex items-center justify-center mx-auto">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h2 className="card-title">Telemetry link failure</h2>
              <p className="text-sm text-ink-soft leading-relaxed">
                Could not connect to localhost:5000 telemetry daemon. Verify that the Python backend process is listening.
              </p>
              <div className="inset-panel p-2.5 text-neg text-xs font-mono break-all text-left">{error}</div>
              <button onClick={() => fetchData(customParams, true)} className="btn-primary w-full py-2">
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-establish telemetry link</span>
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
      case "carbon":
        return <CarbonFootprint carbon={rawData.carbon} onOpenDirectives={() => handleSelectTab("recommendations")} />;
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
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-w-0">
              <div className="lg:col-span-5 flex flex-col min-w-0">
                <LiveWattage reading={effectiveLiveReading} />
              </div>
              <div className="lg:col-span-7 flex flex-col min-w-0">
                <ForecastChart forecast={rawData.forecast} recs={rawData.recs} />
              </div>
            </div>
            <BestTime info={rawData.bestTime} onOpenSettings={() => setSettingsOpen(true)} />
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
    <div className="flex h-screen bg-canvas text-ink overflow-hidden font-sans">
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
        <main ref={mainRef} className="flex-1 overflow-y-auto px-4 py-5 sm:p-6 lg:p-8 space-y-6 min-w-0">
          <div className="mx-auto w-full max-w-[1400px] space-y-6 min-w-0">
            <ViewHeader view={VIEWS[activeTab]} />

            <div key={activeTab} className="space-y-6 min-w-0 animate-view-in">
              {renderView()}
            </div>

            {/* Dashboard Footer */}
            <footer className="pt-4 pb-2 border-t border-line flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-accent" />
                <span className="font-medium text-ink-soft">WattTrace</span>
              </div>
              <div className="tabular-nums">
                This device · Sampling: 2000 ms · Tariff: ₱{customParams?.rate?.toFixed(2)} / kWh · Cap: ₱{customParams?.budget} · Cycle starts day {customParams?.cycleStartDay ?? 1}
              </div>
            </footer>
          </div>
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
        currentCarbonBudget={customParams?.carbonBudget}
        currentTariff={customParams?.tariff}
        currentPeakRate={customParams?.peakRate}
        currentOffpeakRate={customParams?.offpeakRate}
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
  return (
    <div className="min-w-0">
      <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-ink">{view.title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{view.description}</p>
    </div>
  );
}
