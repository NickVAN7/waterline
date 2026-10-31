<script setup lang="ts">
// A project's module choice (design-doc §1.1), in the create dialog and in settings: each module
// with its note from module guidance and whether it's recommended for the type; a module that
// hasn't shipped is a disabled checkbox with "Not available yet" (DL-136; `available`): a native
// `disabled`, as its own label, which names it, says why (UI-TOK-10). `warning(module)` is the text shown under a module
// (settings warns when one is turned off). The group's id is `{prefix}-enabled-modules`.
import type { components } from '@/api/schema'
import { MODULE, NOT_AVAILABLE_YET, PROJECT_TYPE } from '@/app/labels'
import GroupError from '@/components/GroupError.vue'
import Icon from '@/components/Icon.vue'

import { enableable } from './modules'

type ProjectType = components['schemas']['ProjectType']
type ProjectModule = components['schemas']['ProjectModule']

const props = defineProps<{
  prefix: string
  guidance: components['schemas']['ModuleGuidance']
  type: ProjectType
  error?: string
  warning?: (module: ProjectModule) => string
}>()
const emit = defineEmits<{ edit: [] }>()

const modules = defineModel<ProjectModule[]>({ required: true })

// Only a module the API's `ProjectModule` allows can be turned off, so only one may warn.
const warningFor = (module: string) => (enableable(module) && props.warning?.(module)) || ''

const recommended = (module: string) =>
  props.guidance.types.find((t) => t.type === props.type)?.recommended.includes(module) ?? false
</script>

<template>
  <fieldset
    :id="`${prefix}-enabled-modules`"
    tabindex="-1"
    :aria-describedby="error ? `${prefix}-modules-error` : undefined"
    :aria-invalid="error ? 'true' : undefined"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Modules</legend>
    <div v-for="note in guidance.modules" :key="note.module" class="flex flex-col gap-1">
      <label class="flex items-start gap-2">
        <input
          v-model="modules"
          type="checkbox"
          :value="note.module"
          :disabled="!note.available"
          :aria-describedby="
            warningFor(note.module) ? `${prefix}-module-${note.module}-warning` : undefined
          "
          class="size-(--target-min) shrink-0"
          @change="emit('edit')"
        />
        <span class="flex flex-col">
          <span class="font-medium">
            {{ MODULE[note.module] ?? note.module }}
            <span v-if="recommended(note.module)" class="text-sm text-text-muted">
              · Recommended for {{ PROJECT_TYPE[type] }}</span
            >
            <span v-if="!note.available" class="text-sm text-text-muted">
              · {{ NOT_AVAILABLE_YET }}</span
            >
          </span>
          <span class="text-sm text-text-muted">{{ note.note }}</span>
        </span>
      </label>
      <p
        v-if="warningFor(note.module)"
        :id="`${prefix}-module-${note.module}-warning`"
        class="m-0 flex items-start gap-1 pl-8 text-sm text-tone-warning-fg"
      >
        <Icon name="warning" />{{ warningFor(note.module) }}
      </p>
    </div>
    <GroupError :id="`${prefix}-modules-error`" :error="error" />
  </fieldset>
</template>
