<script setup lang="ts">
// The requirements list under a new-password field (UI-FRM-10, DL-91, DL-94 to DL-96). Each line
// turns from unmet to met as the user types, by icon and by hidden "Met" / "Not met" text read
// with its label; it's not a live region, so nothing is announced per keystroke. A line a 422
// marked (`failed`) shows a visible "Not met:" in the error style. A requirement it can't check
// (one it doesn't know, or "not your current password" without one) is plain text.
import { computed } from 'vue'

import type { PasswordRequirement } from '@/composables/usePasswordPolicy'

import Icon from './Icon.vue'

const props = defineProps<{
  id: string
  requirements: PasswordRequirement[]
  password: string
  email: string
  username: string
  /** The current-password field's value, where the form has one. */
  current?: string
  failed: string[]
}>()

type State = 'met' | 'unmet' | 'failed' | 'unchecked'

// Close to the server's `casefold()`: upper-casing first folds "ß" to "SS", as it does.
const fold = (text: string) => text.toUpperCase().toLowerCase()
const same = (a: string, b: string) => fold(a) === fold(b)

function met(requirement: PasswordRequirement): boolean | null {
  const password = props.password
  switch (requirement.code) {
    case 'too_short':
      // Characters, as the server counts them, not UTF-16 units.
      return requirement.value == null ? null : Array.from(password).length >= requirement.value
    case 'same_as_email':
      return !same(password, props.email)
    case 'same_as_username':
      return !same(password, props.username)
    case 'same_as_current':
      return props.current === undefined ? null : password !== props.current
    default:
      return null
  }
}

const lines = computed(() =>
  props.requirements.map((requirement) => {
    const check = met(requirement)
    let state: State = check === null ? 'unchecked' : check && props.password ? 'met' : 'unmet'
    if (props.failed.includes(requirement.code)) state = 'failed'
    return { ...requirement, state }
  }),
)

const ICONS = { met: 'check', unmet: 'circle', failed: 'alert' } as const
</script>

<template>
  <ul v-if="requirements.length" :id="id" class="m-0 flex list-none flex-col gap-1 p-0 text-sm">
    <li
      v-for="line in lines"
      :key="line.code"
      :class="[
        'flex items-center gap-2',
        line.state === 'failed'
          ? 'text-tone-danger-fg'
          : line.state === 'met'
            ? 'text-text'
            : 'text-text-muted',
      ]"
    >
      <Icon v-if="line.state !== 'unchecked'" :name="ICONS[line.state as keyof typeof ICONS]" />
      <span>
        <template v-if="line.state === 'failed'">Not met: </template>
        <span v-else-if="line.state !== 'unchecked'" class="sr-only">
          {{ line.state === 'met' ? 'Met' : 'Not met' }}:
        </span>
        {{ line.label }}
      </span>
    </li>
  </ul>
</template>
