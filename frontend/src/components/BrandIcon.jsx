import { AppWindow, SquareTerminal } from "lucide-react";

// Logo file (public/brands/<file>.svg) for each AI app and host the device reader names
// (backend ai_processes.py AI_APPS and HOSTS), keyed by the name in lowercase.
const BRANDS = {
  "ollama": "ollama",
  "lm studio": "lmstudio",
  "mlx": "apple",
  "claude desktop": "claude",
  "claude code": "claudecode",
  "codex": "codex",
  "amazon q": "aws",
  "chatgpt": "openai",
  "cursor": "cursor",
  "windsurf": "windsurf",
  "trae": "trae",
  "devin": "devin",
  "devin desktop": "devin",
  "antigravity": "antigravity",
  "kiro": "kiro",
  "kiro crew": "kiro",
  "gemini cli": "geminicli",
  "opencode": "opencode",
  "github copilot": "githubcopilot",
  "vs code": "vscode",
  "vs code insiders": "vscode",
  "vscodium": "vscodium",
  "zed": "zed",
  "intellij idea": "intellij",
  "pycharm": "pycharm",
  "webstorm": "webstorm",
  "goland": "goland",
  "phpstorm": "phpstorm",
  "rubymine": "rubymine",
  "clion": "clion",
  "rider": "rider",
  "datagrip": "datagrip",
  "rustrover": "jetbrains",
  "android studio": "androidstudio",
  "xcode": "xcode",
  "iterm": "iterm",
  "warp": "warp",
  "ghostty": "ghostty",
  "wezterm": "wezterm",
  "alacritty": "alacritty",
  "hyper": "hyper",
  "gnome terminal": "gnometerminal",
  "powershell": "powershell",
};

// Hosts with no logo of their own.
const GLYPHS = {
  "terminal": SquareTerminal,
  "kitty": SquareTerminal,
  "tabby": SquareTerminal,
  "konsole": SquareTerminal,
  "windows terminal": SquareTerminal,
  "orca": AppWindow,
};

// Who makes a model, from its id (the patterns of backend models_catalog.PROVIDERS).
const MODEL_MAKERS = [
  [/claude/, "claude"],
  [/(^|[/.])(gpt|o\d|codex|chatgpt)/, "openai"],
  [/gemini|gemma/, "gemini"],
  [/llama/, "meta"],
  [/mistral|mixtral|codestral|devstral/, "mistral"],
  [/deepseek/, "deepseek"],
  [/grok/, "xai"],
  [/qwen/, "qwen"],
];

// Single-colour logos: drawn in the text colour, so they follow the theme. The rest keep
// their brand colours.
const MONO = new Set(["apple", "aws", "cursor", "ghostty", "githubcopilot", "gnometerminal", "hyper", "iterm",
  "lmstudio", "ollama", "openai", "opencode", "powershell", "wezterm", "windsurf", "xai", "zed"]);

// `name` is an app or host ("Claude Code", "VS Code"), a usage row ("Claude Code · claude-opus-5-5",
// "Ollama · llama3.2") or a bare model id. The app decides the logo; failing that, the model's maker.
function resolve(name) {
  const parts = (name || "").toLowerCase().split(" · ");
  if (BRANDS[parts[0]]) return { file: BRANDS[parts[0]] };
  if (GLYPHS[parts[0]]) return { Glyph: GLYPHS[parts[0]] };
  const maker = MODEL_MAKERS.find(([pattern]) => pattern.test(parts[parts.length - 1]));
  return maker ? { file: maker[1] } : {};
}

/**
 * The logo of an AI app, editor, terminal or model maker. Decorative: the name is always
 * written next to it. `fallback` is the icon for names with no logo (none: nothing is drawn).
 */
export default function BrandIcon({ name, fallback: Fallback, className = "w-4 h-4" }) {
  const { file, Glyph = Fallback } = resolve(name);
  // Inline, so it also sits in a line of text ("in [logo] VS Code").
  const box = `${className} inline-block align-middle shrink-0`;
  if (!file) return Glyph ? <Glyph className={`${box} text-ink-muted`} aria-hidden /> : null;
  const url = `/brands/${file}.svg`;
  if (MONO.has(file)) {
    const mask = `url(${url}) center / contain no-repeat`;
    return <span className={`${box} bg-ink`} style={{ mask, WebkitMask: mask }} aria-hidden />;
  }
  return <img src={url} alt="" className={box} />;
}

// A name with its logo in front, for use inside a line of text.
export function BrandName({ name }) {
  return (
    <>
      <BrandIcon name={name} className="w-3.5 h-3.5" /> {name}
    </>
  );
}
