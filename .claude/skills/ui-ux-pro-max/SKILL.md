---
name: ui-ux-pro-max
description: UI/UX design quality guidance — apply when a task changes how a feature looks, feels, moves, or is interacted with. Skip for pure backend/API/database/infra work.
---

# UI/UX Pro Max: Core Principles & Actionable Guidance

## When to Use This Skill

Apply this skill when tasks involve **UI structure, visual design, interaction patterns, or user experience quality**. Skip for pure backend logic, APIs, databases, infrastructure, or non-visual work.

**Decision criterion**: Use if the task changes how a feature "looks, feels, moves, or is interacted with."

---

## Priority-Based Rule Categories (1–10)

### 1. **Accessibility (CRITICAL)**
- **Color contrast**: Minimum 4.5:1 for normal text; 3:1 for large text
- **Focus states**: Visible focus rings (2–4px) on all interactive elements
- **Alt text & aria-labels**: Required for images and icon-only buttons
- **Keyboard navigation**: Full support with logical tab order matching visual layout
- **Dynamic text scaling**: Support system text size increases without truncation
- **Reduced motion**: Respect `prefers-reduced-motion` by reducing/disabling animations
- **Screen reader support**: Meaningful labels and logical reading order for VoiceOver/TalkBack

### 2. **Touch & Interaction (CRITICAL)**
- **Touch target minimum**: 44×44pt (iOS) / 48×48dp (Android)
- **Touch spacing**: Minimum 8px/8dp gap between targets
- **No hover-only reliance**: Tap/click for primary interactions
- **Loading feedback**: Show spinners or disable buttons during async operations
- **Press feedback**: Visual response (ripple/highlight) within 100ms of tap
- **Safe-area awareness**: Keep targets away from notch, Dynamic Island, and gesture zones
- **Swipe affordance**: Clear hints when swipe actions are available

### 3. **Performance (HIGH)**
- **Image optimization**: Use WebP/AVIF with responsive srcset; lazy load below-fold
- **Prevent layout shift**: Declare image dimensions or aspect-ratio; CLS <0.1
- **Font loading**: Use `font-display: swap` to avoid invisible text (FOIT)
- **Code splitting**: Split by route/feature (React Suspense / Next.js dynamic)
- **Virtualize long lists**: For 50+ items, implement list virtualization
- **Animation performance**: Use transform/opacity only; avoid animating width/height
- **Debounce/throttle**: High-frequency events (scroll, resize, input)
- **Progressive loading**: Skeleton screens for >1s operations instead of spinners

### 4. **Style Selection (HIGH)**
- **Match product type**: Choose style consistent with product category (SaaS, e-commerce, etc.)
- **SVG icons only**: No emojis for structural icons; use vector icon families
- **Consistency**: Apply same style across all pages
- **Platform idioms**: Respect iOS HIG and Material Design guidelines per platform
- **State clarity**: Hover/pressed/disabled states visually distinct and on-brand
- **Elevation consistency**: Unified shadow/elevation scale for all components
- **Dark mode parity**: Design light/dark variants together with equal contrast

### 5. **Layout & Responsive (HIGH)**
- **Viewport meta**: `width=device-width, initial-scale=1` (never disable zoom)
- **Mobile-first design**: Start small, scale up to tablet/desktop
- **Systematic breakpoints**: Use consistent breakpoints (375 / 768 / 1024 / 1440)
- **Minimum 16px body text**: On mobile to avoid iOS auto-zoom
- **No horizontal scroll**: Ensure content fits viewport width
- **8dp spacing system**: Use incremental spacing (Material Design standard)
- **Safe area padding**: Reserve space for status bar, notch, and gesture home indicator
- **Content priority**: Show core content first; hide/fold secondary content on mobile

### 6. **Typography & Color (MEDIUM)**
- **Line height**: 1.5–1.75 for body text; 1.2–1.4 for headings
- **Line length**: 65–75 characters for desktop; 35–60 for mobile
- **Font pairing**: Match heading/body personalities; maintain consistency
- **Semantic tokens**: Use named color tokens (primary, secondary, error, surface) not raw hex
- **Dark mode contrast**: Desaturated/lighter variants, not inverted colors
- **Accessible pairs**: Foreground/background must meet WCAG AA (4.5:1) or AAA (7:1)
- **Truncation strategy**: Prefer wrapping; use ellipsis + tooltip only when necessary
- **Tabular figures**: Monospaced numbers for prices, amounts, timers

### 7. **Animation (MEDIUM)**
- **Timing**: 150–300ms for micro-interactions; ≤400ms for complex transitions
- **Transform only**: Animate transform/opacity; avoid width/height/position
- **Meaningful motion**: Every animation must express cause-effect, not decoration
- **Easing**: Ease-out for entering, ease-in for exiting
- **Spring physics**: Prefer spring curves for natural feel (Apple HIG style)
- **Exit faster**: Exit animations ~60–70% of enter duration for responsiveness
- **Interruptible**: User tap must immediately cancel in-progress animations
- **Spatial continuity**: Maintain visual connection between screens (shared element transitions)

### 8. **Forms & Feedback (MEDIUM)**
- **Visible labels**: Always use label elements, not placeholder-only
- **Error placement**: Show errors below the related field
- **Inline validation**: Validate on blur, not keystroke
- **Helper text**: Persistent guidance for complex inputs
- **Progressive disclosure**: Reveal options gradually, don't overwhelm upfront
- **Success feedback**: Brief visual confirmation (checkmark, color flash, toast)
- **Error clarity**: State cause + recovery path ("Invalid email. Try example@test.com")
- **Undo support**: Allow undo for destructive actions
- **Focus management**: Auto-focus first invalid field after submit error
- **Multi-step progress**: Show step indicator; allow back navigation

### 9. **Navigation Patterns (HIGH)**
- **Bottom nav limit**: Maximum 5 items with labels + icons (Material Design)
- **Back consistency**: Predictable and preserves scroll/filter state
- **Deep linking**: All key screens reachable via URL for sharing/notifications
- **State highlighting**: Current location visually highlighted (color, weight, indicator)
- **Modal close affordance**: Clear dismiss option; swipe-down on mobile
- **Gesture support**: Support system gestures (iOS back swipe, Android predictive back)
- **Navigation hierarchy**: Separate primary (tabs/bottom bar) from secondary (drawer/settings)
- **Avoid nav changes**: Keep navigation placement consistent across all pages

### 10. **Charts & Data (LOW)**
- **Chart type matching**: Line for trends, bar for comparison, pie for proportions
- **Color accessibility**: Avoid red/green-only distinctions (colorblind-friendly)
- **Legend visibility**: Always show; position near chart, not below fold
- **Tooltips/labels**: Hover (Web) or tap (mobile) for exact values
- **Responsive simplification**: Reflow/simplify for small screens (horizontal bars, fewer ticks)
- **Accessible tables**: Provide table alternative for screen readers
- **Interactive legends**: Allow toggling series visibility
- **Empty state**: Meaningful message when no data exists, not blank chart

---

## Common Professional UI Standards (App-Focused)

### Icons & Visual Elements

| Rule | Do | Avoid |
|------|-----|---------|
| **Icon structure** | Use SVG or vector families (Lucide, react-native-vector-icons) | Emoji for navigation, settings, system controls |
| **Icon sizing** | Define as tokens (icon-sm, icon-md=24pt, icon-lg) | Random arbitrary sizes (20pt / 28pt mixed) |
| **Stroke consistency** | Uniform stroke width per layer (1.5px or 2px) | Mixing thick/thin strokes randomly |
| **Icon alignment** | Consistent baseline alignment and padding | Misaligned icons, inconsistent spacing |
| **Contrast** | 4.5:1 for small elements, 3:1 minimum for UI glyphs | Low-contrast icons blending into background |

### Interaction Essentials

| Rule | Standard | Avoid |
|------|----------|-------|
| **Tap feedback** | Clear pressed response (ripple/opacity/elevation) within 100ms | No visual feedback on tap |
| **Animation timing** | 150–300ms micro-interactions with platform easing | Instant transitions or >500ms delays |
| **Disabled clarity** | Semantic disabled state, reduced emphasis, no tap action | Controls that look tappable but are inactive |
| **Focus accessibility** | Screen reader focus matches visual order with descriptive labels | Unlabeled controls, confusing traversal |
| **Gesture conflicts** | One primary gesture per region, avoid nested tap/drag | Overlapping gestures causing accidental actions |

### Light/Dark Mode Parity

| Rule | Do | Don't |
|------|-----|---------|
| **Text contrast** | 4.5:1 primary, 3:1 secondary in both themes | Low-contrast text in either mode |
| **Borders/dividers** | Visible in both light and dark themes | Theme-dependent borders disappearing |
| **State distinction** | Equal visual clarity for pressed/focused/disabled in both modes | Interaction states defined for one theme only |
| **Modal scrim** | 40–60% black opacity to isolate foreground | Weak scrim competing with background |
| **Token-driven** | Use semantic color tokens per theme, not hardcoded hex | Per-screen hardcoded values |

### Layout & Spacing

| Rule | Do | Don't |
|------|-----|---------|
| **Safe areas** | Respect notch, status bar, gesture zones | UI colliding with OS chrome |
| **Spacing rhythm** | 4/8dp incremental system across components/sections/pages | Random spacing with no rhythm |
| **Text measure** | 65–75 chars/line on desktop, 35–60 on mobile | Edge-to-edge long text on tablets |
| **Adaptive gutters** | Increase horizontal insets on larger widths/landscape | Same narrow gutter everywhere |
| **Content layering** | Add insets so scroll content isn't hidden behind fixed bars | Lists obscured by sticky headers/footers |

---

## Pre-Delivery Quality Checklist

### Visual Quality
- [ ] No emojis used as structural icons (use SVG)
- [ ] All icons from consistent family and style
- [ ] Official brand assets with correct proportions
- [ ] Pressed states do not shift layout or cause jitter
- [ ] Semantic theme tokens used consistently

### Interaction
- [ ] All tappable elements show clear pressed feedback
- [ ] Touch targets ≥44×44pt (iOS) / ≥48×48dp (Android)
- [ ] Micro-interaction timing in 150–300ms range
- [ ] Disabled states are visually clear and non-interactive
- [ ] Screen reader focus order matches visual order
- [ ] No nested gesture conflicts (tap/drag/back-swipe)

### Light/Dark Mode
- [ ] Primary text ≥4.5:1 contrast in both modes
- [ ] Secondary text ≥3:1 contrast in both modes
- [ ] Dividers/borders and states distinguishable in both
- [ ] Modal scrim opacity sufficient for foreground readability
- [ ] Both themes tested, not inferred

### Layout
- [ ] Safe areas respected for headers, tab bars, CTAs
- [ ] Scroll content not hidden behind fixed bars
- [ ] Tested on small phone, large phone, tablet (portrait + landscape)
- [ ] Horizontal insets adapt by device/orientation
- [ ] 4/8dp spacing maintained across all levels
- [ ] Long-form text readable on larger devices

### Accessibility
- [ ] Meaningful images/icons have accessibility labels
- [ ] Form fields have labels, hints, error messages
- [ ] Color not sole indicator of meaning
- [ ] Reduced motion and dynamic text size supported
- [ ] Accessibility traits/roles/states announced correctly

---

## Workflow Summary

1. **Analyze requirements** (product type, audience, style keywords, stack)
2. **Generate design system** (comprehensive recommendations)
3. **Supplement with domain searches** as needed (style, color, typography, UX, charts)
4. **Apply stack-specific guidelines** (React Native / React / Next.js / SwiftUI)
5. **Run pre-delivery checklist** before implementation

**Key principle**: If it affects how something looks, feels, moves, or is interacted with—this skill applies.

---

_Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill_
