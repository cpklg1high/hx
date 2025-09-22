<template>
  <div class="preplan-grid">
    <div class="grid-toolbar">
      <span class="tip">点击空白格创建班级（默认使用该时间段，创建时可再修改）</span>
    </div>

    <div v-if="!teachers.length" class="empty">
      请选择一个有效周期后加载老师行。
    </div>

    <div v-else class="table">
      <!-- 表头：老师 + 时间 + 周一~周日 -->
      <div class="thead">
        <div class="th th-teacher">老师</div>
        <div class="th th-time">时间</div>
        <div v-for="w in WEEKDAYS" :key="w.key" class="th th-week">{{ w.label }}</div>
      </div>

      <!-- 每位老师一块；右侧为 6 个固定时间段行 -->
      <div v-for="t in teachers" :key="t.teacher_id" class="teacher-block">
        <div class="teacher-name">{{ t.teacher_name || '未指派' }}</div>
        <div class="slots">
          <div v-for="slot in FIXED_SLOTS" :key="slotKey(slot)" class="slot-row">
            <div class="slot-title">{{ slot.label }}</div>

            <div
              v-for="w in WEEKDAYS"
              :key="w.key + slotKey(slot)"
              class="cell"
              @click="emitCreate(t.teacher_id, w, slot)"
            >
              <div class="cell-inner">
                <div class="plus">＋</div>
                <div class="hint">创建</div>
              </div>
            </div>
          </div>
        </div>
      </div> <!-- /teacher-block -->
    </div> <!-- /table -->
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 复用 /cycles/{id}/board 的结构，至少包含 { rows, dates }
  board: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['create-at'])

const WEEKDAYS = [
  { key: 'Mon', label: '周一', idx: 1 },
  { key: 'Tue', label: '周二', idx: 2 },
  { key: 'Wed', label: '周三', idx: 3 },
  { key: 'Thu', label: '周四', idx: 4 },
  { key: 'Fri', label: '周五', idx: 5 },
  { key: 'Sat', label: '周六', idx: 6 },
  { key: 'Sun', label: '周日', idx: 7 },
]

/** 固定 6 个时间段（显示用 label，传参用 start/end） */
const FIXED_SLOTS = [
  { start: '08:00', end: '10:00', label: '08:00 - 10:00' },
  { start: '10:00', end: '12:00', label: '10:00 - 12:00' },
  { start: '13:00', end: '15:00', label: '13:00 - 15:00' },
  { start: '15:00', end: '17:00', label: '15:00 - 17:00' },
  { start: '17:00', end: '19:00', label: '17:00 - 19:00' },
  { start: '19:00', end: '21:00', label: '19:00 - 21:00' },
]

const teachers = computed(() => props.board?.rows || [])

/** 把 board.dates 分桶为 Mon..Sun，仅用于为事件提供“默认源日期” */
const byWeekday = computed(() => {
  const dates = Array.isArray(props.board?.dates) ? props.board.dates : []
  const map = { Mon:[], Tue:[], Wed:[], Thu:[], Fri:[], Sat:[], Sun:[] }
  for (const s of dates) {
    const d = new Date(s + 'T00:00:00')
    if (isNaN(d.getTime())) continue
    const key = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()]
    if (map[key]) map[key].push(s)
  }
  Object.keys(map).forEach(k => map[k].sort())
  return map
})

function firstDateOf(weekdayKey) {
  const arr = byWeekday.value?.[weekdayKey] || []
  return arr.length ? arr[0] : null
}
function allDatesOf(weekdayKey) {
  return byWeekday.value?.[weekdayKey] || []
}
function slotKey(s) { return `${s.start}-${s.end}` }

/** 点击格子 → 通知父组件打开“创建班级”对话框
 *  默认时间即为该格时间段；日期不展示，仅在事件参数中提供默认源日（可为空）
 */
function emitCreate(teacherId, weekday, slot) {
  emit('create-at', {
    teacherId,
    weekday: weekday.key,             // 'Mon'..'Sun'
    weekdayIdx: weekday.idx,          // 1..7
    start: slot.start,                // 默认开始时间
    end: slot.end,                    // 默认结束时间
    sourceDate: firstDateOf(weekday.key), // 'YYYY-MM-DD' | null
    allDates: allDatesOf(weekday.key),    // ['YYYY-MM-DD', ...]
  })
}
</script>

<style scoped>
.preplan-grid { margin-top: 12px; }
.grid-toolbar { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.tip { color:#909399; }

.table { width:100%; overflow:auto; border:1px solid #ebeef5; border-radius:8px; }

/* 表头：老师(180) + 时间(140) + 7列 */
.thead {
  display:grid;
  grid-template-columns: 180px 140px repeat(7, minmax(140px, 1fr));
  background:#fafafa; border-bottom:1px solid #ebeef5;
}
.th { padding:10px; font-weight:600; border-right:1px solid #eee; }
.th:last-child { border-right:none; }
.th-teacher { position:sticky; left:0; background:#fafafa; z-index:1; }

.teacher-block {
  display:grid;
  grid-template-columns: 180px 1fr;
  border-bottom:1px solid #f2f2f2;
}
.teacher-name {
  padding:10px;
  border-right:1px solid #f2f2f2;
  position:sticky; left:0; background:white; z-index:1;
}

.slots { display:flex; flex-direction:column; }
.slot-row { display:grid; grid-template-columns: 140px repeat(7, minmax(140px,1fr)); }
.slot-title {
  padding:8px 10px; color:#606266;
  border-right:1px dashed #eee; border-bottom:1px dashed #f5f5f5; background:#fcfcfc;
}
.cell {
  border-right:1px dashed #f2f2f2; border-bottom:1px dashed #f5f5f5;
  cursor:pointer; min-height:56px;
}
.cell-inner { height:100%; display:flex; align-items:center; justify-content:center; gap:6px; color:#a0a0a0; }
.cell:hover .cell-inner { color:#409eff; }
.plus { font-size:18px; line-height:18px; }

.empty { padding:18px; color:#909399; }
</style>
