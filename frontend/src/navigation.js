import { Activity, BarChart2, Cpu, Laptop, Leaf, Settings, Sliders, Target } from "lucide-react";

// Sidebar groups. Each item is its own view in App, except "settings" which opens the tariff modal.
export const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      {
        id: "dashboard",
        label: "Telemetry Console",
        icon: Activity,
        title: "Telemetry Console",
        description: "Live power draw, current bill and where this cycle is heading.",
      },
      {
        id: "device",
        label: "This Device",
        icon: Laptop,
        title: "This Device",
        description: "Hardware, power sensors and the AI processes being read on this machine.",
      },
    ],
  },
  {
    label: "Analysis",
    items: [
      {
        id: "analytics",
        label: "Billing Projection",
        icon: BarChart2,
        title: "Billing Projection",
        description: "Projected end-of-cycle bill and how much of it comes from AI workloads.",
      },
      {
        id: "accuracy",
        label: "Forecast Accuracy",
        icon: Target,
        title: "Forecast Accuracy",
        description: "Accuracy, precision, recall and F1 of the fine-tuned models on readings they never saw.",
      },
      {
        id: "models",
        label: "Model Runtimes",
        icon: Cpu,
        title: "Model Runtimes",
        description: "Energy and cost per model for the selected window.",
      },
      {
        id: "carbon",
        label: "Carbon Ledger",
        icon: Leaf,
        title: "Carbon Ledger",
        description: "CO₂ from AI on this device and in cloud data centers, and what the directives avoid.",
      },
      {
        id: "recommendations",
        label: "Load Directives",
        icon: Sliders,
        title: "Load Directives",
        description: "Suggested workload changes and what each one saves.",
      },
    ],
  },
  {
    label: "Configuration",
    items: [{ id: "settings", label: "Tariff & Hardware", icon: Settings }],
  },
];

export const VIEWS = Object.fromEntries(
  NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.id !== "settings").map((i) => [i.id, i])
);
