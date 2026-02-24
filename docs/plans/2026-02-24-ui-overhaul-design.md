# Study Pal UI Overhaul — Design Document

**Date:** 2026-02-24
**Direction:** Modern minimal (Linear/Vercel/Raycast aesthetic)
**Approach:** Full Tailwind CSS migration, every component redesigned

---

## 1. Design System

### Colors (Tailwind `sp-` namespace)

```
Backgrounds:
  sp-base:      #09090b   (zinc-950)
  sp-surface:   #18181b   (zinc-900)
  sp-elevated:  #27272a   (zinc-800)

Borders:
  sp-border:    #3f3f46   (zinc-700)
  sp-border-subtle: #27272a (zinc-800)

Text:
  sp-text:      #fafafa   (zinc-50 — headings)
  sp-body:      #d4d4d8   (zinc-300 — body)
  sp-muted:     #71717a   (zinc-500 — secondary)

Accent:
  sp-accent:    #818cf8   (indigo-400)
  sp-accent-hover: #a5b4fc (indigo-300)
  sp-accent-glow: #818cf833 (20% opacity)

Status:
  success: #4ade80  warning: #fbbf24  error: #f87171
```

### Typography

- Font: Inter (system-ui fallback)
- Headings: font-semibold tracking-tight
- Body: text-zinc-300 leading-relaxed
- Scale: Tailwind defaults (text-xs through text-3xl)

### Spacing & Borders

- Cards: rounded-xl, subtle shadow (`shadow-sm shadow-black/10`), no visible borders by default
- Hover: `ring-1 ring-indigo-500/30` glow ring
- Elevated elements: `shadow-lg shadow-black/20`
- Standard padding: p-5 for cards, px-6 py-8 for page containers

---

## 2. Global Nav

- `sticky top-0 z-50 bg-sp-base/80 backdrop-blur-xl border-b border-zinc-800/50 h-14`
- Left: Logo icon + "Study Pal" font-semibold text-zinc-50
- Right: Breadcrumb trail (Dashboard > Course > Subtopic)
- Content scrolls behind the transparent blurred nav

---

## 3. Dashboard (Course Grid)

### Header
- "Your Courses" text-2xl font-semibold tracking-tight
- Subtitle: "Continue learning or start something new" text-zinc-500
- "+ New Course" button: `bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-4 py-2`

### Course Cards
- `bg-zinc-900 rounded-xl p-5 hover:bg-zinc-800/80 transition-all duration-200`
- Hover: `ring-1 ring-indigo-500/30`
- Title: text-lg font-medium text-zinc-50
- Description: text-sm text-zinc-400 line-clamp-2
- Footer: Section count pill (`bg-zinc-800 rounded-full px-2 py-0.5 text-xs`) + date
- Delete: Hidden, appears on hover as `text-zinc-600 hover:text-red-400` icon

### Empty State
- Centered SVG illustration + "No courses yet" + CTA button

---

## 4. Course View (Sections & Subtopics)

### Course Header
- Title: text-2xl font-semibold
- Description: text-zinc-400 text-sm
- Quiz button: Ghost style `border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10`

### Section Accordion
- `bg-zinc-900 rounded-xl overflow-hidden` — no visible border
- Header: `px-5 py-4 hover:bg-zinc-800/50` clickable
- Chevron: Rotates 180deg when expanded
- Content: `transition-all duration-200` slide open

### Subtopic Rows
- `px-5 py-3 hover:bg-zinc-800/50 flex items-center justify-between`
- Progress: Colored dot + text (gray=not started, amber=in progress, green=done)
- "Study" link: text-indigo-400, appears on hover with arrow icon

### Section Metadata
- Learning objectives: Numbered list, text-zinc-400
- Key concepts: `bg-zinc-800 text-zinc-300 rounded-full px-3 py-1 text-xs` tags

---

## 5. Study Session (Chat + Diagrams)

### Layout
- Full viewport, three rows: Header | Content | Input
- Content: Two-column split (60/40), smooth width transitions

### Chat Header
- `bg-zinc-900/80 backdrop-blur-sm border-b border-zinc-800/50`
- Left: Back chevron + subtopic title + pulsing connection dot
- Right: Icon-only buttons (Clear, Diagram, Panel toggle) with tooltips
  - `p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300`

### Chat Messages
- User: `bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[75%]`
- Assistant: `bg-zinc-900 text-zinc-200 rounded-2xl rounded-bl-md px-4 py-2.5 border border-zinc-800`
- Streaming cursor: Thin blinking indigo line
- Thinking: Three dots with staggered bounce animation
- Gap: space-y-3

### Markdown in Chat
- Code blocks: `bg-zinc-950 border border-zinc-800 rounded-lg`
- Inline code: `bg-zinc-800 text-indigo-300 rounded px-1.5 py-0.5`
- Bold: text-zinc-50 (pops against zinc-300 body)

### Diagram Panel
- Header: "Diagrams" label + close icon
- Cards: `bg-zinc-950 rounded-lg border border-zinc-800 p-4`
- Empty: Dashed border with hint text
- Collapsed: Minimal pill on edge with diagram count

### Input Bar
- `bg-zinc-900 border-t border-zinc-800/50 px-4 py-3`
- Input: `bg-zinc-950 border border-zinc-800 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 rounded-xl`
- Voice button: `rounded-full w-10 h-10`, red ring pulse when recording
- Send button: `bg-indigo-500 rounded-full w-10 h-10`, fades in when text exists
- TTS: Small toggle switch

---

## 6. New Course Page

### Tab Toggle (Segmented Control)
- `bg-zinc-950 rounded-lg p-1 inline-flex`
- Active: `bg-zinc-800 text-zinc-50 rounded-md shadow-sm`
- Inactive: `text-zinc-500 hover:text-zinc-300`

### Upload Zone
- `border-2 border-dashed border-zinc-700 rounded-xl p-8 hover:border-zinc-500`
- Drag active: `border-indigo-500 bg-indigo-500/5`
- File selected: Green checkmark + file info + remove

### Processing Overlay
- Step list with animated checkmarks
- Progress bar
- Subtle spinner

---

## 7. Quiz View

### Question Cards
- `bg-zinc-900 rounded-xl p-6 space-y-4`
- Question number: `text-xs text-zinc-500 uppercase tracking-wide`
- Question text: text-lg font-medium text-zinc-100

### MCQ Options
- `border border-zinc-800 rounded-lg px-4 py-3 hover:border-zinc-600 cursor-pointer`
- Selected: `border-indigo-500 bg-indigo-500/10`

### Results
- Score: Large centered number with color-coded accent
- Feedback: Green/red left border per question
- Correct: `bg-green-500/10 border-l-2 border-green-500`
- Wrong: `bg-red-500/10 border-l-2 border-red-500`

---

## 8. Implementation Notes

- Add Tailwind CSS + @tailwindcss/typography plugin
- Define custom colors in tailwind.config with `sp-` prefix
- Migrate all inline `styles` objects to Tailwind classes
- Remove all `onMouseEnter`/`onMouseLeave` handlers (use Tailwind hover:)
- Add focus-visible styles for accessibility
- Add responsive breakpoints (mobile-first)
- Keep all existing functionality — visual-only changes
