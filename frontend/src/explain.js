/**
 * Plain-language explanations of the live reading: why power is being used (or not),
 * what each AI app is doing, and what the numbers mean.
 */

import { formatWatts } from "./format";

// What each `activity` from the backend (attribution.activity) means for the user.
// TODO: Add more activities and their meanings

export const ACTIVITY = {
  working: {
    label: "Working",
    chip: "tech-tag-pos",
  },
  background: {
    label: "Background",
    chip: "tech-tag-live",
  },
  loaded: {
    label: "Loaded",
    chip: "tech-tag-sim",
  },
  idle: {
    label: "Idle",
    chip: "tech-tag-neutral text-ink-muted",
  },
};

const isToolRuns = (app) => (app.model || "").endsWith("· tool runs");

// One sentence on why this app is (or isn't) using power right now.
export function explainApp(app) {
  const tool = isToolRuns(app);
  switch (app.activity) {
    case "working":
      if (app.kind === "local")
        return "Generating on this computer: the model runs on your own CPU/GPU, so all of its power is on your bill.";
      if (tool) return `Commands ${app.app} started for you (tests, builds, scripts) are running on this computer.`;
      return "Using noticeable CPU here, usually from streaming a reply, running tools or indexing files. The model itself runs in the provider's data center.";
    case "background":
      return tool
        ? `Commands ${app.app} started are mostly waiting; they use a little CPU.`
        : "Open and doing light upkeep (syncing, watching files). Not answering a prompt.";
    case "loaded":
      return "Held in memory, ready for the next prompt, but not generating. Ollama unloads it after about 5 minutes without use.";
    case "idle":
      if (tool) return `Commands ${app.app} started are still open but idle (e.g. a server waiting for requests).`;
      return app.model && app.kind === "client"
        ? "Open and waiting for a prompt. The model name is the last one it used, not one running now."
        : "Open and waiting for a prompt. Uses almost no power.";
    default:
      return null;
  }
}

const names = (apps) => {
  const list = apps.map((a) => a.name || a.model || a.app);
  return list.length <= 2 ? list.join(" and ") : `${list.slice(0, 2).join(", ")} and ${list.length - 2} more`;
};

// A few sentences on why the computer draws what it draws right now.
export function explainReading(reading) {
  if (!reading) return [];
  const total = reading.watts ?? 0;
  if (reading.source !== "collector") {
    return [
      `Your computer is drawing about ${formatWatts(total)}.`,
      "Start the device reader (This Device) to see which AI apps use that power and why.",
    ];
  }

  const apps = reading.apps || [];
  const ai = reading.ai_watts ?? apps.reduce((s, a) => s + (a.watts || 0), 0);
  const share = total > 0 ? Math.round((ai / total) * 100) : 0;
  const working = apps.filter((a) => a.activity === "working");
  const local = working.filter((a) => a.kind === "local");
  const loaded = apps.filter((a) => a.activity === "loaded");

  const out = [];
  if (local.length) {
    out.push(`${names(local)} ${local.length > 1 ? "are" : "is"} generating on this computer, which is why the power is up.`);
  } else if (working.length) {
    out.push(`${names(working)} ${working.length > 1 ? "are" : "is"} busy on this computer right now.`);
  } else if (apps.length) {
    out.push("No AI app is working right now. The ones listed are just open, waiting for a prompt.");
  } else {
    out.push("No AI apps are open.");
  }

  if (apps.length) {
    out.push(`AI apps use ${formatWatts(ai)} of the ${formatWatts(total)} your computer draws (${share}%).`);
  }

  if (share < 50) {
    out.push(`The other ${formatWatts(Math.max(total - ai, 0))} is the rest of the computer (screen, system, other apps) and is used with or without AI.`);
  }

  if (loaded.length) {
    out.push(`${names(loaded)} ${loaded.length > 1 ? "are" : "is"} loaded in memory but not generating.`);
  }
  if (working.length && !local.length) {
    out.push("Cloud models run in the provider's data center; only the app's own work on this computer is counted here.");
  }
  return out;
}

// What the numbers on the live panel mean.
export const METRICS = [
  {
    term: "Watts (W)",
    text: "How much power is being used right now. 1 W for one hour is 1 Wh; 1,000 Wh is 1 kWh, the unit your electricity bill charges for.",
  },
  {
    term: "Measured / Estimated",
    text: "Measured: read from the computer's own power sensor. Estimated: calculated from CPU and GPU use with a formula calibrated to this computer.",
  },
  {
    term: "Load %",
    text: "How far the needle is on the dial. The dial resizes to fit your readings, so it isn't a percentage of the computer's maximum.",
  },
  {
    term: "CPU %",
    text: "How much of one processor core the app keeps busy. 100% is one core fully busy; it can go above 100% on computers with several cores.",
  },
  {
    term: "CPU / GPU / RAM watts",
    text: "The app's share of each part's power. Power the computer uses while doing nothing is never charged to an app.",
  },
  {
    term: "Where the watts go",
    text: "By part: what the CPU, GPU, RAM and disk draw; the rest is the screen, Wi-Fi, fans and board. By use: AI apps, other apps and the OS, and the baseline the computer draws even when doing nothing.",
  },
  {
    term: "Holds RAM",
    text: "Memory the app keeps reserved. Holding memory costs little power; reading and writing it while generating costs more.",
  },
  {
    term: "Working / Background / Loaded / Idle",
    text: "Working: generating, streaming or running tools. Background: open with light upkeep. Loaded: a local model in memory, not generating. Idle: open, waiting for a prompt.",
  },
];
