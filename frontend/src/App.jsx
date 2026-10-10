import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./api/client";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import { LogoMark } from "./components/Logo";
import LiveWattage from "./components/LiveWattage";
import { TrajectoryBanner, BillMetricsGrid } from "./components/BillSummary";
import UsageBreakdown from "./components/UsageBreakdown";
import UsageLog from "./components/UsageLog";
import ForecastChart from "./components/ForecastChart";
import ForecastAccuracy from "./components/ForecastAccuracy";
import Recommendations from "./components/Recommendations";
import BillImpact from "./components/BillImpact";
import TariffSettingsModal from "./components/TariffSettingsModal";
import DeviceReader from "./components/DeviceReader";
import MeterCheck from "./components/MeterCheck";
import ScaleUp from "./components/ScaleUp";
import CarbonFootprint from "./components/CarbonFootprint";
import BestTime from "./components/BestTime";
import Assistant from "./components/Assistant";
import Disclosure from "./components/Disclosure";
import { VIEWS } from "./navigation";
import { peso } from "./format";
import { AlertTriangle, RefreshCw } from "lucide-react";

const LIVE_POLL_MS = 2000;

const viewFromHash = () => {
  const id = window.location.hash.slice(1);
  return VIEWS[id] ? id : "dashboard";
};

export default function App() {
  const [rawData, setRawData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(viewFromHash);
  const [dateRange, setDateRange] = useState("30d");
  const [liveReading, setLiveReading] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [system, setSystem] = useState(null);
  // Budget overruns, savings and notes (rule-based), for the bell and the assistant.
  const [alerts, setAlerts] = useState([]);
  // A question for the assistant from elsewhere in the app ("Ask Kilo" on an alert).
  const [askRequest, setAskRequest] = useState(null);
  const mainRef = useRef(null);
  // Read by fetchData so a refresh keeps the selected window without re-creating the callback.
  const dateRangeRef = useRef(dateRange);
  dateRangeRef.current = dateRange;

  // The user's rate, bills, budget and billing cycle. Starts from the backend's .env values.
  const [customParams, setCustomParams] = useState(null);
  const [defaultParams, setDefaultParams] = useState(null);

  const fetchData = useCallback(async (params, isRefresh = false) => {
    if (!isRefresh) setLoading(true);
    setError(null);
    // Alerts don't hold up the dashboard: they arrive when they're ready.
    api.alerts(params, dateRangeRef.current).then((d) => setAlerts(d.alerts)).catch(() => {});

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
      setError(e.message || "The backend didn't answer.");
    } finally {
      setLoading(false);
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
    const timer = setInterval(poll, LIVE_POLL_MS);
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
    Promise.all([api.usage(customParams, dateRange), api.carbon(customParams, dateRange)])
      .then(([usage, carbon]) => {
        if (id === usageRequest.current) setRawData((d) => ({ ...d, usage, carbon }));
      })
      .catch((e) => setError(e.message || "Failed to load usage for this window."));
    // Runs only when the window changes; settings changes refetch everything through fetchData.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateRange]);

  const askAssistant = useCallback((text) => setAskRequest({ text, at: Date.now() }), []);

  const badges = { recommendations: rawData?.recs?.recommendations?.length || 0 };

  const renderView = () => {
    switch (activeTab) {
      case "device":
        return (
          <>
            <DeviceReader params={customParams} onDataChanged={refresh} />
            <LiveWattage reading={liveReading} />
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
      case "accuracy":
        return <ForecastAccuracy />;
      case "models":
        return <UsageBreakdown usage={rawData.usage} />;
      case "log":
        return <UsageLog params={customParams} range={dateRange} />;
      case "carbon":
        return (
          <CarbonFootprint
            carbon={rawData.carbon}
            params={customParams}
            range={dateRange}
            onAsk={askAssistant}
            onOpenRecommendations={() => handleSelectTab("recommendations")}
          />
        );
      case "recommendations":
        return <Recommendations recs={rawData.recs} liveReading={liveReading} onApplied={refresh} />;
      case "disclosure":
        return <Disclosure />;
      default:
        return (
          <>
            {/* Row 1: Trajectory container */}
            <TrajectoryBanner forecast={rawData.forecast} recs={rawData.recs} />

            {/* Row 2: 2x2 cards (Left) + Cycle projection trajectory card (Right, equal height) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0 items-stretch">
              <div className="min-w-0 flex flex-col h-full">
                <BillMetricsGrid
                  forecast={rawData.forecast}
                  recs={rawData.recs}
                  liveReading={liveReading}
                  usage={rawData.usage}
                  rate={customParams?.rate}
                />
              </div>
              <div className="min-w-0 flex flex-col h-full">
                <ForecastChart forecast={rawData.forecast} recs={rawData.recs} className="h-full" />
              </div>
            </div>

            {/* Row 3: Active power draw monitor (divided into two balanced cards, scrollable) */}
            <LiveWattage reading={liveReading} />

            {/* Row 4: Best time to run local AI card */}
            <BestTime info={rawData.bestTime} onOpenSettings={() => setSettingsOpen(true)} />

            {/* Row 5: If you kept this up */}
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
        liveReading={liveReading}
      />

      {/* 2. Main Viewport Container */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        {/* Top Navigation Bar */}
        <TopBar
          dateRange={dateRange}
          setDateRange={setDateRange}
          electricityRate={customParams?.rate}
          monthlyBudget={customParams?.budget}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          system={system}
          liveReading={liveReading}
          alerts={alerts}
          onOpenView={handleSelectTab}
          onAsk={askAssistant}
        />

        {/* Scrollable View */}
        <main ref={mainRef} className="flex-1 overflow-y-auto px-4 py-5 sm:p-6 lg:p-8 space-y-6 min-w-0">
          <div className="mx-auto w-full max-w-[87.5rem] space-y-6 min-w-0">
            <ViewHeader view={VIEWS[activeTab]} />

            {/* A failed refresh keeps the last figures on screen */}
            {error && rawData && (
              <div role="alert" className="notice notice-warn items-center">
                <AlertTriangle />
                <span className="flex-1 min-w-0">Couldn't refresh: {error}. Showing the last figures.</span>
                <button onClick={refresh} className="btn shrink-0">
                  <RefreshCw className="w-3.5 h-3.5" /> Try again
                </button>
              </div>
            )}

            {loading ? (
              <LoadingSkeleton />
            ) : !rawData ? (
              <ConnectionError error={error} onRetry={() => fetchData(customParams, true)} />
            ) : (
              <div key={activeTab} className="stagger space-y-6 min-w-0">
                {renderView()}
              </div>
            )}

            {/* Dashboard Footer */}
            <footer className="pt-4 pb-2 border-t border-line flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
              <div className="flex items-center gap-1.5">
                <LogoMark className="h-4 w-4" />
                <span className="font-semibold text-ink-soft">Kilo What?</span>
              </div>
              {customParams && (
                <div className="tabular-nums">
                  This device · Sampling every {LIVE_POLL_MS / 1000} s · Rate {peso(customParams.rate)} / kWh · Budget{" "}
                  {peso(customParams.budget, 0)} / mo · Cycle starts day {customParams.cycleStartDay ?? 1}
                </div>
              )}
            </footer>
          </div>
        </main>
      </div>

      {/* Kilo, the on-device assistant */}
      <Assistant
        params={customParams}
        range={dateRange}
        view={activeTab}
        alerts={alerts}
        askRequest={askRequest}
        onOpenView={handleSelectTab}
      />

      {/* Tariff & bill settings */}
      <TariffSettingsModal
        isOpen={settingsOpen && customParams != null}
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

// The shape of the dashboard while the first figures load, so nothing jumps when they arrive.
function LoadingSkeleton() {
  return (
    <div className="space-y-6 min-w-0" aria-busy="true" aria-label="Loading">
      <div className="dash-card h-16 animate-pulse" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="stat-card h-44 animate-pulse" />
          ))}
        </div>
        <div className="dash-card h-80 lg:h-auto animate-pulse" />
      </div>
    </div>
  );
}

function ConnectionError({ error, onRetry }) {
  return (
    <div className="flex justify-center py-10">
      <div role="alert" className="dash-card max-w-md w-full p-6 text-center space-y-4">
        <div className="w-10 h-10 rounded-full border border-line bg-sunken text-neg flex items-center justify-center mx-auto">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <h2 className="card-title">Can't reach the backend</h2>
        <p className="text-sm text-ink-soft leading-relaxed">
          The dashboard reads from the Python backend on localhost:5001. Check that it's running, then try again.
        </p>
        {error && <div className="inset-panel p-2.5 text-xs text-ink-soft break-words text-left">{error}</div>}
        <button onClick={onRetry} className="btn-primary w-full py-2">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Try again</span>
        </button>
      </div>
    </div>
  );
}

function ViewHeader({ view }) {
  if (!view) return null;
  return (
    <div className="min-w-0">
      <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-ink">{view.title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{view.description}</p>
    </div>
  );
}
