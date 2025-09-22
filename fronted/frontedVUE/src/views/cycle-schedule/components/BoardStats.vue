<template>
  <div class="stats">
    <div class="stat">
      <div class="stat-label">总课次</div>
      <div class="stat-value">{{ lessonCount }}</div>
    </div>
    <div class="divider" />
    <div class="stat">
      <div class="stat-label">教师数</div>
      <div class="stat-value">{{ teacherCount }}</div>
    </div>
    <div class="divider" />
    <div class="stat">
      <div class="stat-label">学科数</div>
      <div class="stat-value">{{ subjectCount }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  board: { type: Object, default: null } // { dates:[], rows:[{teacher_id, teacher_name, days:{date:[cells...]}}] }
})

/** 累加器：安全地从 board 汇总唯一 lesson/teacher/subject */
const lessonCount = computed(() => {
  const b = props.board
  if (!b?.rows?.length || !b?.dates?.length) return 0
  const ids = new Set()
  for (const r of b.rows) {
    const days = r.days || {}
    for (const d of b.dates) {
      const cells = days[d] || []
      for (const c of cells) if (c?.lesson_id != null) ids.add(c.lesson_id)
    }
  }
  return ids.size
})

const teacherCount = computed(() => {
  const b = props.board
  if (!b?.rows?.length) return 0
  // 只统计“有课”的老师。
  const t = new Set()
  for (const r of b.rows) {
    const has = Object.values(r.days || {}).some(arr => (arr?.length || 0) > 0)
    if (has) t.add(r.teacher_id ?? r.teacher_name ?? '_')
  }
  return t.size
})

const subjectCount = computed(() => {
  const b = props.board
  if (!b?.rows?.length || !b?.dates?.length) return 0
  const s = new Set()
  for (const r of b.rows) {
    const days = r.days || {}
    for (const d of b.dates) {
      const cells = days[d] || []
      for (const c of cells) if (c?.subject) s.add(c.subject)
    }
  }
  return s.size
})
</script>

<style scoped>
.stats {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
}
.stat {
  min-width: 120px;
  padding: 6px 10px;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
}
.divider {
  width: 1px;
  background: #f2f3f5;
  margin: 0 2px;
}
</style>
