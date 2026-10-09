import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import {
  Laptop,
  Play,
  Square,
  Loader2,
  Bot,
  Cloud,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import { formatWatts, formatWh, formatTokens, formatAppWatts, peso } from "../format";
import AppPowerParts from "./AppPowerParts";
import { CardHeader } from "./Card";

const SENSOR_LABELS = { system: "Whole machine", cpu: "CPU", gpu: "GPU", memory: "Memory", disk: "Disk" };

function Row({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-line last:border-0">
      <span className="text-xs text-ink-muted shrink-0">{label}</span>
      <span className="text-xs font-medium text-ink text-right min-w-0 break-words">{children}</span>
    </div>
  );
}

function Panel({ icon: Icon, title, children }) {
  return (
    <div className="inset-panel p-4 min-w-0">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-4 h-4 text-ink-muted" />
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
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
        <div className="mt-3 pt-3 border-t border-line space-y-1.5">
          <div className="text-xs font-medium text-ink-muted">Power readings</div>
          {Object.entries(sensors).map(([part, sensor]) => (
            <div key={part} className="flex items-center justify-between gap-2 text-xs">
              <span className="text-ink-soft">{SENSOR_LABELS[part] || part}</span>
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
            <span className="font-bold tabular-nums">{formatWatts(latest.measured_watts ?? latest.est_watts)}</span>{" "}
            <span className="font-normal text-ink-muted">{latest.measured_watts != null ? "measured" : "estimated"}</span>
          </Row>
          <Row label="AI apps">
            <span className="font-bold tabular-nums">{formatWatts(aiWatts)}</span>{" "}
            <span className="font-normal text-ink-muted">calculated share</span>
          </Row>
          <div className="mt-3 space-y-2.5">
            {apps.length === 0 && <div className="text-xs text-ink-muted">No AI apps running.</div>}
            {apps.map((a, i) => (
              <div key={`${a.model || a.app}-${a.host}-${i}`} className="flex items-start justify-between gap-2 text-xs">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-ink truncate">{a.model || a.app}</div>
                  <div className="text-xs text-ink-muted tabular-nums">
                    {a.kind === "local" ? "local model" : "cloud client"}
                    {a.host ? ` · in ${a.host}` : ""}{a.effort ? ` · ${a.effort} effort` : ""} · {(a.cpu_percent || 0).toFixed(1)}% CPU
                  </div>
                  <AppPowerParts app={a} />
                </div>
                <span className="text-sm font-semibold tabular-nums text-ink shrink-0">{formatAppWatts(a.watts || 0)}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="text-xs text-ink-muted flex items-center gap-2">
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
        <div className="text-xs text-ink-muted flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading app logs…
        </div>
      </Panel>
    );
  }
  const unmeasurable = models.extensions.filter((e) => !e.measurable);
  return (
    <Panel icon={Cloud} title={`Models found (last ${models.days} days)`}>
      {models.models.length === 0 && (
        <div className="text-xs text-ink-muted">No AI model usage found in Claude Code, Codex, Copilot, Kiro, Amazon Q, OpenCode or Gemini CLI.</div>
      )}
      <div className="space-y-2.5">
        {models.models.map((m) => (
          <div key={`${m.app}-${m.model}`} className="flex items-start justify-between gap-2 text-xs">
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink truncate">
                {m.name} <span className="font-normal text-ink-muted">· {m.app}</span>
              </div>
              <div className="text-xs text-ink-muted tabular-nums">
                {m.requests} requests
                {m.tokens.output ? ` · ${formatTokens(m.tokens.output)} output tokens` : " · no token counts"}
                {m.relative_energy ? ` · ${m.priced_as ? "≈" : ""}${m.relative_energy}× Sonnet` : ""}
                {m.priced_as ? ` · not in catalog, priced like ${m.priced_as}` : ""}
                {m.relative_energy == null ? ` · ${m.provider ? `${m.provider} model` : "model"} not in catalog, no estimate` : ""}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-sm font-semibold tabular-nums text-ink">{formatWh(m.datacenter_wh)}</div>
              <div className="text-[11px] text-ink-muted">data center · est.</div>
              {m.device_kwh != null && (
                <div className="tabular-nums text-xs text-accent mt-0.5">
                  {formatWh(m.device_kwh * 1000)} · {peso(m.device_cost)} <span className="text-ink-muted">on this device</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {models.switch_hint && (
        <div className="notice notice-warn mt-3">
          <AlertTriangle />
          <span>{models.switch_hint.message}</span>
        </div>
      )}
      {unmeasurable.length > 0 && (
        <div className="mt-3 text-xs text-ink-muted">
          Installed, can't be measured separately: {unmeasurable.map((e) => e.name).join(", ")}
        </div>
      )}
      <div className="mt-2 text-xs text-ink-muted">
        Estimated from list prices; {models.reference.source}. Not on your bill.
      </div>
    </Panel>
  );
}

export default function DeviceReader({ params, onDataChanged }) {
  const [status, setStatus] = useState(null);
  const [system, setSystem] = useState(null);
  const [sensors, setSensors] = useState(null);
  const [models, setModels] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  const running = status?.running || status?.external_collector;

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

  const showDetails = running || system;

  return (
    <section className="dash-card p-5 min-w-0">
      <CardHeader
        title="Device reader"
        sub={
          running
            ? `Reading every 2 s · ${status.samples || status.stored_samples} samples${status.external_collector ? " (collect.py)" : ""}`
            : "Measures the AI apps on this computer"
        }
      >
        <span className={`tech-tag ${running ? "tech-tag-live" : "tech-tag-neutral"}`}>{running ? "Reading" : "Stopped"}</span>
        {running && !status.external_collector && (
          <button onClick={stop} className="btn">
            <Square className="w-3 h-3" /> Stop reading
          </button>
        )}
      </CardHeader>

      {error && (
        <div role="alert" className="notice notice-neg mt-4">
          <AlertTriangle />
          <span>{error}</span>
        </div>
      )}
      {status?.error && (
        <div className="notice notice-warn mt-4">
          <AlertTriangle />
          <span>Last reading failed: {status.error}</span>
        </div>
      )}

      {!running && (
        <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 space-y-2 text-sm text-ink-soft leading-relaxed">
            <p>
              Detects your OS, CPU, GPU, NPU and battery, finds the AI apps and models on this computer, then
              measures how many watts they use every 2 seconds.
            </p>
            <p className="flex items-center gap-1.5 text-xs text-ink-muted">
              <ShieldCheck className="w-4 h-4 text-pos shrink-0" />
              Everything stays on this computer. Only model names and token counts are read from app logs, never
              prompts or code.
            </p>
          </div>
          <button onClick={start} disabled={starting} className="btn-primary px-5 py-2.5 text-sm shrink-0">
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
              <div className="text-xs text-ink-muted">Reading stopped. {status?.stored_samples || 0} samples saved.</div>
            </Panel>
          )}
          <ModelsPanel models={models} />
        </div>
      )}
    </section>
  );
}
