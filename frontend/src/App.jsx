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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const mainRef = useRef(null);

  // The user's rate, bills and budget. Starts from the backend's .env values.
  const [customParams, setCustomParams] = useState(null);

  const fetchData = useCallback(async (params, isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [usage, forecast, recs, impact] = await Promise.all([
        api.usage(params),
        api.forecast(params),
        api.recommendations(params),
        api.impact(params),
      ]);
      setRawData({ usage, forecast, recs, impact });
      if (!params) {
        setCustomParams({
          rate: usage.rate_per_kwh,
          baseline: forecast.baseline_bill,
          currentBill: impact.current_bill,
          budget: forecast.budget,
        });
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

  const refresh = useCallback(() => fetchData(customParams, true), [fetchData, customParams]);

  // While showing this device's data, keep the dashboard current as readings come in.
  const dataSource = rawData?.usage?.data_source;
  useEffect(() => {
    if (dataSource !== "device") return undefined;
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [dataSource, refresh]);

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

  // The backend does the bill math; here we only narrow the usage table to the date range.
  const processedData = useMemo(() => {
    if (!rawData) return null;
    const rate = rawData.usage.rate_per_kwh;
    const today = new Date();
    const since = new Date(today);
    if (dateRange === "7d") since.setDate(today.getDate() - 7);
    else if (dateRange === "month") since.setDate(1);
    else since.setDate(today.getDate() - 30);
    const sinceIso = since.toISOString().slice(0, 10);

    const totals = {};
    for (const row of rawData.usage.daily || []) {
      if (row.date < sinceIso) continue;
      const m = (totals[row.model] ||= { model: row.model, kind: row.kind, source: row.source, kwh: 0 });
      m.kwh += row.kwh;
    }
    const byModel = Object.values(totals)
      .map((m) => ({ ...m, cost: m.kwh * rate }))
      .sort((a, b) => b.kwh - a.kwh);

    return { ...rawData, usage: { ...rawData.usage, by_model: byModel } };
  }, [rawData, dateRange]);

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
            <DeviceReader dataSource={dataSource} params={customParams} onDataChanged={refresh} />
            <LiveWattage reading={liveReading} />
          </>
        );
      case "analytics":
        return (
          <>
            <ForecastChart forecast={processedData.forecast} recs={processedData.recs} />
            <BillImpact impact={processedData.impact} />
          </>
        );
      case "models":
        return <UsageBreakdown usage={processedData.usage} />;
      case "recommendations":
        return <Recommendations recs={processedData.recs} />;
      default:
        return (
          <>
            <BillSummary
              forecast={processedData.forecast}
              recs={processedData.recs}
              liveReading={liveReading}
              usage={processedData.usage}
            />
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-w-0">
              <div className="lg:col-span-5 flex flex-col min-w-0">
                <LiveWattage reading={liveReading} />
              </div>
              <div className="lg:col-span-7 flex flex-col min-w-0">
                <ForecastChart forecast={processedData.forecast} recs={processedData.recs} />
              </div>
            </div>
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
              {dataSource === "device" ? "THIS DEVICE" : "SAMPLE DATA"} · SAMPLING: 2000MS · TARIFF: ₱{customParams?.rate?.toFixed(2)} / KWH · CAP: ₱{customParams?.budget}
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
