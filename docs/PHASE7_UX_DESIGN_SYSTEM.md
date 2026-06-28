# Phase 7 — UX Design System

**Design philosophy:** calm, clinical, fast. Inspired by Apple HIG (clarity, deference, depth) and Material 3 (tonal color, elevation, motion) but implemented entirely within Odoo 19's OWL/QWeb/SCSS frontend stack — no generic unstyled list/form views for the core clinical screens. Generic Odoo views remain acceptable only for low-frequency admin/config screens (e.g., department config) where building a custom UI would be wasted effort.

---

## 1. Design Principles

1. **Calm over busy.** Clinical environments are stressful; the UI should reduce visual noise, not add to it. Generous whitespace, muted base palette, color reserved for status/action signaling.
2. **Speed is a feature.** Every core screen optimizes for the fewest clicks/keystrokes to complete the dominant task (register a patient, record vitals, write a prescription).
3. **One screen, full context.** Avoid forcing tab-hopping for information needed in the moment (e.g., doctor sees history + vitals + notes on one consultation screen, per PRD FR-15).
4. **Keyboard-first where it matters.** Reception and pharmacy are high-throughput, keyboard-and-mouse roles — full keyboard navigation and shortcuts. Nurse/doctor are tablet-first — large touch targets, minimal typing.
5. **Status is always legible.** Every workflow state is shown as a status chip with icon + text + color (never color alone — accessibility requirement AC-2).
6. **Consistent with Odoo, not fighting it.** We extend Odoo's design tokens (its existing color system, font stack `Inter`/system font) rather than importing a foreign design language wholesale — this keeps the product feeling native, upgrade-safe, and avoids reinventing component primitives Odoo already ships (dialogs, dropdowns, notifications).

---

## 2. Color Palette

Built as an extension of Odoo 19's existing SCSS variable system (`o-color-1` … `o-color-5`, `$o-brand-*`), so it themes correctly with Odoo's own light/dark mode infrastructure rather than fighting it.

| Token | Hex | Usage |
|---|---|---|
| `--hms-primary` | `#1668DC` (clinical blue) | Primary actions, links, active nav |
| `--hms-primary-dark` | `#0F4FA8` | Hover/active states |
| `--hms-surface` | `#FFFFFF` | Card/panel backgrounds (light mode) |
| `--hms-surface-dark` | `#15191E` | Card/panel backgrounds (dark mode) |
| `--hms-bg` | `#F4F6F8` | App background (light) |
| `--hms-bg-dark` | `#0B0D10` | App background (dark) |
| `--hms-text-primary` | `#1A1D21` / `#EDEFF2` (dark) | Body text |
| `--hms-text-secondary` | `#5C6470` / `#9AA3AE` (dark) | Secondary/meta text |
| `--hms-success` | `#1FA463` | Normal vitals, completed, dispensed |
| `--hms-warning` | `#E0A327` | Pending, backordered, waiting |
| `--hms-danger` | `#D6463D` | Urgent/emergency, abnormal results, conflicts |
| `--hms-info` | `#3D8BFF` | Informational chips (e.g., "scheduled") |
| `--hms-emergency` | `#B0142B` (high-saturation, used sparingly) | Emergency priority only — must stay rare to retain urgency signal |

**Rule:** no more than one "loud" color (danger/emergency) visible per screen region at once, to avoid alarm fatigue — exactly the kind of restraint a clinical UI needs that a generic dashboard doesn't.

---

## 3. Typography

- **Font:** `Inter` (already Odoo 19's default UI font) — no custom font load, keeps performance high and stays visually native.
- **Scale:** 12 / 14 / 16 / 20 / 24 / 32px, in line with Material 3's type scale ratios, mapped onto Odoo's existing `$o-font-size-*` SCSS variables rather than introducing parallel ones.
- **Weight usage:** 400 body, 500 labels/chips, 600 headings/KPI numbers. Never lighter than 400 for clinical data — legibility under tablet glare matters.
- **Numerals:** tabular figures for vitals/lab values so columns of numbers align (important for scanning lab result grids).

---

## 4. Spacing & Grid System

- **Base unit:** 4px. Spacing scale: 4/8/12/16/24/32/48px.
- **Grid:** 12-column responsive grid for dashboards; forms use a 2-column max layout on desktop, single-column on tablet/mobile.
- **Card padding:** 16px standard, 24px for primary content cards (e.g., consultation workspace panels).
- **Touch targets:** minimum 44×44px on any view flagged "tablet mode" (nurse/doctor), per AC-4.

---

## 5. Core Components

| Component | Spec |
|---|---|
| **Cards** | 8px corner radius, 1px border `--hms-border` (light) or subtle elevation shadow, used as the primary content container instead of bare Odoo list rows for dashboards. |
| **Buttons** | Primary (filled, `--hms-primary`), Secondary (outline), Ghost (text-only for low-emphasis actions). Height 40px desktop / 48px tablet. Icon+label, never icon-only for primary actions (clarity over cleverness). |
| **Tables** | Sticky header, zebra-free (rely on row hover + spacing, not stripes, for a calmer look), right-aligned numeric columns, inline status chips. |
| **Forms** | Floating/inline labels above fields (not placeholder-as-label, which disappears and harms accessibility), inline validation messages directly under the field (AC-5). |
| **Dialogs** | Centered modal for short confirmations (cancel visit, override warnings); side-panel drawer for longer contextual tasks (e.g., quick patient history lookup while staying on the queue screen). |
| **Notifications** | Odoo's native toast/snackbar system extended with our color tokens — not reinvented. |
| **Status Chips** | Pill shape, icon + label + color token, e.g., 🟡 "Waiting" / 🟢 "Completed" / 🔴 "Urgent" / 🔵 "Scheduled". |
| **Patient Timeline** | Vertical timeline component (visit → vitals → consultation → prescription/lab/radiology → outcome), each entry expandable inline, used on the Patient Profile screen (Phase 8). |
| **Vitals Cards** | Compact 4-up grid (BP / Pulse / Temp / SpO2) with mini sparkline trend if multiple readings exist, color-flagged if out of normal range. |
| **Doctor Workspace Layout** | 3-pane: left = queue list, center = active consultation, right = collapsible patient history panel — all visible without navigation on desktop; stacks to tabs on tablet. |
| **Pharmacy Workspace** | Queue list + dispense detail split view, with a persistent stock-level badge on each medicine line. |
| **Lab Workspace** | Queue grouped by priority/test type, result entry as a structured grid mirroring the printed report layout (reduces transcription error). |

---

## 6. Dark Mode

- Built on Odoo 19's native dark mode toggle/infrastructure — our SCSS tokens define both light and dark values (Section 2) and respond to the same user-level theme preference, not a separate custom toggle.
- Status colors (success/warning/danger) are saturation-adjusted, not just inverted, to maintain WCAG AA contrast on dark surfaces.

## 7. Tablet Mode

- Nurse and Doctor dashboards detect viewport/touch capability and switch to "tablet mode": larger touch targets, simplified single-column flow, bottom action bar for primary actions (thumb-reachable), per Phase 1's explicit tablet requirement.

## 8. Responsive Design

- Breakpoints: `<768px` (tablet portrait/nurse), `768–1280px` (tablet landscape/doctor), `>1280px` (desktop/reception, admin, pharmacy).
- Dashboards reflow from multi-column KPI grids (desktop) to stacked cards (tablet/mobile) — no horizontal scrolling on any core screen.

## 9. Keyboard Shortcuts (high-throughput roles)

| Context | Shortcut | Action |
|---|---|---|
| Reception | `N` | New registration |
| Reception | `/` | Focus patient search |
| Reception queue | `↑`/`↓` + `Enter` | Navigate and call next patient |
| Doctor consultation | `Ctrl+P` | Open prescription builder |
| Doctor consultation | `Ctrl+L` | Add lab order |
| Doctor consultation | `Ctrl+Enter` | Save & close consultation |
| Pharmacy queue | `D` | Dispense focused line |
| Global | `Ctrl+K` | Command palette / global patient search (Odoo 19 already ships a command palette pattern we extend) |

---

## Status

Design system defined. Proceeding to Phase 8 — Screen-by-Screen UX.
