<template>
  <div class="grid-wrap">
    <!-- 表头：列名 -->
    <div class="header" :style="{ gridTemplateColumns: headerCols }">
      <div class="header-cell time-col">时间</div>
      <div v-for="col in columns" :key="col.key" class="header-cell">{{ col.label }}</div>
    </div>

    <!-- 主体：时间轴 + 列容器 -->
    <div class="body">
      <!-- 时间刻度 -->
      <div class="time-rail" :style="{ height: canvasHeight + 'px' }">
        <div v-for="tick in ticks" :key="tick.key" class="tick" :style="{ top: tick.y + 'px' }">
          <span class="tick-label">{{ tick.label }}</span>
          <span class="tick-line"></span>
        </div>
      </div>

      <!-- 列容器（绝对定位事件块） -->
      <div class="cols" :style="{ gridTemplateColumns: bodyCols }">
        <div v-for="col in columns" :key="col.key" class="col-cell">
          <div class="events" :style="{ height: canvasHeight + 'px' }" @click="(e)=>onColBlankClick(e, col)">
            <GridEventBlock
              v-for="ev in eventsByCol[col.key]"
              :key="ev.id"
              :event="ev"
              :px-per-min="pxPerMin"
              @click.stop="handleClick"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-if="!events.length" class="empty">本周暂无课程。点击任意年级列的时间网格即可新建班级。</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import GridEventBlock from './GridEventBlock.vue'

const props = defineProps({
  range: { type: Object, required: true },
  columns: { type: Array, required: true },
  events: { type: Array, required: true },
  pxPerMin: { type: Number, default: 1.5 },
  dayStart: { type: Number, default: 420 },
  dayEnd: { type: Number, default: 1320 }
})
const emits = defineEmits(['event-click','blank-click'])

const headerCols = computed(() => `200px ${props.columns.map(()=> '1fr').join(' ')}`)
const bodyCols = computed(() => `${props.columns.map(()=> '1fr').join(' ')}`)
const canvasHeight = computed(() => (props.dayEnd - props.dayStart) * props.pxPerMin)

// 时间刻度（每 60 分钟）
const ticks = computed(() => {
  const res = []
  for (let m = props.dayStart; m <= props.dayEnd; m += 60) {
    const h = Math.floor(m / 60), mm = m % 60
    const label = `${String(h).padStart(2,'0')}:${String(mm).padStart(2,'0')}`
    res.push({ key: m, y: (m - props.dayStart) * props.pxPerMin, label })
  }
  return res
})

// 按列分组事件
const eventsByCol = computed(() => {
  const map = {}
  for (const col of props.columns) map[col.key] = []
  for (const ev of props.events) {
    if (!map[ev.colKey]) map[ev.colKey] = []
    map[ev.colKey].push(ev)
  }
  return map
})

function handleClick(ev){ emits('event-click', ev) }

function onColBlankClick(e, col) {
  const rect = e.currentTarget.getBoundingClientRect()
  const y = e.clientY - rect.top // 相对容器顶部的像素
  const minute = Math.round(y / props.pxPerMin) // 从 dayStart 起的分钟数（取整）
  emits('blank-click', { colKey: col.key, minute })
}
</script>

<style scoped>
.grid-wrap { position: relative; display:flex; flex-direction: column; border:1px solid #eee; border-radius:8px; overflow:hidden; }

.header { display:grid; align-items:stretch; border-bottom:1px solid #eee; background:#fafafa; }
.header-cell { padding:8px; font-weight:600; border-right:1px solid #eee; }
.header-cell:last-child { border-right:0; }
.time-col { width:200px; }

.body { display:flex; }
.time-rail { position:relative; width:200px; background:#fff; }
.tick { position:absolute; left:0; height:1px; width:100%; }
.tick-label { position:absolute; left:8px; top:-8px; font-size:12px; color:#888; background:#fff; padding:0 4px; }
.tick-line { position:absolute; left:0; right:0; top:0; height:1px; background:#eee; }

.cols { display:grid; flex:1; }
.col-cell { position:relative; border-left:1px solid #f0f0f0; background:#fff; }
.events { position:relative; } /* 绝对定位事件块的承载容器 */

.empty { position:absolute; left:0; right:0; bottom:12px; text-align:center; color:#888; font-size:12px; pointer-events:none; }
</style>
