# collection-search-prototype

Astro prototype for the FAMSF collection website hero — a search "console" where
the FAMSF brand forward-slash doubles as the prompt. The field self-types
collection terms (`/art` → `/sculpture` → `/rodin` …), deleting each a character
at a time, and hands control to the visitor on first interaction.

Built against the real FAMSF design system: **Akzidenz-Grotesk Next Pro** (Adobe
Typekit kit `tpb7nan`) and **Signifier** (self-hosted woff2). Figma reference:
node `82:1028`.

## Stack

- **Astro** — static output
- **Tailwind CSS 4** — via `@tailwindcss/vite`; tokens in `src/styles/global.css`
- **Node** — >= 22.12

## Commands

Run from the repo root:

| Command | Action |
| :--- | :--- |
| `npm install` | Install dependencies |
| `npm run dev` | Dev server at `localhost:4321` |
| `npm run build` | Production build to `./dist/` |
| `npm run preview` | Preview the build locally |

## Structure

```
src/
├── layouts/Layout.astro          Base HTML shell (fonts, meta)
├── styles/global.css             Design tokens + @font-face
├── components/HeroConsole.astro  The console hero (markup + typing script)
└── pages/
    ├── index.astro               Prototype directory
    └── hero.astro                The console hero in page context
public/
├── standard.jpg                  Ruscha "Standard Station" backdrop
└── fonts/signifier/              Self-hosted Signifier woff2
```

## Deploy

Pushed to `main` → GitHub Actions builds and publishes to GitHub Pages at
<https://famsf.github.io/collection-search-prototype/>. The Astro `base` path is
set accordingly in `astro.config.mjs`.
