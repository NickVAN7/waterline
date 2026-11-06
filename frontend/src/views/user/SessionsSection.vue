<script setup lang="ts">
// Account settings' Sessions (design-doc §4; DL-298 to DL-301): the user's live sessions, each
// with its device from its user agent, this one marked, when it signed in, and when it was last
// active; and Sign out other sessions, which stays in place, blocked with its reason, once there
// are none (a control isn't removed by its own action).
import { computed, nextTick, onUnmounted, ref } from 'vue'

import { api, ApiError, client, NETWORK_ERROR } from '@/api/client'
import { deviceLabel, THIS_SESSION } from '@/app/labels'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { ANNOUNCE_DELAY_MS, FORM_MESSAGES } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'

// shortcut: the first 200 sessions only (the API's page limit); page them if anyone has more.
const page = useLoad(() =>
  api(client.GET('/api/me/sessions', { params: { query: { limit: 200 } } })),
)
void page.run()

const others = computed(() => page.data.value?.items.some((s) => !s.is_current) ?? false)
const signingOut = ref(false)
const done = ref('')
const failure = ref('')
const failures = ref(0)
const button = ref<InstanceType<typeof Button>>()
const failureAlert = ref<InstanceType<typeof Alert>>()

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const when = (value: string) => timeFormat.format(new Date(value))

async function signOutOthers() {
  signingOut.value = true
  failure.value = ''
  done.value = ''
  try {
    await api(client.POST('/api/me/sessions/sign-out-others'))
    done.value = 'Your other sessions are signed out.'
    await page.run()
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failure.value = `Couldn't sign out your other sessions. ${
      error.code === NETWORK_ERROR ? FORM_MESSAGES.network : FORM_MESSAGES.generic
    }`
    failures.value += 1
    await nextTick()
    failureAlert.value?.focus()
  } finally {
    signingOut.value = false
  }
}

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(announcing))

function dismiss() {
  failure.value = ''
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = 'Alert dismissed'), ANNOUNCE_DELAY_MS)
  button.value?.focus()
}
</script>

<template>
  <section aria-labelledby="sessions-heading" class="flex flex-col gap-4">
    <h2 id="sessions-heading" class="m-0 text-lg font-semibold">Sessions</h2>
    <Alert v-if="failure" ref="failureAlert" :key="failures" live dismissible @dismiss="dismiss">{{
      failure
    }}</Alert>
    <div :aria-busy="page.loading.value ? 'true' : 'false'" class="flex flex-col gap-3">
      <ErrorState
        v-if="page.error.value"
        :key="page.failures.value"
        :live="page.failures.value > 1 || done !== ''"
        thing="your sessions"
        :pending="page.loading.value"
        @retry="page.retry"
      />
      <Skeleton v-else-if="!page.data.value" />
      <ul v-else class="m-0 flex list-none flex-col gap-3 p-0">
        <li
          v-for="item in page.data.value.items"
          :key="item.id"
          class="flex flex-col gap-1 border-b border-border-subtle pb-3"
        >
          <span class="flex flex-wrap items-center gap-2 font-medium">
            {{ deviceLabel(item.user_agent) }}
            <Badge v-if="item.is_current" :tone="THIS_SESSION.tone" :icon="THIS_SESSION.icon">{{
              THIS_SESSION.label
            }}</Badge>
          </span>
          <span class="text-sm text-text-muted">
            Signed in {{ when(item.created_at) }} ·
            {{ item.is_current ? 'Active now' : `Last active ${when(item.last_seen_at)}` }}
          </span>
        </li>
      </ul>
    </div>
    <div v-if="page.data.value" class="flex flex-col gap-2">
      <Button
        ref="button"
        variant="secondary"
        class="self-start"
        :pending="signingOut"
        pending-label="Signing out…"
        :blocked="!others"
        :aria-describedby="others ? undefined : 'sessions-none'"
        @click="signOutOthers"
        >Sign out other sessions</Button
      >
      <p v-if="!others" id="sessions-none" class="m-0 text-sm text-text-muted">
        You have no other sessions.
      </p>
      <SuccessStatus :message="done" />
    </div>
    <p class="sr-only" aria-live="polite">
      {{ page.loading.value && !page.data.value ? 'Loading your sessions…' : '' }}
    </p>
    <p class="sr-only" aria-live="polite">{{ said }}</p>
  </section>
</template>
