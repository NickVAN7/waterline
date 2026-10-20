<script setup lang="ts">
// A project's module choice (design-doc §1.1), in the create dialog and in settings: each module
// with its note from module guidance and whether it's recommended for the type; a module that
// can't be enabled yet (v2) only described. `warning(module)` is the text shown under a module
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
    <template v-for="note in guidance.modules" :key="note.module">
      <div v-if="enableable(note.module)" class="flex flex-col gap-1">
        <label class="flex items-start gap-2">
          <input
            v-model="modules"
            type="checkbox"
            :value="note.module"
            :aria-describedby="
              warning?.(note.module) ? `${prefix}-module-${note.module}-warning` : undefined
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
          v-if="warning?.(note.module)"
          :id="`${prefix}-module-${note.module}-warning`"
          class="m-0 flex items-start gap-1 pl-8 text-sm text-tone-warning-fg"
        >
          <Icon name="warning" />{{ warning(note.module) }}
        </p>
      </div>
      <p v-else class="m-0 flex flex-col pl-8 text-text-muted">
        <span>
          {{ MODULE[note.module] ?? note.module }} · {{ NOT_AVAILABLE_YET }}
          <span v-if="recommended(note.module)"> · Recommended for {{ PROJECT_TYPE[type] }}</span>
        </span>
        <span class="text-sm">{{ note.note }}</span>
      </p>
    </template>
    <GroupError :id="`${prefix}-modules-error`" :error="error" />
  </fieldset>
</template>
