/**
 * Plain-language explanations of the live reading: why power is being used (or not),
 * what each AI app is doing, and what the numbers mean.
 */

import { formatCo2, formatWatts, shortDate } from "./format";

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

const pct = (x) => `${Math.round(x * 100)}%`;
const count = (n) => Math.round(n).toLocaleString("en-PH");

// The Carbon Ledger in a few plain sentences, from the figures the backend worked out
// (carbon.insights). Each item: {key, text}, so the page can show them as a list.
export function explainCarbon(carbon) {
  if (!carbon) return [];
  const { totals, insights: ins = {}, budget, top_actions: actions = [], window } = carbon;
  const span = window?.label?.toLowerCase() || "in this window";
  if (!totals.total_kg) {
    return [{ key: "none", text: `No CO₂ from AI was recorded ${span}. Start the device reader in This Device to measure it.` }];
  }

  const out = [];
  const eq = ins.equivalents || {};
  out.push({
    key: "size",
    text: `Your AI use caused ${formatCo2(totals.total_kg)} ${span}: about as much as driving a car ${count(eq.car_km)} km, or charging a phone ${count(eq.phone_charges)} times.`,
  });

  const cloud = ins.cloud_share ?? 0;
  out.push({
    key: "where",
    text:
      cloud >= 0.995
        ? "Almost all of it (over 99%) came from cloud data centers running models like Claude. That CO₂ isn't on your electricity bill, but it still counts."
        : cloud <= 0.005
        ? "Almost all of it (over 99%) came from this computer, so the same energy is on your electricity bill too."
        : cloud >= 0.5
        ? `${pct(cloud)} of it came from cloud data centers running models like Claude. That CO₂ isn't on your electricity bill, but it still counts.`
        : `${pct(1 - cloud)} of it came from this computer, so the same energy is on your electricity bill too.`,
  });

  const peak = ins.peak_day;
  if (peak && ins.active_days > 1) {
    out.push({
      key: "peak",
      text: `${shortDate(peak.date)} was your heaviest day at ${formatCo2(peak.kg)}, ${pct(peak.share)} of the total.`,
    });
  }

  const trend = ins.trend;
  if (trend?.direction === "up") {
    out.push({
      key: "trend",
      text: `It's rising: since ${shortDate(trend.split_date)} you've averaged ${formatCo2(trend.later_avg_kg)} a day, up from ${formatCo2(trend.earlier_avg_kg)}.`,
    });
  } else if (trend?.direction === "down") {
    out.push({
      key: "trend",
      text: `It's falling: since ${shortDate(trend.split_date)} you've averaged ${formatCo2(trend.later_avg_kg)} a day, down from ${formatCo2(trend.earlier_avg_kg)}.`,
    });
  } else if (trend?.direction === "flat") {
    out.push({ key: "trend", text: `It's steady at about ${formatCo2(ins.avg_per_day_kg)} a day.` });
  }

  if (budget) {
    const now = pct(budget.used_share);
    const recs = pct(budget.used_share_with_recommendations);
    out.push({
      key: "budget",
      text:
        budget.status === "under"
          ? `This cycle is on track: ${now} of your ${budget.kg} kg CO₂ budget.`
          : budget.status === "fixed_by_recommendations"
          ? `This cycle is heading for ${now} of your ${budget.kg} kg CO₂ budget. Following the recommendations would bring it to ${recs}.`
          : `This cycle is heading for ${now} of your ${budget.kg} kg CO₂ budget, and still ${recs} with the recommendations.`,
    });
  }

  const top = actions[0];
  if (top) {
    out.push({
      key: "action",
      text: `The biggest single cut would save about ${formatCo2(top.co2_saved_kg)} a month (${top.model}; see Biggest CO₂ cuts below).`,
    });
  }
  return out;
}

// What the words on the Carbon Ledger mean.
export const CARBON_TERMS = [
  {
    term: "CO₂ (kg, g)",
    text: "Carbon dioxide, the main gas that warms the climate. Power plants release it when they make electricity. 1 kg is 1,000 g.",
  },
  {
    term: "This device",
    text: "CO₂ from the electricity this computer used for AI: measured kWh times the local grid's factor. The same energy is on your bill.",
  },
  {
    term: "Cloud data centers",
    text: "CO₂ from the servers that run cloud models like Claude or GPT. Estimated from the tokens you used, so treat it as a ranking rather than an exact figure. It is never on your bill.",
  },
  {
    term: "Grid factor (kg CO₂/kWh)",
    text: "How much CO₂ the grid releases for each kWh. It is higher when coal and gas plants supply more of the power, and changes by the hour (see Cleanest hours).",
  },
  {
    term: "Carbon budget",
    text: "A monthly CO₂ cap you set in Tariff & bill. The bar shows where this cycle is heading; the marker shows where the recommendations would bring it.",
  },
  {
    term: "Recommendations",
    text: "The app's suggested changes (a smaller model, unloading an idle one, running in cleaner hours) with the CO₂ and pesos each one saves.",
  },
  {
    term: "Trees",
    text: "A mature tree absorbs about 22 kg of CO₂ a year (1.8 kg a month). It turns a CO₂ figure into something you can picture.",
  },
];
