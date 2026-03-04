# Web UI Setup (Beginner Guide + Component Map)

This document is for people who do not already know how shadcn, Tailwind tokens, and dark mode work. It explains the “mental model,” then maps the UI components to what they do and where they live.

## Goals

- Ensure shadcn/ui is configured correctly (tokens, aliases, animations).
- Make dark mode render consistently across surfaces and components.
- Reduce hardcoded light colors that break theme switching.

## High-level Summary

- Added shadcn config via `web/components.json`.
- Introduced CSS variables and shadcn token mapping in Tailwind.
- Added dark theme variables and a theme-aware page background.
- Normalized component styles to use semantic tokens (`bg-card`, `text-foreground`, etc).
- Installed `tailwindcss-animate` plugin used by shadcn components.

## Mental Model (How This UI Works)

Think of the UI as three layers:

1. CSS variables define “theme colors” (light + dark).
2. Tailwind maps semantic class names to those variables.
3. Components use those semantic classes, so they switch automatically with the theme.

If any component uses hardcoded colors (like `bg-white`), it will break dark mode.

### Layer 1: CSS Variables

The theme is a set of CSS variables in `web/app/globals.css`:

- Light mode is defined under `:root`.
- Dark mode is defined under `.dark`.

Example (simplified):

```css
:root {
  --background: 40 40% 94%;
  --foreground: 33 22% 10%;
}

.dark {
  --background: 30 16% 9%;
  --foreground: 40 40% 94%;
}
```

### Layer 2: Tailwind Token Mapping

`web/tailwind.config.ts` maps Tailwind class names to those variables:

- `bg-background` → `hsl(var(--background))`
- `text-foreground` → `hsl(var(--foreground))`
- `border-border` → `hsl(var(--border))`

This means the class name never changes, but the actual color does depending on light/dark.

### Layer 3: Component Classes

Components should use tokens like:

- `bg-card`
- `text-foreground`
- `text-muted-foreground`
- `border-border`

So when `.dark` is set on `<html>`, the entire app flips without changing component code.

## How Dark Mode Is Applied

The app is currently forced to dark mode by adding `className="dark"` on `<html>`:

- `web/app/layout.tsx`

If you want a toggle, remove the hardcoded class and add a theme provider (see “Future Improvements”).

## Files and Changes

### `web/components.json`

shadcn configuration file. This is required for the shadcn CLI to add components correctly.

- `style`: `default`
- `rsc`: `true` (Next.js App Router)
- `tsx`: `true`
- `tailwind.css`: `app/globals.css`
- `tailwind.config`: `tailwind.config.ts`
- `cssVariables`: `true`
- `aliases`: `@/components`, `@/components/ui`, `@/lib/utils`

If you run the shadcn CLI, it will read this file to install components into `web/components/ui`.

### `web/tailwind.config.ts`

Added token-based colors and radius mapping to support shadcn components and dark mode:

- Semantic tokens: `background`, `foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `border`, `input`, `ring`.
- `borderRadius` now maps to `--radius` for shadcn rounded styles.
- Included `tailwindcss-animate` plugin.
- Expanded `content` paths to include `lib`.

### `web/app/globals.css`

Introduced CSS variables and dark theme values:

- Light mode tokens under `:root`.
- Dark mode tokens under `.dark`.
- `--page-bg` variable for theme-specific background gradients.
- Base styles apply `border-border` and set `body` color/background using tokens.

Important: `body` now uses `var(--page-bg)` for the visible page background, while base layer sets `background` and `color` using tokens.

### Layout + Component Tokenization

Hardcoded light colors were replaced with semantic tokens so dark mode works consistently:

- `bg-canvas` → `bg-background`
- `bg-panel` → `bg-card`
- `text-ink` → `text-foreground`
- `text-muted` → `text-muted-foreground`
- `bg-white`/`bg-white/70` → `bg-card` or `bg-background` variants

Key files updated:

- `web/components/layout/shell.tsx`
- `web/components/layout/topbar.tsx`
- `web/components/layout/sidebar.tsx`
- `web/components/ui/button.tsx`
- `web/components/ui/badge.tsx`
- `web/components/ui/card.tsx`
- `web/components/newsmap/treemap-client.tsx`
- `web/components/alerts/alerts-dashboard.tsx`
- `web/components/alerts/alert-list.tsx`
- `web/components/topics/topic-selector.tsx`
- `web/components/topics/topic-browser.tsx`
- `web/app/topics/page.tsx`

### shadcn UI Component Alignment

The following components now use shadcn-standard class tokens so they inherit theme variables correctly:

- `Button`: uses `bg-primary`, `text-primary-foreground`, `ring-ring`, `ring-offset-background`.
- `Badge`: uses `bg-secondary` and adjusted alert colors for dark backgrounds.
- `Card`: uses `bg-card` and `text-card-foreground`.

## Component Map (What Does What)

This is the practical “who does what” list. Use it to find where to edit behavior or visuals.

### Layout and Navigation

- `web/app/layout.tsx`
  - Root layout for the entire app.
  - Applies fonts and the `.dark` class to `<html>`.
  - Wraps all pages in `Shell`.
- `web/components/layout/shell.tsx`
  - Main layout grid (sidebar + content).
  - Sets `bg-background` and `text-foreground` on the page container.
- `web/components/layout/sidebar.tsx`
  - Left nav. Holds navigation links and branding.
  - If links or spacing are wrong, edit here.
- `web/components/layout/topbar.tsx`
  - Top bar with title and badges.

### Pages (Route Entrypoints)

- `web/app/page.tsx`
  - Home dashboard grid (links to Newsmap / Alerts / Topics).
- `web/app/newsmap/page.tsx`
  - Newsmap page wrapper. Most UI is in the component below.
- `web/app/alerts/page.tsx`
  - Alerts page wrapper. Uses `AlertsDashboard`.
- `web/app/topics/page.tsx`
  - Topics page wrapper. Uses `TopicSelector` and `TopicBrowser`.

### Alerts Area

- `web/components/alerts/alerts-dashboard.tsx`
  - Orchestrates filtering, search, and the layout of alert lists.
  - State lives here (`query`, `filter`).
- `web/components/alerts/alert-list.tsx`
  - Renders a list of alert items.
  - Controls the per-item UI and badge display.

### Newsmap Area

- `web/components/newsmap/treemap-client.tsx`
  - Renders the ECharts treemap.
  - Handles click events and shows details panel.
  - If the chart looks wrong, this is where to start.

### Topics Area

- `web/components/topics/topic-selector.tsx`
  - Dropdown-based topic selection.
  - Renders the response for the selected topic.
- `web/components/topics/topic-browser.tsx`
  - Search + list-based topic selection.
  - Uses Button variants to highlight the selected topic.

### UI Primitives (Reusable)

- `web/components/ui/button.tsx`
  - shadcn-style button variants and sizes.
  - If all buttons look wrong, start here.
- `web/components/ui/badge.tsx`
  - Badge variants used in topbar and alerts.
- `web/components/ui/card.tsx`
  - Card container used on the home page.

### Utilities and Data

- `web/lib/utils.ts`
  - `cn()` helper for class name merging.
- `web/lib/dashboard.ts`
  - Types and data helpers used by alerts/topics UI.

## How to Change Behavior Safely

If you change UI behavior, follow this path:

1. Identify which page uses the component (see “Pages” section).
2. Find the component that owns state (usually in `components/alerts` or `components/topics`).
3. Change the state or data logic there.
4. Only update UI primitives (like `Button`) if you want a global visual change.

## How to Add New UI Without Breaking Dark Mode

Use tokens. Avoid hard-coded colors.

Good:

```
className="bg-card text-foreground border border-border"
```

Bad:

```
className="bg-white text-black"
```

## How to Add New UI

Prefer shadcn components and tokens. Guidelines:

- Use semantic tokens (`bg-card`, `text-foreground`, `border-border`).
- Avoid raw colors (`bg-white`, `text-black`) unless you want a deliberate override.
- For inputs, set `bg-background` and `text-foreground`.
- For hover styles, use `hover:bg-accent` and `hover:text-accent-foreground`.

If you use the shadcn CLI:

1. `cd web`
2. `pnpm dlx shadcn@latest add button` (example)
3. Components will be placed in `web/components/ui`.

## Known Constraints and Warnings

- `pnpm` warned about ignored build scripts. If you hit issues with native deps, run:
  - `pnpm approve-builds` in `web/`.
- Tests were not run (pytest not installed in this environment).

## Quick Checks

If the theme “doesn’t work”:

- Inspect for stray hardcoded light colors (`bg-white`, `text-black`).
- Ensure `.dark` is applied at `<html>` or via theme provider.
- Verify `tailwindcss-animate` is installed and `tailwind.config.ts` includes it.

## Future Improvements (Optional)

- Add a theme toggle using `next-themes`.
- Define component-specific variants for alerts to better reflect status.
- Add a shared `Input` component in `web/components/ui/input.tsx` to avoid repeating input class lists.
