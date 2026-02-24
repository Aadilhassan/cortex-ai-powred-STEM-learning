# UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate Study Pal from inline CSS to Tailwind CSS with a modern minimal redesign (zinc palette, indigo accents, backdrop-blur nav, rounded cards).

**Architecture:** Full Tailwind migration — every component gets rewritten from inline `styles` objects to Tailwind utility classes. Design tokens defined in `tailwind.config.mjs` with `sp-` prefix. No new dependencies beyond Tailwind and its Astro integration. All existing functionality preserved.

**Tech Stack:** Tailwind CSS 4, @astrojs/tailwind, @tailwindcss/typography

**Design doc:** `docs/plans/2026-02-24-ui-overhaul-design.md`

---

## Task 1: Install Tailwind CSS and Configure Design System

**Files:**
- Run: `npx astro add tailwind` in `/home/aadil/Me/study-pal/frontend`
- Create: `/home/aadil/Me/study-pal/frontend/src/styles/global.css`
- Modify: `/home/aadil/Me/study-pal/frontend/tailwind.config.mjs` (auto-created by astro add)
- Modify: `/home/aadil/Me/study-pal/frontend/astro.config.mjs`

**Step 1: Install Tailwind**

```bash
cd /home/aadil/Me/study-pal/frontend
npx astro add tailwind -y
```

If `astro add` doesn't work cleanly, fall back to manual:
```bash
npm install tailwindcss @astrojs/tailwind @tailwindcss/typography
```

**Step 2: Create global CSS with Tailwind directives**

Create `/home/aadil/Me/study-pal/frontend/src/styles/global.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-sp-base text-sp-body font-sans min-h-screen antialiased;
  }

  a {
    @apply text-indigo-400 no-underline hover:underline;
  }

  button {
    @apply cursor-pointer font-sans;
  }
}

/* Markdown content styles for chat */
@layer components {
  .markdown-content h1,
  .markdown-content h2,
  .markdown-content h3 {
    @apply mt-2 mb-1 text-zinc-50 font-semibold;
  }

  .markdown-content p {
    @apply my-1 leading-relaxed;
  }

  .markdown-content ul,
  .markdown-content ol {
    @apply my-1 pl-6;
  }

  .markdown-content li {
    @apply my-0.5;
  }

  .markdown-content code {
    @apply bg-zinc-800 text-indigo-300 px-1.5 py-0.5 rounded text-sm font-mono;
  }

  .markdown-content pre {
    @apply bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-x-auto my-2;
  }

  .markdown-content pre code {
    @apply bg-transparent p-0 text-zinc-300;
  }

  .markdown-content blockquote {
    @apply border-l-2 border-indigo-500 pl-4 my-2 text-zinc-500;
  }

  .markdown-content a {
    @apply text-indigo-400;
  }

  .markdown-content table {
    @apply border-collapse my-2 w-full;
  }

  .markdown-content th,
  .markdown-content td {
    @apply border border-zinc-800 px-3 py-2 text-left;
  }

  .markdown-content th {
    @apply bg-zinc-900;
  }
}

/* Animations */
@layer utilities {
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  @keyframes bounce-dot {
    0%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-6px); }
  }

  @keyframes pulse-ring {
    0% { transform: scale(1); opacity: 0.5; }
    100% { transform: scale(1.8); opacity: 0; }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .animate-blink {
    animation: blink 0.8s infinite;
  }

  .animate-bounce-dot {
    animation: bounce-dot 1.2s infinite ease-in-out;
  }

  .animate-pulse-ring {
    animation: pulse-ring 1.5s infinite;
  }
}
```

**Step 3: Configure Tailwind with design tokens**

Create or update `/home/aadil/Me/study-pal/frontend/tailwind.config.mjs`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sp: {
          base: '#09090b',
          surface: '#18181b',
          elevated: '#27272a',
          border: '#3f3f46',
          'border-subtle': '#27272a',
          text: '#fafafa',
          body: '#d4d4d8',
          muted: '#71717a',
          accent: '#818cf8',
          'accent-hover': '#a5b4fc',
          'accent-glow': 'rgba(129, 140, 248, 0.2)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
```

**Step 4: Update astro.config.mjs**

Add tailwind integration if not auto-added. Ensure the config includes:
```javascript
import tailwind from '@astrojs/tailwind';
// ...
integrations: [react(), tailwind()],
```

**Step 5: Verify Tailwind works**

```bash
cd /home/aadil/Me/study-pal/frontend
npm run dev
```

Open http://localhost:4321 — the page should still render (existing inline styles still work). Tailwind classes should now be available.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: install Tailwind CSS with design system tokens"
```

---

## Task 2: Migrate Layout.astro and Global Nav

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/layouts/Layout.astro`

**Step 1: Rewrite Layout.astro**

Replace the entire file with:

```astro
---
const { title = "Study Pal" } = Astro.props;
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body>
  <nav class="sticky top-0 z-50 h-14 bg-sp-base/80 backdrop-blur-xl border-b border-zinc-800/50 flex items-center gap-6 px-6">
    <a href="/" class="text-lg font-bold text-zinc-50 no-underline hover:no-underline">Study Pal</a>
  </nav>
  <main class="px-6 py-8 max-w-5xl mx-auto">
    <slot />
  </main>
</body>
</html>
```

Remove the old `<style is:global>` block — global styles now live in `global.css`.

Import global.css at the top of Layout.astro's frontmatter:
```astro
---
import '../styles/global.css';
const { title = "Study Pal" } = Astro.props;
---
```

**Step 2: Verify nav renders with blur effect**

Open the app, scroll a page with content — nav should be semi-transparent with backdrop blur.

**Step 3: Commit**

```bash
git add src/layouts/Layout.astro
git commit -m "feat: migrate Layout.astro to Tailwind with backdrop-blur nav"
```

---

## Task 3: Migrate Dashboard.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/Dashboard.tsx` (229 lines)

**Step 1: Rewrite Dashboard.tsx**

Remove the `const C = { ... }` color object, the `styles: Record<string, React.CSSProperties>` object, and all `onMouseEnter`/`onMouseLeave` handlers. Replace all inline `style={styles.xxx}` with Tailwind `className="..."`.

**Key class mappings:**
- Container: `className="space-y-6"`
- Header row: `className="flex items-center justify-between"`
- Title: `className="text-2xl font-semibold tracking-tight text-zinc-50"`
- Subtitle: `className="text-sm text-zinc-500 mt-1"`
- New Course button: `className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"`
- Course grid: `className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"`
- Course card: `className="group bg-zinc-900 rounded-xl p-5 hover:bg-zinc-800/80 hover:ring-1 hover:ring-indigo-500/30 transition-all duration-200 cursor-pointer relative"`
- Card title: `className="text-lg font-medium text-zinc-50"`
- Card description: `className="text-sm text-zinc-400 mt-1 line-clamp-2"`
- Card footer: `className="flex items-center gap-3 mt-4 text-xs text-zinc-500"`
- Section count badge: `className="bg-zinc-800 text-zinc-400 rounded-full px-2 py-0.5"`
- Delete button: `className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1 rounded-md text-zinc-600 hover:text-red-400 hover:bg-red-400/10 transition-all"`
- Empty state: `className="flex flex-col items-center justify-center py-20 text-center"`
- Empty state text: `className="text-zinc-500 mt-4 mb-6"`
- Loading: `className="text-zinc-500 text-center py-20"`

**Step 2: Verify in browser**

- Dashboard renders with rounded cards
- Hover shows indigo ring glow
- Delete button appears on hover
- Grid is responsive (1 col mobile, 2 tablet, 3 desktop)
- Empty state shows when no courses

**Step 3: Commit**

```bash
git add src/components/Dashboard.tsx
git commit -m "feat: migrate Dashboard to Tailwind with card hover glow"
```

---

## Task 4: Migrate NewCourse.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/NewCourse.tsx` (400 lines)

**Step 1: Rewrite NewCourse.tsx**

Remove `const C = { ... }` and `styles` object. Replace with Tailwind.

**Key class mappings:**
- Container: `className="max-w-2xl mx-auto space-y-6"`
- Title: `className="text-2xl font-semibold tracking-tight text-zinc-50"`
- Tab toggle: `className="inline-flex bg-zinc-950 rounded-lg p-1"`
- Active tab: `className="px-4 py-2 rounded-md text-sm font-medium bg-zinc-800 text-zinc-50 shadow-sm transition-all"`
- Inactive tab: `className="px-4 py-2 rounded-md text-sm font-medium text-zinc-500 hover:text-zinc-300 transition-colors"`
- Upload zone (default): `className="border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center hover:border-zinc-500 transition-colors cursor-pointer"`
- Upload zone (dragging): add `border-indigo-500 bg-indigo-500/5`
- Upload zone (file selected): add `border-green-500/50 bg-green-500/5`
- Textarea: `className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-zinc-200 text-sm leading-relaxed resize-y focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors"`
- Word count: `className="text-right text-xs text-zinc-600 mt-1"`
- Submit button: `className="w-full bg-indigo-500 hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-lg py-3 text-sm font-medium transition-colors"`
- Processing overlay: Use `className` equivalents for the spinner and step indicators
- Error box: `className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400 text-sm"`
- Info box: `className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-400"`

**Step 2: Verify**

- Tab toggle switches between Upload/Paste
- Drag-and-drop zone changes appearance on drag
- File selection shows file info
- Processing overlay shows step progress
- Error state displays correctly

**Step 3: Commit**

```bash
git add src/components/NewCourse.tsx
git commit -m "feat: migrate NewCourse to Tailwind with segmented tabs"
```

---

## Task 5: Migrate CourseView.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/CourseView.tsx` (484 lines)

**Step 1: Rewrite CourseView.tsx**

**Key class mappings:**
- Course header: `className="flex items-start justify-between gap-4 flex-wrap mb-8"`
- Title: `className="text-2xl font-semibold tracking-tight text-zinc-50"`
- Description: `className="text-sm text-zinc-400 mt-1 max-w-2xl"`
- Quiz button (ghost): `className="border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-zinc-300 rounded-lg px-4 py-2 text-sm font-medium transition-all"`
- Sections container: `className="space-y-4"`
- Section group: `className="bg-zinc-900 rounded-xl overflow-hidden"`
- Section header: `className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-800/50 transition-colors"`
- Section title: `className="text-base font-medium text-zinc-100"`
- Chevron: `className="text-zinc-500 transition-transform duration-200"` + `rotate-180` when expanded
- Subtopic count: `className="text-xs text-zinc-500"`
- Subtopic row: `className="group px-5 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors border-t border-zinc-800/50"`
- Progress dot: `className="w-2 h-2 rounded-full"` + `bg-zinc-600` / `bg-amber-400` / `bg-green-400`
- Progress text: `className="text-xs"` + `text-zinc-600` / `text-amber-400` / `text-green-400`
- Study link: `className="text-sm text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"`
- Concept tags: `className="bg-zinc-800 text-zinc-300 rounded-full px-3 py-1 text-xs"`
- Delete course button: `className="mt-8 border border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 rounded-lg px-4 py-2 text-sm transition-all"`

**Step 2: Verify**

- Sections expand/collapse with chevron rotation
- Subtopic rows show hover effects and Study link
- Progress badges display correct colors
- Quiz buttons work at section and course level

**Step 3: Commit**

```bash
git add src/components/CourseView.tsx
git commit -m "feat: migrate CourseView to Tailwind with accordion sections"
```

---

## Task 6: Migrate StudyView.tsx (Main Layout Shell)

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/StudyView.tsx` (478 lines)
- Modify: `/home/aadil/Me/study-pal/frontend/src/pages/study/[subtopicId].astro`

**Step 1: Update study page to use full-width layout**

In `[subtopicId].astro`, the StudyView needs full viewport. Either:
- Pass a `fullWidth` prop to Layout and conditionally remove `max-w-5xl` and padding
- Or have StudyView use negative margins to break out of the container

Best approach: Add a `fullWidth` prop to Layout.astro:
```astro
---
import '../styles/global.css';
const { title = "Study Pal", fullWidth = false } = Astro.props;
---
<!-- ... nav stays same ... -->
<main class={fullWidth ? "" : "px-6 py-8 max-w-5xl mx-auto"}>
  <slot />
</main>
```

Then in `[subtopicId].astro`:
```astro
<Layout title="Study - Study Pal" fullWidth={true}>
```

**Step 2: Rewrite StudyView.tsx**

**Key class mappings:**
- Root: `className="flex flex-col h-[calc(100vh-56px)]"` (56px = nav height h-14)
- Chat header: `className="flex items-center justify-between px-4 py-3 bg-zinc-900/80 backdrop-blur-sm border-b border-zinc-800/50 shrink-0"`
- Header left: `className="flex items-center gap-3"`
- Back link: `className="flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300 no-underline hover:no-underline transition-colors"`
- Subtopic label: `className="text-sm text-zinc-500"`
- Connection dot: `className="w-2 h-2 rounded-full shrink-0"` + `bg-green-400 animate-pulse` / `bg-red-400`
- Icon buttons (Clear, Diagram, Toggle): `className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"` with `title` for tooltip
- Main content: `className="flex flex-1 overflow-hidden"`
- Chat area: `className="flex-1 flex flex-col overflow-hidden transition-all duration-300"` — use flex-1 instead of fixed widths, let diagram panel take its space
- Diagram area (open): `className="w-[40%] shrink-0 transition-all duration-300"`
- Diagram area (closed): `className="w-0 shrink-0 overflow-hidden transition-all duration-300"`
- Input bar: `className="flex items-center gap-3 px-4 py-3 bg-zinc-900 border-t border-zinc-800/50 shrink-0"`
- Textarea: `className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-200 text-sm resize-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors"` with `min-h-[42px] max-h-[120px]`
- Send button: `className="bg-indigo-500 hover:bg-indigo-400 disabled:opacity-30 text-white rounded-full w-10 h-10 flex items-center justify-center shrink-0 transition-all"`

**Step 3: Verify**

- Full viewport height layout works
- Diagram panel toggles with smooth width transition
- Chat header has blur effect
- Icon buttons show tooltips
- Input bar has proper focus ring

**Step 4: Commit**

```bash
git add src/components/StudyView.tsx src/pages/study/\\[subtopicId\\].astro src/layouts/Layout.astro
git commit -m "feat: migrate StudyView to Tailwind with full-width layout"
```

---

## Task 7: Migrate ChatPanel.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/ChatPanel.tsx` (187 lines)

**Step 1: Rewrite ChatPanel.tsx**

Remove the `styles` object and the `<style>` tag (markdown styles are now in `global.css`).

**Key class mappings:**
- Container: `className="flex flex-col h-full overflow-hidden"`
- Message list: `className="flex-1 overflow-y-auto px-4 py-4 space-y-3"`
- User bubble: `className="self-end max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed"`
- Assistant bubble: `className="self-start max-w-[75%] bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed"`
- Streaming cursor: `className="text-indigo-400 font-bold ml-0.5 animate-blink"`
- Thinking dots container: `className="flex gap-1.5 py-1 items-center"`
- Each dot: `className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce-dot"` with inline `style={{ animationDelay: '0s' / '0.15s' / '0.3s' }}`
- Markdown container: Still uses `className="markdown-content"` (styles in global.css)

**Step 2: Verify**

- Messages align correctly (user right, assistant left)
- Bubble shapes have proper border radius
- Streaming text shows blinking cursor
- Thinking dots animate with stagger
- Markdown renders correctly in assistant messages

**Step 3: Commit**

```bash
git add src/components/ChatPanel.tsx
git commit -m "feat: migrate ChatPanel to Tailwind with rounded bubbles"
```

---

## Task 8: Migrate DiagramPanel.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/DiagramPanel.tsx` (266 lines)

**Step 1: Rewrite DiagramPanel.tsx**

**Key class mappings:**
- Panel: `className="flex flex-col h-full border-l border-zinc-800 bg-sp-base"`
- Header: `className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/50 bg-zinc-900 shrink-0"`
- Header title: `className="text-sm font-semibold text-zinc-200"`
- Toggle button: `className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors"`
- Content: `className="flex-1 overflow-y-auto p-4 space-y-4"`
- Diagram card: `className="bg-zinc-950 rounded-lg border border-zinc-800 p-4 overflow-auto text-center"`
- Section label: `className="text-xs font-semibold uppercase tracking-wider text-zinc-500"`
- Empty state: `className="flex flex-col items-center justify-center h-full text-center px-8"`
- Empty text: `className="text-zinc-500 mt-3 text-sm"`
- Error pre: `className="text-red-400 p-4 text-xs whitespace-pre-wrap"`
- Collapsed toggle: `className="absolute right-0 top-1/2 -translate-y-1/2 bg-zinc-900 border border-zinc-800 border-r-0 text-zinc-500 hover:text-indigo-400 px-1.5 py-3 rounded-l-lg flex flex-col items-center gap-1 cursor-pointer transition-colors z-10"`

Update mermaid theme config to match new palette:
```typescript
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    darkMode: true,
    background: '#18181b',
    primaryColor: '#818cf8',
    primaryTextColor: '#d4d4d8',
    primaryBorderColor: '#3f3f46',
    lineColor: '#71717a',
    secondaryColor: '#27272a',
    tertiaryColor: '#09090b',
  },
});
```

**Step 2: Verify**

- Diagrams render in dark-themed cards
- Panel opens/closes smoothly
- Collapsed state shows pill with count
- Mermaid diagrams use new color scheme

**Step 3: Commit**

```bash
git add src/components/DiagramPanel.tsx
git commit -m "feat: migrate DiagramPanel to Tailwind with mermaid dark theme"
```

---

## Task 9: Migrate VoiceInput.tsx and AudioController.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/VoiceInput.tsx` (283 lines)
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/AudioController.tsx` (54 lines)

**Step 1: Rewrite VoiceInput.tsx**

**Key class mappings:**
- Container: `className="relative"`
- Button (idle): `className="w-10 h-10 rounded-full border-2 border-zinc-700 text-zinc-500 flex items-center justify-center hover:border-zinc-500 hover:text-zinc-300 transition-all"`
- Button (listening): `className="w-10 h-10 rounded-full border-2 border-red-500 text-red-400 bg-red-500/10 flex items-center justify-center"`
- Button (speaking): `className="w-10 h-10 rounded-full border-2 border-green-500 text-green-400 bg-green-500/10 flex items-center justify-center"`
- Pulse ring (listening): `className="absolute inset-0 rounded-full border-2 border-red-500 animate-pulse-ring pointer-events-none"`
- Tooltip: `className="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs px-2 py-1 rounded bg-zinc-800 text-zinc-400"`

**Step 2: Rewrite AudioController.tsx**

**Key class mappings:**
- Disabled state: `className="w-10 h-10 rounded-full border-2 border-zinc-700 text-zinc-500 flex items-center justify-center hover:border-zinc-500 hover:text-zinc-300 transition-all"`
- Enabled state: `className="w-10 h-10 rounded-full border-2 border-indigo-500 text-indigo-400 bg-indigo-500/10 flex items-center justify-center transition-all"`

**Step 3: Verify**

- Mic button toggles between states
- Red pulse ring appears when recording
- Audio toggle shows enabled/disabled state
- Hover effects work

**Step 4: Commit**

```bash
git add src/components/VoiceInput.tsx src/components/AudioController.tsx
git commit -m "feat: migrate VoiceInput and AudioController to Tailwind"
```

---

## Task 10: Migrate QuizView.tsx

**Files:**
- Modify: `/home/aadil/Me/study-pal/frontend/src/components/QuizView.tsx` (455 lines)

**Step 1: Rewrite QuizView.tsx**

**Key class mappings — Quiz mode:**
- Container: `className="max-w-3xl mx-auto space-y-6"`
- Title: `className="text-2xl font-semibold tracking-tight text-zinc-50"`
- Question card: `className="bg-zinc-900 rounded-xl p-6 space-y-4"`
- Question number: `className="text-xs text-zinc-500 uppercase tracking-wide font-medium"`
- Question text: `className="text-lg font-medium text-zinc-100"`
- MCQ option (default): `className="border border-zinc-800 rounded-lg px-4 py-3 cursor-pointer hover:border-zinc-600 transition-colors flex items-center gap-3"`
- MCQ option (selected): `className="border-indigo-500 bg-indigo-500/10 rounded-lg px-4 py-3 cursor-pointer flex items-center gap-3"`
- Radio circle (unselected): `className="w-5 h-5 rounded-full border-2 border-zinc-600 shrink-0"`
- Radio circle (selected): `className="w-5 h-5 rounded-full border-2 border-indigo-500 bg-indigo-500 shrink-0"` with inner dot
- Short answer input: `className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-zinc-200 text-sm focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors"`
- Submit button: `className="block mx-auto mt-8 bg-indigo-500 hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white rounded-lg px-8 py-3 text-sm font-medium transition-colors"`

**Key class mappings — Results mode:**
- Score container: `className="bg-zinc-900 rounded-xl p-8 text-center mb-8"`
- Score number: `className="text-4xl font-bold"` + dynamic color (`text-green-400` / `text-amber-400` / `text-red-400`)
- Score subtitle: `className="text-zinc-500 mt-2"`
- Feedback card (correct): `className="bg-green-500/5 border-l-2 border-green-500 rounded-lg p-5 mb-3"`
- Feedback card (wrong): `className="bg-red-500/5 border-l-2 border-red-500 rounded-lg p-5 mb-3"`
- Correct indicator: `className="flex items-center gap-2 text-green-400 text-sm font-medium mb-2"`
- Wrong indicator: `className="flex items-center gap-2 text-red-400 text-sm font-medium mb-2"`
- Your answer label: `className="text-xs text-zinc-500 uppercase tracking-wide"`
- Explanation box: `className="bg-zinc-900 rounded-lg p-3 mt-3 text-sm text-zinc-400"`
- Back button: `className="inline-flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-6 py-2.5 font-medium no-underline hover:no-underline transition-colors"`

Update mermaid config in MermaidDiagram sub-component to match DiagramPanel theme.

**Step 2: Verify**

- Questions render with proper card layout
- MCQ selection shows indigo highlight
- Submit is disabled until all answered
- Results show color-coded score and feedback
- Diagram questions render mermaid correctly
- Back to Course link works

**Step 3: Commit**

```bash
git add src/components/QuizView.tsx
git commit -m "feat: migrate QuizView to Tailwind with color-coded results"
```

---

## Task 11: Final Cleanup and Visual QA

**Files:**
- All component files (verify no remaining inline styles)
- `/home/aadil/Me/study-pal/frontend/src/styles/global.css` (verify all needed styles present)

**Step 1: Search for remaining inline styles**

```bash
cd /home/aadil/Me/study-pal/frontend/src
grep -rn "style={{" components/ --include="*.tsx" | head -30
grep -rn "style={styles" components/ --include="*.tsx" | head -30
grep -rn "const styles" components/ --include="*.tsx" | head -30
```

Any remaining `styles` objects should be removed. A few inline styles may remain for truly dynamic values (e.g., `animationDelay` on staggered dots) — that's acceptable.

**Step 2: Check responsive breakpoints**

Open each page at mobile width (375px) and verify nothing overflows:
- Dashboard: Single column grid
- NewCourse: Full width form
- CourseView: Stacked layout
- StudyView: Diagram panel hidden on mobile (optional improvement)
- QuizView: Full width cards

**Step 3: Verify all existing functionality still works**

- Create a course (upload/paste)
- Navigate course structure
- Start a study session (text + voice)
- Diagrams generate and display
- Take a quiz, see results

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup remaining inline styles, visual QA pass"
```
