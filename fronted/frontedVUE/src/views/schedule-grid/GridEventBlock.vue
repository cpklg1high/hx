<template>
  <div
    class="ev"
    :title="title"
    :style="styleObj"
    @click.stop="$emit('click', event.raw)"
  >
    <div class="line1">{{ event.subject }}｜{{ event.course_mode }}</div>
    <div class="line2">{{ event.teacher }}<span v-if="event.room">｜{{ event.room }}</span></div>
    <div class="line3">{{ event.enrolled }}<span v-if="event.capacity">/{{ event.capacity }}</span></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  event: { type: Object, required: true },
  pxPerMin: { type: Number, default: 1.5 }
})

const styleObj = computed(() => ({
  position: 'absolute',
  top: `${props.event.y}px`,
  left: `${props.event.leftPct}%`,
  width: `${props.event.widthPct}%`,
  height: `${props.event.h}px`,
  borderRadius: '6px',
  border: '1px solid #e5e7eb',
  background: props.event.status === 'finished' ? '#ecfdf5' : (props.event.status === 'canceled' ? '#f5f5f5' : '#eff6ff'),
  padding: '6px 8px',
  overflow: 'hidden',
  cursor: 'pointer',
  boxShadow: '0 1px 2px rgba(0,0,0,.05)',
  fontSize: '12px',
  lineHeight: '16px'
}))

const title = computed(() => {
  const e = props.event
  return `${e.subject}｜${e.course_mode}｜${e.teacher}${e.room?('｜'+e.room):''}｜${e.enrolled}${e.capacity?('/'+e.capacity):''}\n${e.date} ${e.start_time} ~ ${e.end_time}`
})
</script>

<style scoped>
.ev:hover { outline: 2px solid #93c5fd; }
.line1 { font-weight: 600; white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }
.line2, .line3 { white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }
</style>
