import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import {
  Laptop,
  Play,
  Square,
  Loader2,
  Cpu,
  Bot,
  Cloud,
  ShieldCheck,
  Database,
} from "lucide-react";
import { formatWatts, formatWh, formatTokens, peso } from "../format";

const SENSOR_LABELS = { system: "Whole machine", cpu: "CPU", gpu: "GPU", memory: "Memory", disk: "Disk" };

function Row({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1 border-b border-white/[0.04] last:border-0">
      <span className="text-[10px] font-mono uppercase text-slate-500 shrink-0">{label}</span>
      <span className="text-[11px] text-slate-200 text-right min-w-0 break-words">{children}</span>
    </div>
  );
}

function Panel({ icon: Icon, title, children }) {
  return (
    <div className="rounded-lg bg-black/30 border border-white/5 p-3 min-w-0">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5 text-sky-400" />
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function DevicePanel({ system, sensors }) {
  if (!system) return null;
  const list = (items, fmt) => (items?.length ? items.map(fmt).join(", ") : "none found");
  const battery = system.battery;
  return (
    <Panel icon={Laptop} title="This device">
      <Row label="OS">{system.os} {system.os_version} ({system.arch})</Row>
      <Row label="Device">{system.device?.model || "unknown model"} · {system.device?.type}</Row>
      <Row label="CPU">{system.cpu}, {system.cpu_cores?.physical} cores</Row>
      <Row label="RAM">{system.memory_gb} GB</Row>
      <Row label="GPU">{list(system.gpus, (g) => `${g.name} (${g.type})`)}</Row>
      <Row label="NPU">{list(system.npus, (n) => n.name)}</Row>
      <Row label="Disks">{list(system.disks, (d) => `${d.name} (${d.type}, ${d.size_gb} GB)`)}</Row>
      <Row label="Battery">
        {battery ? `${battery.percent}%, ${battery.plugged_in ? "plugged in" : "on battery"}` : "none (desktop)"}
      </Row>
      {sensors && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-1">
          <div className="text-[10px] font-mono uppercase text-slate-500">Power readings</div>
          {Object.entries(sensors).map(([part, sensor]) => (
            <div key={part} className="flex items-center justify-between text-[11px]">
              <span className="text-slate-300">{SENSOR_LABELS[part] || part}</span>
              <span className={`tech-tag ${sensor ? "tech-tag-live" : "tech-tag-sim"}`}>
                {sensor ? `measured · ${sensor}` : "estimated"}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function AppsPanel({ status }) {
  const latest = status?.latest;
  const apps = latest?.apps || [];
  const aiWatts = apps.reduce((s, a) => s + (a.watts || 0), 0);
  return (
    <Panel icon={Bot} title="AI apps running now">
      {latest ? (
        <>
          <Row label="Machine">
            {formatWatts(latest.measured_watts ?? latest.est_watts)}{" "}
            <span className="text-slate-500">{latest.measured_watts != null ? "measured" : "estimated"}</span>
          </Row>
          <Row label="AI apps">
            {formatWatts(aiWatts)} <span className="text-slate-500">calculated share</span>
          </Row>
          <div className="mt-2 space-y-1.5">
            {apps.length === 0 && <div className="text-[11px] text-slate-400">No AI apps running.</div>}
            {apps.map((a, i) => (
              <div key={`${a.model || a.app}-${a.host}-${i}`} className="flex items-center justify-between gap-2 text-[11px]">
                <div className="min-w-0">
                  <div className="text-slate-100 truncate">{a.model || a.app}</div>
                  <div className="text-[10px] text-slate-500">
                    {a.kind === "local" ? "local model" : "cloud client"}
                    {a.host ? ` · in ${a.host}` : ""} · {(a.cpu_percent || 0).toFixed(1)}% CPU
                  </div>
                </div>
                <span className="font-mono tabular-nums text-sky-300 shrink-0">{(a.watts || 0).toFixed(2)} W</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="text-[11px] text-slate-400 flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Taking the first reading…
        </div>
      )}
    </Panel>
  );
}

function ModelsPanel({ models }) {
  if (!models) {
    return (
      <Panel icon={Cloud} title="Models found">
        <div className="text-[11px] text-slate-400 flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading app logs…
        </div>
      </Panel>
    );
  }
  const unmeasurable = models.extensions.filter((e) => !e.measurable);
  return (
    <Panel icon={Cloud} title={`Models found (last ${models.days} days)`}>
      {models.models.length === 0 && (
        <div className="text-[11px] text-slate-400">No AI model usage found in Claude Code, Codex, Copilot, Kiro, Amazon Q, OpenCode or Gemini CLI.</div>
      )}
      <div className="space-y-1.5">
        {models.models.map((m) => (
          <div key={`${m.app}-${m.model}`} className="flex items-center justify-between gap-2 text-[11px]">
            <div className="min-w-0">
              <div className="text-slate-100 truncate">
                {m.name} <span className="text-slate-500">· {m.app}</span>
              </div>
              <div className="text-[10px] text-slate-500">
                {m.requests} requests
                {m.tokens.output ? ` · ${formatTokens(m.tokens.output)} output tokens` : " · no token counts"}
                {m.relative_energy ? ` · ${m.priced_as ? "≈" : ""}${m.relative_energy}× Sonnet` : ""}
                {m.priced_as ? ` · not in catalog, priced like ${m.priced_as}` : ""}
                {m.relative_energy == null ? ` · ${m.provider ? `${m.provider} model` : "model"} not in catalog, no estimate` : ""}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="font-mono tabular-nums text-amber-300">{formatWh(m.datacenter_wh)}</div>
              <div className="text-[9px] text-slate-500 uppercase">data center · est.</div>
              {m.device_kwh != null && (
                <div className="font-mono tabular-nums text-[10px] text-sky-300 mt-0.5">
                  {formatWh(m.device_kwh * 1000)} · {peso(m.device_cost)} <span className="text-slate-500">on this device</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {models.switch_hint && (
        <div className="mt-2 p-2 rounded bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-200">
          {models.switch_hint.message}
        </div>
      )}
      {unmeasurable.length > 0 && (
        <div className="mt-2 text-[10px] text-slate-500">
          Installed, can't be measured separately: {unmeasurable.map((e) => e.name).join(", ")}
        </div>
      )}
      <div className="mt-2 text-[10px] text-slate-500">
        Estimated from list prices; {models.reference.source}. Not on your bill.
      </div>
    </Panel>
  );
}

export default function DeviceReader({ dataSource, params, onDataChanged }) {
  const [status, setStatus] = useState(null);
  const [system, setSystem] = useState(null);
  const [sensors, setSensors] = useState(null);
  const [models, setModels] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  const running = status?.running || status?.external_collector;
  const viewingDevice = dataSource === "device";

  const loadDetails = useCallback(async () => {
    const [sys, mdl] = await Promise.all([api.system(), api.models(params)]);
    setSystem(sys.system);
    setSensors(sys.sensors);
    setModels(mdl);
  }, [params]);

  // A reading may already be going (page reload, or collect.py in a terminal).
  useEffect(() => {
    api.deviceStatus().then((s) => {
      setStatus(s);
      if (s.running || s.external_collector) loadDetails().catch(() => {});
    }).catch(() => {});
  }, [loadDetails]);

  useEffect(() => {
    if (!running) return undefined;
    const statusTimer = setInterval(() => api.deviceStatus().then(setStatus).catch(() => {}), 2000);
    const modelsTimer = setInterval(() => api.models(params).then(setModels).catch(() => {}), 30000);
    return () => {
      clearInterval(statusTimer);
      clearInterval(modelsTimer);
    };
  }, [running, params]);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const res = await api.startDevice();
      setStatus(res);
      setSystem(res.system);
      setSensors(res.sensors);
      onDataChanged?.();
      setModels(await api.models(params));
    } catch (e) {
      setError(`Could not start reading: ${e.message}. Is the backend running on this computer?`);
    } finally {
      setStarting(false);
    }
  };

  const stop = async () => {
    setStatus(await api.stopDevice());
    onDataChanged?.();
  };

  const switchSource = async (source) => {
    setStatus(await api.setDataSource(source));
    onDataChanged?.();
  };

  const showDetails = running || system;

  return (
    <section className="dash-card p-4 sm:p-5 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider">Device Reader</h2>
            <div className="text-[10px] font-mono text-slate-400">
              {running
                ? `Reading every 2 s · ${status.samples || status.stored_samples} samples${status.external_collector ? " (collect.py)" : ""}`
                : "Measures the AI apps on this computer"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-black/40 border border-white/5 p-0.5 text-[10px] font-mono">
            {[
              ["device", "This device"],
              ["sample", "Sample (John)"],
            ].map(([id, label]) => (
              <button
                key={id}
                onClick={() => switchSource(id)}
                className={`px-2 py-1 rounded-md transition-colors ${
                  dataSource === id ? "bg-sky-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {running && !status.external_collector ? (
            <button
              onClick={stop}
              className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 text-xs font-bold flex items-center gap-1.5"
            >
              <Square className="w-3 h-3" /> Stop reading
            </button>
          ) : null}
        </div>
      </div>

      {error && (
        <div className="mt-3 p-2.5 rounded bg-rose-500/10 border border-rose-500/25 text-rose-300 text-[11px]">{error}</div>
      )}
      {status?.error && (
        <div className="mt-3 p-2.5 rounded bg-amber-500/10 border border-amber-500/25 text-amber-300 text-[11px]">
          Last reading failed: {status.error}
        </div>
      )}

      {!running && (
        <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 space-y-1.5 text-[12px] text-slate-300">
            <p>
              Detects your OS, CPU, GPU, NPU and battery, finds the AI apps and models on this computer, then
              measures how many watts they use every 2 seconds.
            </p>
            <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              Everything stays on this computer. Only model names and token counts are read from app logs, never
              prompts or code.
            </p>
            {!viewingDevice && (
              <p className="flex items-center gap-1.5 text-[11px] text-amber-300">
                <Database className="w-3.5 h-3.5 shrink-0" /> The dashboard is showing sample data (John's gaming PC).
              </p>
            )}
          </div>
          <button
            onClick={start}
            disabled={starting}
            className="px-5 py-3 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-60 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-sm shrink-0"
          >
            {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {starting ? "Detecting your device…" : system ? "Start reading again" : "Start reading my device"}
          </button>
        </div>
      )}

      {showDetails && (
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-3">
          <DevicePanel system={system} sensors={sensors} />
          {running ? <AppsPanel status={status} /> : (
            <Panel icon={Bot} title="AI apps running now">
              <div className="text-[11px] text-slate-400">Reading stopped. {status?.stored_samples || 0} samples saved.</div>
            </Panel>
          )}
          <ModelsPanel models={models} />
        </div>
      )}
    </section>
  );
}
