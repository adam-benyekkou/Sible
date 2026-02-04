# ⚪ SIBLE DESIGN SYSTEM (Vercel / Geist Aesthetic)

> **INSTRUCTION:** You are implementing a pixel-perfect clone of the Vercel Dashboard aesthetic using Pico.css variables.
> **KEYWORD:** "Radical Minimalism". High legibility, strict greyscale, subtle borders.

## 1. Typography (The Core)
- **Font:** 'Inter', sans-serif (closest match to Geist Sans).
- **Mono:** 'JetBrains Mono' (for code/terminals).
- **Tracking:** Tight (`-0.02em` for headings, `-0.01em` for body).
- **Weights:** 500 for text, 600 for headings.

## 2. CSS Variables (The "Geist" Palette)
Add this STRICTLY to `static/css/style.css`. We use a "Light Mode First" approach, but support Dark Mode via media query.

```css
/* --- GLOBAL VARIABLES (Light Theme - Default) --- */
:root {
    /* 1. The Geist Greyscale */
    --ds-background-100: #ffffff;
    --ds-background-200: #fafafa; /* Slight grey for sidebars */
    --ds-gray-100: #f5f5f5;       /* Hover states */
    --ds-gray-200: #eaeaea;       /* Borders */
    --ds-gray-alpha-400: rgba(0, 0, 0, 0.08); /* Shadows */
    
    /* 2. Text Colors */
    --ds-gray-1000: #000000;      /* Headings / Primary Actions */
    --ds-gray-900: #171717;       /* Body text */
    --ds-gray-600: #666666;       /* Muted text / Meta data */
    
    /* 3. Sible Identity (Ansible Red - Subtle usage only) */
    --sible-red: #E03E3E;         /* Slightly desaturated for white bg */
    --sible-red-bg: #FFEEEE;      /* For error backgrounds */

    /* 4. Pico Overrides */
    --pico-font-family: 'Inter', system-ui, sans-serif;
    --pico-background-color: var(--ds-background-100);
    --pico-color: var(--ds-gray-900);
    --pico-border-radius: 6px;    /* Vercel uses 6px exactly */
    --pico-form-element-border-color: var(--ds-gray-200);
    --pico-primary-background: var(--ds-gray-1000); /* Black buttons */
    --pico-primary-border: var(--ds-gray-1000