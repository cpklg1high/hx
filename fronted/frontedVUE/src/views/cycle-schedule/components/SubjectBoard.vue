<template>
  <div class="board">
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint error">看板加载失败</div>
    <div v-else-if="!board || !board.dates?.length" class="hint">暂无数据</div>
    <div v-else class="table-wrap">
      <!-- 表头 -->
      <div class="row header">
        <div class="cell sticky left subject">学科</div>
        <div class="cell" v-for="d in board.dates" :key="d">{{ d }}</div>
      </div>

      <!-- 行：按学科聚合 -->
      <div class="rows">
        <div
          class="row"
          v-for="s in filteredSubjects"
          :key="`sub-${s.name}`"
        >
          <div class="cell sticky left subject">{{ s.name }}</div>
          <div
            class="cell"
            v-for="d in board.dates"
            :key="`c-${s.name}-${d}`"
          >
            <div
              v-for="cell in (s.byDate[d] || [])"
              :key="cell.lesson_id"
              class="pill clickable"
              :title="pillTitle(cell, s.name)"
              @click="$emit('open-lesson', { lessonId: cell.lesson_id, date: d, classGroupId: cell.class_group_id })"
            >
              <div class="pill-line">
                {{ cell.class_group_name }} · {{ cell.slot }}
              </div>
              <div class="pill-sub">
                {{ cell.teacher_name || '未指派' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineEmits(['open-lesson'])

const props = defineProps({
  board: { type: Object, default: null },   // { dates:[], rows:[{teacher_id,teacher_name,days:{date: [cells]}}] }
  loading: { type: Boolean, default: false },
  error: { type: [Object, String], default: null },
  filterText: { type: String, default: '' } // 此视图下按「学科名」过滤
})

/**
 * 将 TeacherBoard 的数据透视为 Subject 维度
 * 结构：[{ name, byDate: { '2025-09-01': [cells...] }, teachers:Set }]
 */
const subjects = computed(() => {
  const b = props.board
  if (!b?.rows?.length || !b?.dates?.length) return []

  // subjMap: name -> { name, byDate: {}, teachers: Set }
  const subjMap = new Map()

  for (const row of b.rows) {
    const tId = row.teacher_id
    const tName = row.teacher_name || ''
    const days = row.days || {}
    for (const d of b.dates) {
      const cells = days[d] || []
      for (const c of cells) {
        const name = c.subject || '未知学科'
        if (!subjMap.has(name)) {
          subjMap.set(name, { name, byDate: {}, teachers: new Set() })
        }
        const entry = subjMap.get(name)
        if (!entry.byDate[d]) entry.byDate[d] = []
        entry.byDate[d].push({
          lesson_id: c.lesson_id,
          class_group_id: c.class_group_id,
          class_group_name: c.class_group_name,
          slot: c.slot,
          teacher_id: tId,
          teacher_name: tName
        })
        entry.teachers.add(tId)
      }
    }
  }

  // 转数组并按学科名排序
  return Array.from(subjMap.values()).sort((a, b2) => a.name.localeCompare(b2.name, 'zh'))
})

const filteredSubjects = computed(() => {
  const q = (props.filterText || '').trim().toLowerCase()
  if (!q) return subjects.value
  return subjects.value.filter(s => s.name.toLowerCase().includes(q))
})

function pillTitle(cell, subject) {
  return `${subject} | ${cell.class_group_name} | ${cell.slot} | ${cell.teacher_name || '未指派'}`
}
</script>

<style scoped>
.board { width: 100%; }
.hint { padding: 12px; color: #909399; }
.hint.error { color: #f56c6c; }

.table-wrap {
  overflow-x: auto;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.row {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(160px, 1fr);
  border-bottom: 1px solid #f2f3f5;
}
.row.header {
  position: sticky;
  top: 0;
  background: #fafafa;
  font-weight: 600;
  z-index: 1;
}
.rows .row:last-child { border-bottom: none; }

.cell {
  padding: 8px;
  min-height: 56px;
  border-right: 1px solid #f2f3f5;
}
.row .cell:last-child { border-right: none; }

.sticky.left { position: sticky; left: 0; background: #fff; z-index: 2; }
.subject { width: 200px; min-width: 200px; }

/* 课程小块 */
.pill {
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  margin-bottom: 6px;
  font-size: 12px;
  line-height: 1.2;
}
.pill:last-child { margin-bottom: 0; }
.pill-line { font-weight: 600; }
.pill-sub { color: #909399; margin-top: 2px; }

.clickable { cursor: pointer; transition: transform .05s ease; }
.clickable:active { transform: scale(0.98); }
</style>
