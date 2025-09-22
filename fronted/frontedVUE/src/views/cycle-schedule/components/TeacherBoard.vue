<!-- 只贴变化完整组件，直接覆盖即可 -->
<template>
  <div class="board">
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint error">看板加载失败</div>
    <div v-else-if="!board || !board.dates?.length" class="hint">暂无数据</div>
    <div v-else class="table-wrap">
      <!-- 表头 -->
      <div class="row header">
        <div class="cell sticky left teacher">老师</div>
        <div class="cell" v-for="d in board.dates" :key="d">{{ d }}</div>
      </div>

      <!-- 行 -->
      <div class="rows">
        <div
          class="row"
          v-for="r in filteredRows"
          :key="`t-${r.teacher_id}`"
        >
          <div class="cell sticky left teacher">{{ r.teacher_name || '未指派' }}</div>
          <div
            class="cell"
            v-for="d in board.dates"
            :key="`c-${r.teacher_id}-${d}`"
          >
            <div
              v-for="cell in (r.days?.[d] || [])"
              :key="cell.lesson_id"
              class="pill clickable"
              :title="pillTitle(cell)"
              @click="$emit('open-lesson', { lessonId: cell.lesson_id, date: d, classGroupId: cell.class_group_id })"
            >
              <div class="pill-line">{{ cell.subject }} · {{ cell.slot }}</div>
              <div class="pill-sub">{{ cell.class_group_name }}</div>
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
  board: { type: Object, default: null },      // { dates:[], rows:[] }
  loading: { type: Boolean, default: false },
  error: { type: [Object, String], default: null },
  filterText: { type: String, default: '' }
})

const filteredRows = computed(() => {
  if (!props.board?.rows) return []
  const q = (props.filterText || '').trim().toLowerCase()
  if (!q) return props.board.rows
  return props.board.rows.filter(r => (r.teacher_name || '').toLowerCase().includes(q))
})

function pillTitle(cell) {
  return `${cell.subject} | ${cell.class_group_name} | ${cell.slot}`
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
.teacher { width: 200px; min-width: 200px; }

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
