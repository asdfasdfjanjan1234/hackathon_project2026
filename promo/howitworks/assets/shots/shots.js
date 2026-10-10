window.SHOTS = {
 "ask-dark": {
  "src": "assets/shots/ask-dark.png",
  "w": 122.9,
  "h": 44
 },
 "window-dark": {
  "src": "assets/shots/window-dark.png",
  "w": 1600,
  "h": 1000
 },
 "main-dark": {
  "src": "assets/shots/main-dark.png",
  "w": 1360,
  "h": 1800
 },
 "ask-light": {
  "src": "assets/shots/ask-light.png",
  "w": 122.9,
  "h": 44
 },
 "window-light": {
  "src": "assets/shots/window-light.png",
  "w": 1600,
  "h": 1000
 },
 "main-light": {
  "src": "assets/shots/main-light.png",
  "w": 1360,
  "h": 1800
 },
 "verdict": {
  "src": "assets/shots/verdict.png",
  "w": 1296,
  "h": 502.6
 },
 "recs": {
  "src": "assets/shots/recs.png",
  "w": 1296,
  "h": 442
 }
};
window.WHERE = {
 "main": {
  "x": 240,
  "y": 64,
  "w": 1360,
  "h": 936
 },
 "toggle": {
  "light": {
   "x": 1435,
   "y": 20.5,
   "w": 30,
   "h": 22
  },
  "dark": {
   "x": 1495,
   "y": 20.5,
   "w": 30,
   "h": 22
  }
 },
 "ask": {
  "x": 1453.1,
  "y": 932,
  "w": 122.9,
  "h": 44
 },
 "stats": {
  "watts": {
   "x": 32,
   "y": 228,
   "w": 310,
   "h": 301.1
  },
  "energy": {
   "x": 358,
   "y": 228,
   "w": 310,
   "h": 301.1
  },
  "cost": {
   "x": 32,
   "y": 545.1,
   "w": 310,
   "h": 312.1
  },
  "bill": {
   "x": 358,
   "y": 545.1,
   "w": 310,
   "h": 312.1
  }
 },
 "apps": {
  "x": 692,
  "y": 881.1,
  "w": 636,
  "h": 783.4
 },
 "draw": {
  "x": 32,
  "y": 881.1,
  "w": 636,
  "h": 783.4
 },
 "verdict": {
  "cut": 318.1
 },
 "recs": {
  "savings": {
   "x": 1184.6,
   "y": 21,
   "w": 90.4,
   "h": 54.5
  },
  "saves": [
   {
    "x": 1088.3,
    "y": 108.5,
    "w": 84.8,
    "h": 56
   },
   {
    "x": 1069.8,
    "y": 206.2,
    "w": 77.7,
    "h": 56
   }
  ],
  "apply": {
   "x": 1163.5,
   "y": 220.2,
   "w": 111.5,
   "h": 28
  }
 }
};
window.FACTS = {
 "taken": "2026-10-10 07:34",
 "device": "MacBook Air (Mac14,2)",
 "cpu": "Apple M2",
 "os": "macos",
 "sensors": {
  "cpu": null,
  "disk": null,
  "gpu": "IOReport GPU Energy",
  "memory": null,
  "system": "battery (ioreg)"
 },
 "power_model": {
  "fitted_on": 500,
  "idle_watts": 2.4949012232466465,
  "watts_per_cpu_pct": 0.14392472660747577,
  "watts_per_gpu_pct": 0.11783246676378621
 },
 "stored_samples": 30791,
 "live": {
  "watts": 13.0,
  "ai_watts": 4.52,
  "cpu_percent": 19.2,
  "gpu_percent": 96.0,
  "components": {
   "cpu": {
    "source": "estimated",
    "watts": 0.459
   },
   "disk": {
    "source": "estimated",
    "watts": 0.051
   },
   "gpu": {
    "source": "IOReport GPU Energy",
    "watts": 3.527
   },
   "memory": {
    "source": "estimated",
    "watts": 2.784
   },
   "other": {
    "source": "system − components",
    "watts": 6.162
   }
  },
  "apps": [
   {
    "name": "Ollama · qwen3.5:4b-q4_K_M",
    "kind": "local",
    "activity": "working",
    "watts": 4.489
   },
   {
    "name": "Claude Code · claude-opus-5-5",
    "kind": "client",
    "activity": "background",
    "watts": 0.02
   },
   {
    "name": "Claude Code · tool runs",
    "kind": "client",
    "activity": "idle",
    "watts": 0.005
   },
   {
    "name": "Ollama",
    "kind": "local",
    "activity": "idle",
    "watts": 0.005
   },
   {
    "name": "GitHub Copilot · gpt-4o-mini-2024-07-18",
    "kind": "client",
    "activity": "idle",
    "watts": 0.002
   }
  ]
 },
 "readings": [
  {
   "ts": 1791588841.844413,
   "watts": 12.983,
   "measured": true,
   "cpu": 20.8,
   "gpu": 97.0,
   "ai": 4.19
  },
  {
   "ts": 1791588839.742487,
   "watts": 12.983,
   "measured": true,
   "cpu": 32.7,
   "gpu": 98.0,
   "ai": 3.98
  },
  {
   "ts": 1791588837.512335,
   "watts": 12.983,
   "measured": true,
   "cpu": 59.1,
   "gpu": 97.0,
   "ai": 4.33
  },
  {
   "ts": 1791588835.214033,
   "watts": 12.983,
   "measured": true,
   "cpu": 60.3,
   "gpu": 97.0,
   "ai": 3.54
  },
  {
   "ts": 1791588832.9324448,
   "watts": 12.983,
   "measured": true,
   "cpu": 56.0,
   "gpu": 95.0,
   "ai": 3.89
  },
  {
   "ts": 1791588830.691099,
   "watts": 12.983,
   "measured": true,
   "cpu": 78.0,
   "gpu": 94.0,
   "ai": 6.38
  },
  {
   "ts": 1791588828.478988,
   "watts": 12.983,
   "measured": true,
   "cpu": 76.1,
   "gpu": 83.0,
   "ai": 1.67
  },
  {
   "ts": 1791588826.376137,
   "watts": 12.983,
   "measured": true,
   "cpu": 19.2,
   "gpu": 96.0,
   "ai": 4.52
  }
 ],
 "bill": {
  "baseline_bill": 1500.0,
  "current_bill": 2500.0,
  "increase": 1000.0,
  "ai_effect": 4.58,
  "other_effect": 995.42,
  "rate_effect": 0.0,
  "local_ai_kwh": 0.381817
 },
 "ai_share_pct": 0.5,
 "forecast": {
  "bill": 1510.83,
  "baseline": 1500.0,
  "ai_cost": 10.83,
  "range": {
   "high": 1517.22,
   "low": 1504.43
  },
  "budget": 2000.0,
  "cycle": {
   "days": 31,
   "end": "2026-10-31",
   "start": "2026-10-01",
   "start_day": 1
  },
  "days_left": 22,
  "method": "arima",
  "interval": 0.8,
  "beats_baselines": true,
  "models": {
   "Claude Code": "ARIMA(2,0,1)",
   "Devin Desktop": "ARIMA(2,0,1)",
   "Kiro": "ARIMA(1,0,1)",
   "Ollama": "ARIMA(1,0,1)",
   "Other AI apps": "Routine only"
  },
  "daily": [
   {
    "date": "2026-10-01",
    "ai_cost": 0.39,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-02",
    "ai_cost": 0.3,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-03",
    "ai_cost": 0.25,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-04",
    "ai_cost": 0.29,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-05",
    "ai_cost": 0.33,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-06",
    "ai_cost": 0.3,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-07",
    "ai_cost": 0.25,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-08",
    "ai_cost": 0.31,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-09",
    "ai_cost": 0.18,
    "past": true,
    "today": false
   },
   {
    "date": "2026-10-10",
    "ai_cost": 0.46,
    "past": false,
    "today": true
   },
   {
    "date": "2026-10-11",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-12",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-13",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-14",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-15",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-16",
    "ai_cost": 0.35,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-17",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-18",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-19",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-20",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-21",
    "ai_cost": 0.36,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-22",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-23",
    "ai_cost": 0.36,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-24",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-25",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-26",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-27",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-28",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-29",
    "ai_cost": 0.38,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-30",
    "ai_cost": 0.35,
    "past": false,
    "today": false
   },
   {
    "date": "2026-10-31",
    "ai_cost": 0.37,
    "past": false,
    "today": false
   }
  ]
 },
 "accuracy": {
  "accuracy": 0.7333333333333333,
  "precision": 0.9411764705882353,
  "recall": 0.5161290322580645,
  "f1": 0.6666666666666666,
  "steps": 60
 },
 "accuracy_step_minutes": 15,
 "savings": {
  "pesos": 1.52,
  "co2_kg": 1.6355,
  "count": 3
 },
 "kilo": {
  "question": "How much is AI adding to my bill?",
  "reply": "AI is adding ₱10.83 to your bill this cycle, which is ₱10.83 more than the ₱1,500 household bill before AI use. This brings your total forecast to ₱1,510.83, keeping you under your ₱2,000 budget by ₱489.17. The biggest cost comes from local models like Ollama at ₱6.00 and cloud apps like Claude Code at ₱2.77.",
  "pieces": [
   [
    20.485,
    "AI"
   ],
   [
    20.546,
    " is"
   ],
   [
    20.606,
    " adding"
   ],
   [
    20.732,
    " ₱"
   ],
   [
    20.793,
    "1"
   ],
   [
    20.855,
    "0"
   ],
   [
    20.916,
    "."
   ],
   [
    20.977,
    "8"
   ],
   [
    21.039,
    "3"
   ],
   [
    21.1,
    " to"
   ],
   [
    21.162,
    " your"
   ],
   [
    21.224,
    " bill"
   ],
   [
    21.285,
    " this"
   ],
   [
    21.348,
    " cycle"
   ],
   [
    21.407,
    ","
   ],
   [
    21.466,
    " which"
   ],
   [
    21.526,
    " is"
   ],
   [
    21.649,
    " ₱"
   ],
   [
    21.713,
    "1"
   ],
   [
    21.776,
    "0"
   ],
   [
    21.838,
    "."
   ],
   [
    21.9,
    "8"
   ],
   [
    21.961,
    "3"
   ],
   [
    22.022,
    " more"
   ],
   [
    22.084,
    " than"
   ],
   [
    22.146,
    " the"
   ],
   [
    22.272,
    " ₱"
   ],
   [
    22.336,
    "1"
   ],
   [
    22.397,
    ","
   ],
   [
    22.46,
    "5"
   ],
   [
    22.523,
    "0"
   ],
   [
    22.592,
    "0"
   ],
   [
    22.65,
    " household"
   ],
   [
    22.712,
    " bill"
   ],
   [
    22.775,
    " before"
   ],
   [
    22.839,
    " AI"
   ],
   [
    22.902,
    " use"
   ],
   [
    22.965,
    "."
   ],
   [
    23.029,
    " This"
   ],
   [
    23.094,
    " brings"
   ],
   [
    23.157,
    " your"
   ],
   [
    23.223,
    " total"
   ],
   [
    23.291,
    " forecast"
   ],
   [
    23.358,
    " to"
   ],
   [
    23.494,
    " ₱"
   ],
   [
    23.553,
    "1"
   ],
   [
    23.616,
    ","
   ],
   [
    23.68,
    "5"
   ],
   [
    23.744,
    "1"
   ],
   [
    23.809,
    "0"
   ],
   [
    23.874,
    "."
   ],
   [
    23.939,
    "8"
   ],
   [
    24.004,
    "3"
   ],
   [
    24.069,
    ","
   ],
   [
    24.134,
    " keeping"
   ],
   [
    24.199,
    " you"
   ],
   [
    24.265,
    " under"
   ],
   [
    24.33,
    " your"
   ],
   [
    24.461,
    " ₱"
   ],
   [
    24.526,
    "2"
   ],
   [
    24.592,
    ","
   ],
   [
    24.658,
    "0"
   ],
   [
    24.727,
    "0"
   ],
   [
    24.791,
    "0"
   ],
   [
    24.861,
    " budget"
   ],
   [
    24.931,
    " by"
   ],
   [
    25.07,
    " ₱"
   ],
   [
    25.141,
    "4"
   ],
   [
    25.22,
    "8"
   ],
   [
    25.301,
    "9"
   ],
   [
    25.38,
    "."
   ],
   [
    25.455,
    "1"
   ],
   [
    25.528,
    "7"
   ],
   [
    25.589,
    "."
   ],
   [
    25.656,
    " The"
   ],
   [
    25.724,
    " biggest"
   ],
   [
    25.792,
    " cost"
   ],
   [
    25.863,
    " comes"
   ],
   [
    25.932,
    " from"
   ],
   [
    26.008,
    " local"
   ],
   [
    26.089,
    " models"
   ],
   [
    26.167,
    " like"
   ],
   [
    26.243,
    " O"
   ],
   [
    26.326,
    "ll"
   ],
   [
    26.406,
    "ama"
   ],
   [
    26.481,
    " at"
   ],
   [
    26.634,
    " ₱"
   ],
   [
    26.71,
    "6"
   ],
   [
    26.792,
    "."
   ],
   [
    26.873,
    "0"
   ],
   [
    26.949,
    "0"
   ],
   [
    27.029,
    " and"
   ],
   [
    27.109,
    " cloud"
   ],
   [
    27.19,
    " apps"
   ],
   [
    27.265,
    " like"
   ],
   [
    27.338,
    " Claude"
   ],
   [
    27.409,
    " Code"
   ],
   [
    27.478,
    " at"
   ],
   [
    27.625,
    " ₱"
   ],
   [
    27.698,
    "2"
   ],
   [
    27.774,
    "."
   ],
   [
    27.85,
    "7"
   ],
   [
    27.927,
    "7"
   ],
   [
    28.002,
    "."
   ]
  ],
  "figures": [
   "₱10.83",
   "₱10.83",
   "₱1,500",
   "₱1,510.83",
   "₱2,000",
   "₱489.17",
   "₱6.00",
   "₱2.77"
  ],
  "wrong": [],
  "first_word_s": 18.6,
  "tokens": 113,
  "tokens_per_second": 14.9,
  "model": "qwen3.5:4b-q4_K_M",
  "watts_while_answering": 5.2,
  "data": [
   "Forecast bill for this cycle: ₱1,510.83",
   "₱1,500 household bill before AI + ₱10.83 from AI on this computer",
   "Against the ₱2,000 budget: under by ₱489.17",
   "Biggest: Ollama ₱6.00, Claude Code ₱2.77"
  ]
 }
};
