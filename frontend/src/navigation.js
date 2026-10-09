import { Activity, BarChart2, Cpu, Laptop, Leaf, Settings, Sliders, Target } from "lucide-react";

// Sidebar groups. Each item is its own view in App, except "settings" which opens the tariff modal.
export const NAV_GROUPS = [
  {
    label: "Monitor",
    items: [
      {
        id: "dashboard",
        label: "Telemetry console",
        icon: Activity,
        title: "Telemetry console",
        description: "Live power draw, current bill and where this cycle is heading.",
      },
      {
        id: "device",
        label: "This device",
        icon: Laptop,
        title: "This device",
        description: "Hardware, power sensors and the AI processes being read on this machine.",
      },
    ],
  },
  {
    label: "Analysis",
    items: [
      {
        id: "analytics",
        label: "Billing projection",
        icon: BarChart2,
        title: "Billing projection",
        description: "Projected end-of-cycle bill and how much of it comes from AI workloads.",
      },
      {
        id: "accuracy",
        label: "Forecast accuracy",
        icon: Target,
        title: "Forecast accuracy",
        description: "Accuracy, precision, recall and F1 of the fine-tuned models on readings they never saw.",
      },
      {
        id: "models",
        label: "Model runtimes",
        icon: Cpu,
        title: "Model runtimes",
        description: "Energy and cost per model for the selected window.",
      },
      {
        id: "carbon",
        label: "Carbon ledger",
        icon: Leaf,
        title: "Carbon ledger",
        description: "CO₂ from AI on this device and in cloud data centers, and what the recommendations avoid.",
      },
      {
        id: "recommendations",
        label: "Recommendations",
        icon: Sliders,
        title: "Recommendations",
        description: "Suggested workload changes and what each one saves.",
      },
    ],
  },
  {
    label: "Configuration",
    items: [{ id: "settings", label: "Tariff & bill", icon: Settings }],
  },
];

export const VIEWS = Object.fromEntries(
  NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.id !== "settings").map((i) => [i.id, i])
);
