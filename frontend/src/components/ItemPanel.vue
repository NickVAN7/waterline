<script setup lang="ts">
// An item opened from a list (UI-SHL-11; DL-262, DL-321 to DL-325): at 64rem and wider a split
// pane beside the list, which stays usable, a complementary region named by `label` ("Requirement
// PORTAL-RQ-3"), resizable by its separator (560px by default, 400 to 800px, remembered per viewer
// in `localStorage`; dragged, stepped by a click without a drag, or moved by the arrow keys,
// DL-355); below 64rem a modal overlay (a `showModal()` dialog: the page inert, focus
// kept in it). The content is one teleport that moves between the two, so crossing the width
// keeps what it holds (an open edit included). Its header: the item's ID and status (`meta`),
// Open full page, Copy link, and Close as icon buttons, then the title, the panel's heading,
// which takes focus when it opens or swaps to another item; the item itself follows (`default`).
// The list's URL holds the open item (`?open=RQ-7`): Close and Esc ask the page to take it away
// (`dismiss`), so the page can first ask about unsaved edits (DL-323), and Back works the same;
// the page then calls `close()`, which returns focus to the ID that opened the panel, or to
// `fallbackFocus`. Esc that something inside has cancelled (an edit form, a menu) doesn't close
// it. Shared by every item that opens this way (requirements; tasks in Slice 3).
import { inject, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { type RouteLocationRaw, useRouter } from 'vue-router'

import { ANNOUNCE_DELAY_MS } from '@/composables/useFormErrors'

import Icon from './Icon.vue'

const props = defineProps<{
  title: string
  label: string
  fullPage: RouteLocationRaw
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ dismiss: []; closed: [] }>()

const router = useRouter()
// The layout's column right of `main` (`AppLayout`, DL-356): the split pane goes there, from
// under the header to the window's foot, so the page beside it (its header too) narrows. Mounted
// without the layout (a spec), it stays in place.
const sidePane = inject<string | null>('sidePane', null)

// The split pane's width: 64rem, the layout's wide breakpoint (DL-321).
const query = window.matchMedia('(min-width: 64rem)')
const wide = ref(query.matches)
const onWidth = () => (wide.value = query.matches)
onMounted(() => query.addEventListener('change', onWidth))
onBeforeUnmount(() => query.removeEventListener('change', onWidth))

// In CSS pixels, as DL-322 states them; drawn in rem.
const WIDTH = { initial: 560, min: 400, max: 800, step: 16 }
const STORED = 'waterline.itemPanelWidth'
const clamp = (value: number) => Math.min(WIDTH.max, Math.max(WIDTH.min, Math.round(value)))
function storedWidth(): number {
  try {
    const value = Number(window.localStorage.getItem(STORED))
    return value ? clamp(value) : WIDTH.initial
  } catch {
    return WIDTH.initial
  }
}
const width = ref(storedWidth())
function keepWidth() {
  try {
    window.localStorage.setItem(STORED, String(width.value))
  } catch {
    // Blocked storage: the width lasts until the page goes.
  }
}
// The panel is on the right: Left widens it, Right narrows it.
function resizeKey(event: KeyboardEvent) {
  const by = { ArrowLeft: WIDTH.step, ArrowRight: -WIDTH.step }[event.key]
  if (!by) return
  event.preventDefault()
  width.value = clamp(width.value + by)
  keepWidth()
}
// A click without a drag (DL-355, WCAG 2.5.7) steps through these, back to the narrowest.
const STEPS = [WIDTH.min, WIDTH.initial, WIDTH.max]
// Less movement than this between press and release is a click, not a drag.
const CLICK_SLOP = 4
let dragFrom: { x: number; width: number; moved: boolean } | null = null
function dragStart(event: PointerEvent) {
  // The primary button only: a right-click opens the browser's menu, and isn't a click here.
  if (event.button !== 0) return
  dragFrom = { x: event.clientX, width: width.value, moved: false }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function dragMove(event: PointerEvent) {
  if (!dragFrom) return
  if (Math.abs(event.clientX - dragFrom.x) >= CLICK_SLOP) dragFrom.moved = true
  if (dragFrom.moved) width.value = clamp(dragFrom.width + dragFrom.x - event.clientX)
}
function dragEnd() {
  if (!dragFrom) return
  if (!dragFrom.moved) width.value = STEPS.find((step) => step > width.value) ?? WIDTH.min
  dragFrom = null
  keepWidth()
}
// A press the browser cancels (a system gesture) is neither a click nor a finished drag.
function dragCancel() {
  if (!dragFrom) return
  width.value = dragFrom.width
  dragFrom = null
}

const titleId = useId()
const wideId = useId()
const narrowId = useId()
const dialog = ref<HTMLDialogElement>()
const heading = ref<HTMLElement>()
const isOpen = ref(false)
let opener: HTMLElement | null = null
let returnFocus = true
// Set while the overlay closes only because the panel moved to the split pane.
let moving = false

function rememberOpener() {
  // The body is no opener: nothing had focus (a panel opened by its URL), so the fallback takes it.
  const active = document.activeElement
  opener = active instanceof HTMLElement && active !== document.body ? active : null
}

async function open(): Promise<void> {
  rememberOpener()
  isOpen.value = true
  await nextTick()
  if (!wide.value) dialog.value?.showModal()
  heading.value?.focus()
}

// Another item in the open panel (DL-323): its ID, now focused, is where Close returns.
async function swapped(): Promise<void> {
  rememberOpener()
  await nextTick()
  heading.value?.focus()
}

function close({ returnFocus: back = true } = {}): void {
  if (!isOpen.value) return
  returnFocus = back
  // The overlay's close event finishes it, as every other way it closes does.
  if (dialog.value?.open) dialog.value.close()
  else finish()
}

function finish(): void {
  if (moving) {
    moving = false
    return
  }
  isOpen.value = false
  emit('closed')
  if (!returnFocus) {
    // Nothing: focus belongs to the page the action opened.
  } else if (opener?.isConnected) opener.focus()
  else props.fallbackFocus?.()
  opener = null
  returnFocus = true
}

// Across the breakpoint while open: the overlay opens or closes around the same content. Moving
// the content blurs what had focus, and the dialog's own focusing moves it again, so it's put
// back where it was, or on the title.
watch(wide, async (isWide) => {
  if (!isOpen.value) return
  const active = document.activeElement
  const focused = active instanceof HTMLElement && heading.value?.parentElement?.contains(active)
  await nextTick()
  if (isWide && dialog.value?.open) {
    moving = true
    dialog.value.close()
  } else if (!isWide) dialog.value?.showModal()
  if (focused && active.isConnected) active.focus()
  else if (focused) heading.value?.focus()
})

// Esc in the split pane, unless something inside used it (an edit form, a menu), or it came from
// a dialog opened from the panel (Change restriction…, Delete…): that dialog's keydown bubbles
// through the panel, and its own cancel comes after (UI-SHL-11).
function escape(event: KeyboardEvent) {
  if (event.defaultPrevented || (event.target as Element).closest('dialog')) return
  emit('dismiss')
}

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(announcing))

// What happened, through the live region: never a false success (as TemporaryPasswordNotice).
async function copy(): Promise<void> {
  said.value = ''
  clearTimeout(announcing)
  let text = "Couldn't copy the link. Open the full page and copy its address."
  try {
    await navigator.clipboard.writeText(
      new URL(router.resolve(props.fullPage).href, window.location.origin).href,
    )
    text = 'Link copied.'
  } catch {
    // Blocked or unavailable: `text` says so.
  }
  announcing = setTimeout(() => (said.value = text), ANNOUNCE_DELAY_MS)
}

const iconButton =
  'inline-flex size-(--control-height-sm) items-center justify-center rounded-md text-text hover:bg-hover'

defineExpose({ open, close, swapped, focusTitle: () => heading.value?.focus() })
</script>

<template>
  <!-- The split pane: right of the page, sticky under the header, at full height. -->
  <Teleport defer :to="`#${sidePane}`" :disabled="!sidePane">
    <aside
      v-show="isOpen && wide"
      :aria-label="label"
      class="sticky top-(--header-height) flex h-(--split-pane-height) shrink-0 self-start"
      :style="{ width: `${width / 16}rem` }"
      @keydown.esc="escape"
    >
      <div
        role="separator"
        tabindex="0"
        aria-orientation="vertical"
        aria-label="Resize the panel"
        :aria-valuenow="width"
        :aria-valuetext="`${width} pixels wide`"
        :aria-valuemin="WIDTH.min"
        :aria-valuemax="WIDTH.max"
        class="group flex w-(--target-min) shrink-0 cursor-col-resize touch-none justify-end"
        @keydown="resizeKey"
        @pointerdown="dragStart"
        @pointermove="dragMove"
        @pointerup="dragEnd"
        @pointercancel="dragCancel"
      >
        <span class="w-px bg-border group-hover:bg-accent group-focus-visible:bg-accent" />
      </div>
      <div :id="wideId" class="min-w-0 flex-1 overflow-y-auto bg-surface" />
    </aside>
  </Teleport>
  <!-- The overlay below 64rem, docked at the right at full height. -->
  <dialog
    ref="dialog"
    :aria-labelledby="titleId"
    class="my-0 mr-0 ml-auto h-dvh max-h-none w-full max-w-(--content-narrow) overflow-y-auto border border-border bg-surface p-0 text-text shadow-dialog"
    @cancel.prevent="emit('dismiss')"
    @close="finish"
  >
    <div :id="narrowId" />
  </dialog>
  <Teleport defer :to="`#${wide ? wideId : narrowId}`">
    <div v-if="isOpen" class="flex flex-col gap-4 p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-3"><slot name="meta" /></div>
        <div class="flex items-center gap-1">
          <RouterLink
            :to="fullPage"
            aria-label="Open full page"
            title="Open full page"
            :class="iconButton"
            ><Icon name="external"
          /></RouterLink>
          <button
            type="button"
            aria-label="Copy link"
            title="Copy link"
            :class="iconButton"
            @click="copy"
          >
            <Icon name="link" />
          </button>
          <button
            type="button"
            aria-label="Close"
            title="Close"
            :class="iconButton"
            @click="emit('dismiss')"
          >
            <Icon name="x" />
          </button>
        </div>
      </div>
      <h2 :id="titleId" ref="heading" tabindex="-1" class="m-0 text-xl font-semibold">
        {{ title }}
      </h2>
      <p class="m-0 text-sm" aria-live="polite">{{ said }}</p>
      <slot />
    </div>
  </Teleport>
</template>
