# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Astro static-site prototype for the FAMSF collection website. A directory of
higher-fidelity **design surfaces** (hero, timeline, map), not production code:
each page is a self-contained demo for design review. Deployed to GitHub Pages
at <https://famsf.github.io/collection-search-prototype/>.

Part of the wider `~/git/famsf-collections/` workspace (see the workspace-root
`CLAUDE.md` for how the real Craft site, API, and ETL pipeline fit together).
This repo is prototype-only and never talks to the live API at runtime.

## Commands

Run from repo root. Plain `npm` (host Node ≥ 22.12), **not** DDEV.

| Command | Action |
| :--- | :--- |
| `npm run dev` | Dev server at `localhost:4321` |
| `npm run build` | Production build to `./dist/` |
| `npm run preview` | Preview the build |
| `npm run lint` | `biome check .` (lint + format check) |
| `npm run lint:fix` | `biome check --write .` |
| `npm run check` | `astro check` (type + `.astro` diagnostics) |
| `npm run format` | `biome format --write .` |

CI (`.github/workflows/deploy.yml`) runs `lint → check → build` on push to
`main`, then publishes `dist/` to Pages. Match that order locally before pushing.

Lefthook pre-commit: Biome (`--write`) on `js/ts/mjs/json`, `astro check` on
`.astro`. Biome **excludes** `.astro` files (see `biome.json`); `.astro` is
covered only by `astro check`, so run that after editing components.

## Architecture

**Every prototype is one page + pre-baked JSON.** No runtime API calls, no SSR,
no client framework. A page's `<script>` block `fetch()`es a static file from
`public/data/` (path-prefixed with `import.meta.env.BASE_URL`) and draws to the
DOM / inline SVG with vanilla JS. To add a demo: build its data file, write the
page, register it in the `routes` array in `src/pages/index.astro`.

- `src/pages/index.astro`: the demo directory. Editing the `routes` array is how
  a new surface becomes discoverable.
- `src/pages/{hero,hero-brackets,timeline,map,curator-picks}.astro`: the surfaces.
  `hero*` are the search-console concept (typing animation, Figma node `82:1028`);
  `timeline`, `map`, and `curator-picks` render real collection data.
- `src/components/Hero*.astro`: hero markup + typing script, kept out of the page.
- `src/layouts/Layout.astro`: the only layout. Loads fonts, imports `global.css`.
- `public/data/*.json|.ndjson`: the baked datasets fetched at runtime.

### The BASE_URL rule

`astro.config.mjs` sets `base: "/collection-search-prototype"` for Pages. **All**
internal links and `fetch()` paths must be prefixed:
`import.meta.env.BASE_URL` (or `.replace(/\/$/, "")` when concatenating). A bare
`/data/x.json` or `/hero` works in dev but 404s on the deployed site.

### Design system

Real FAMSF fonts + palette, so demos read as the actual brand: tokens in
`src/styles/global.css` (`@theme`), not literals in markup or scripts.

- **Two-museum palette:** `--color-deyoung` / `--color-cerulean` (de Young teal),
  `--color-legion` / `--color-amethyst` (Legion of Honor purple), plus
  `--color-yellow`. Reach for these when a surface distinguishes the two museums.
- **Fonts:** `--font-grotesk` (Akzidenz-Grotesk Next Pro, Adobe Typekit kit
  `tpb7nan`, `<link>` in `Layout.astro`) · `--font-serif` (Signifier, self-hosted
  woff2 in `public/fonts/signifier/`) · `--font-mono` (IBM Plex Mono, the console
  voice, not a FAMSF face).
- The map's SVG-drawing JS reads `var(--map-*)` tokens (all derived from
  `--color-ink` via `color-mix`) so no colour literals live in the script; change
  ink once, the whole map follows. Keep that discipline for data-viz scripts.
- Honour `prefers-reduced-motion` for any animation (the caret + typing already do).

### Data pipeline (offline, not part of the build)

`public/data/` files are generated ahead of time, then committed. `scripts/`
holds the generators (e.g. `geocode_places.py`, an offline gazetteer match of
place-of-creation names to coords, run via `uv run --with geonamescache python
scripts/geocode_places.py`). Source object data comes from the workspace ES
extract / live API upstream, not from this repo. `scripts/places_raw.json` is a
gitignored intermediate. Real thumbnails are `https://iiif.famsf.org/iiif/3/…/thumb-400.webp`,
but most objects in the extract have none yet, so baked datasets carry mostly
`thumb: null` (timeline has only a handful of real ones). Guard for null and
show a placeholder.
