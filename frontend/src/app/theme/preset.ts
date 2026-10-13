/**
 * The PrimeVue theme (docs/ui-design-guide.md §3.5): Aura, with every color role it uses pointed
 * at our tokens (`src/app/styles/tokens.css`). The tokens switch themselves with `light-dark()`,
 * so one mapping serves both themes. This is the only place PrimeVue's colors are set
 * (UI-TOK-12); a component adopted later gets its own mapping here first (UI-STY-6).
 */
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

const token = (name: string) => `var(--color-${name})`

// PrimeVue wants an 11-step primary scale; ours is the accent mixed toward the page.
const towardPage = (accentPercent: number) =>
  `color-mix(in srgb, ${token('accent')} ${accentPercent}%, ${token('bg')})`

const focusRing = {
  width: 'var(--focus-ring-width)',
  style: 'solid',
  color: token('focus'),
  offset: 'var(--focus-ring-offset)',
  shadow: 'none',
}

const textColors = { color: token('text'), focusColor: token('text') }
const mutedIcon = { color: token('text-muted'), focusColor: token('text-muted') }
const overlay = {
  background: token('surface-raised'),
  borderColor: token('border-subtle'),
  color: token('text'),
  shadow: 'var(--shadow-popover)',
}

function buttonSeverity(fill: string, hover: string, on: string) {
  return {
    background: token(fill),
    hoverBackground: token(hover),
    activeBackground: token(hover),
    borderColor: token(fill),
    hoverBorderColor: token(hover),
    activeBorderColor: token(hover),
    color: token(on),
    hoverColor: token(on),
    activeColor: token(on),
    focusRing: { color: token('focus'), shadow: 'none' },
  }
}

export const overrides = {
  semantic: {
    primary: {
      50: towardPage(6),
      100: towardPage(12),
      200: towardPage(24),
      300: towardPage(40),
      400: towardPage(70),
      500: token('accent'),
      600: token('accent-hover'),
      700: token('accent-hover'),
      800: token('accent-hover'),
      900: token('accent-hover'),
      950: token('accent-hover'),
      color: token('accent'),
      contrastColor: token('on-accent'),
      hoverColor: token('accent-hover'),
      activeColor: token('accent-hover'),
    },
    focusRing,
    formField: {
      focusRing,
      background: token('bg'),
      disabledBackground: token('disabled-bg'),
      filledBackground: token('surface'),
      filledHoverBackground: token('surface'),
      filledFocusBackground: token('surface'),
      borderColor: token('border'),
      hoverBorderColor: token('border'),
      focusBorderColor: token('focus'),
      invalidBorderColor: token('tone-danger-edge'),
      color: token('text'),
      disabledColor: token('disabled-text'),
      placeholderColor: token('placeholder'),
      invalidPlaceholderColor: token('placeholder'),
      floatLabelColor: token('text-muted'),
      floatLabelFocusColor: token('text-muted'),
      floatLabelActiveColor: token('text-muted'),
      floatLabelInvalidColor: token('tone-danger-fg'),
      iconColor: token('text-muted'),
    },
    text: {
      color: token('text'),
      hoverColor: token('text'),
      mutedColor: token('text-muted'),
      hoverMutedColor: token('text-muted'),
    },
    content: {
      background: token('surface-raised'),
      hoverBackground: token('hover'),
      borderColor: token('border-subtle'),
      color: token('text'),
      hoverColor: token('text'),
    },
    overlay: {
      select: overlay,
      popover: overlay,
      modal: { ...overlay, shadow: 'var(--shadow-dialog)' },
    },
    list: {
      option: {
        ...textColors,
        focusBackground: token('hover'),
        selectedBackground: token('selected'),
        selectedFocusBackground: token('selected'),
        selectedColor: token('text'),
        selectedFocusColor: token('text'),
        icon: mutedIcon,
      },
      optionGroup: { color: token('text-muted') },
    },
    navigation: {
      item: {
        ...textColors,
        focusBackground: token('hover'),
        activeBackground: token('selected'),
        activeColor: token('text'),
        icon: { ...mutedIcon, activeColor: token('text-muted') },
      },
      submenuLabel: { color: token('text-muted') },
      submenuIcon: { ...mutedIcon, activeColor: token('text-muted') },
    },
    highlight: {
      background: token('selected'),
      focusBackground: token('selected'),
      color: token('text'),
      focusColor: token('text'),
    },
  },
  components: {
    button: {
      root: {
        primary: buttonSeverity('accent', 'accent-hover', 'on-accent'),
        danger: buttonSeverity('danger', 'danger-hover', 'on-danger'),
        // Secondary is the outlined button: no fill until hovered (UI-TOK-8).
        secondary: {
          background: 'transparent',
          hoverBackground: token('hover'),
          activeBackground: token('hover'),
          borderColor: token('border'),
          hoverBorderColor: token('border'),
          activeBorderColor: token('border'),
          color: token('text'),
          hoverColor: token('text'),
          activeColor: token('text'),
          focusRing: { color: token('focus'), shadow: 'none' },
        },
      },
    },
  },
}

export const preset = definePreset(Aura, overrides)

/** PrimeVue's theme options: our preset, our dark selector, and the CSS layer order. */
export const theme = {
  preset,
  options: {
    darkModeSelector: '[data-theme="dark"]',
    cssLayer: { name: 'primevue', order: 'theme, base, primevue, components, utilities' },
  },
}
