<!-- src/views/preplan/PreplanBoard.vue -->
<template>
  <div class="p-4">
    <!-- 筛选条 -->
    <el-card shadow="never" class="mb-3">
      <el-form :inline="true" label-width="80px">
        <el-form-item label="校区">
          <el-select v-model="state.campusId" placeholder="请选择校区" style="width: 220px" @change="onFilterChange">
            <el-option v-for="c in campuses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="年份">
          <el-input
            v-model="state.year"
            placeholder="例如 2025"
            style="width: 140px"
            @change="onFilterChange"
          />
        </el-form-item>

        <el-form-item label="学期">
          <el-select v-model="state.termType" placeholder="选择学期" style="width: 140px" @change="onFilterChange">
            <el-option label="春季" value="spring" />
            <el-option label="暑假" value="summer" />
            <el-option label="秋季" value="autumn" />
            <el-option label="寒假" value="winter" />
          </el-select>
        </el-form-item>

        <el-form-item label="老师">
          <el-select v-model="state.teacherId" filterable placeholder="选择老师" style="width: 220px" @change="onFilterChange">
            <el-option v-for="t in teachers" :key="t.id" :label="t.name || t.username || ('教师'+t.id)" :value="t.id" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button :loading="state.loading" type="primary" @click="refreshAll">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 占位提示 -->
    <el-alert
      v-if="!state.cycleId || !state.teacherId"
      type="info"
      show-icon
      :closable="false"
      class="mb-3"
      title="请选择『校区 / 年份 / 学期 / 老师』后查看预排模板。"
    />

    <!-- 预排网格 -->
    <el-card v-else shadow="never">
      <div class="grid-wrap">
        <!-- 表头 -->
        <div class="grid grid-header">
          <div class="cell head time-col">时间段</div>
          <div class="cell head" v-for="w in weekdays" :key="w.key">{{ w.label }}</div>
        </div>

        <!-- 每个时间段一行 -->
        <div class="grid grid-row" v-for="slot in timeSlots" :key="slot.key">
          <!-- 左侧时间列 -->
          <div class="cell time-col">{{ slot.label }}</div>

          <!-- 7天列 -->
          <div
            v-for="w in weekdays"
            :key="w.key + '-' + slot.key"
            class="cell"
          >
            <template v-if="cellItems(w.num, slot.start, slot.end).length">
              <!-- 已有预排：列出chips -->
              <div class="chip"
                   v-for="it in cellItems(w.num, slot.start, slot.end)"
                   :key="it.id"
                   :title="chipTitle(it)">
                {{ it.subject || '预排' }}｜{{ (it.start_time || '').slice(0,5) }}-{{ (it.end_time || '').slice(0,5) }}
              </div>
            </template>
            <template v-else>
              <!-- 空白：可点击新增 -->
              <el-button size="small" text @click="openCreate(w.num, slot)">
                + 预排
              </el-button>
            </template>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新建预排槽对话框 -->
    <el-dialog v-model="dlg.visible" title="创建预排槽" width="480px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="周期ID">
          <el-input v-model="state.cycleId" disabled />
        </el-form-item>
        <el-form-item label="老师ID">
          <el-input v-model="state.teacherId" disabled />
        </el-form-item>
        <el-form-item label="周几">
          <el-select v-model="dlg.form.weekday" disabled style="width: 160px">
            <el-option v-for="w in weekdays" :key="w.key" :label="w.label" :value="w.num" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-time-picker
            v-model="dlg.form.start_time"
            placeholder="开始"
            format="HH:mm"
            value-format="HH:mm"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-picker
            v-model="dlg.form.end_time"
            placeholder="结束"
            format="HH:mm"
            value-format="HH:mm"
            style="width: 160px"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dlg.visible=false">取消</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="savePreplan">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listCampuses, listCycles, listTeachers,
  listPreplanSlots, createPreplanSlot
} from '../../api/preplan'

// 固定 6 个时段（可在创建时微调）
const timeSlots = [
  { key: 'S1', label: '08:00-10:00', start: '08:00', end: '10:00' },
  { key: 'S2', label: '10:00-12:00', start: '10:00', end: '12:00' },
  { key: 'S3', label: '13:00-15:00', start: '13:00', end: '15:00' },
  { key: 'S4', label: '15:00-17:00', start: '15:00', end: '17:00' },
  { key: 'S5', label: '17:00-19:00', start: '17:00', end: '19:00' },
  { key: 'S6', label: '19:00-21:00', start: '19:00', end: '21:00' },
]

// 周一=1 ... 周日=7（与后端一致）
const weekdays = [
  { key: 'Mon',  label: '周一', num: 1 },
  { key: 'Tue',  label: '周二', num: 2 },
  { key: 'Wed',  label: '周三', num: 3 },
  { key: 'Thu',  label: '周四', num: 4 },
  { key: 'Fri',  label: '周五', num: 5 },
  { key: 'Sat',  label: '周六', num: 6 },
  { key: 'Sun',  label: '周日', num: 7 },
]

const state = reactive({
  campusId: null,
  year: '',
  termType: '',
  teacherId: null,

  cycleId: null,      // 通过 listCycles 择一（与过滤条件严格匹配）
  loading: false,

  slots: [],          // 预排槽列表（后端原样返回）
})

const campuses = ref([])
const teachers = ref([])
const cycles = ref([])

// 拉数据
async function bootstrap() {
  try {
    const [cs, ts] = await Promise.all([
      listCampuses({ active: true }),
      listTeachers()
    ])
    campuses.value = (cs?.data?.data) || []
    teachers.value = (ts?.data?.data) || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '初始化失败')
  }
}
bootstrap()

// 条件变化时：先找 cycleId，再拉槽位
async function onFilterChange() {
  state.cycleId = null
  state.slots = []
  if (!state.campusId || !state.year || !state.termType) return

  try {
    const { data } = await listCycles({
      campus: state.campusId,
      year: state.year,
      term_type: state.termType,
    })
    const arr = data?.data || []
    // 精确匹配一个周期，如果不唯一，取第一个（前端不做业务判断）
    state.cycleId = arr.length ? arr[0].id : null
    if (!state.cycleId) {
      ElMessage.warning('未找到匹配的周期')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '周期查询失败')
    state.cycleId = null
  }

  if (state.cycleId && state.teacherId) {
    await fetchSlots()
  }
}

async function refreshAll() {
  await onFilterChange()
}

async function fetchSlots() {
  if (!state.cycleId || !state.teacherId) return
  state.loading = true
  try {
    const { data } = await listPreplanSlots({
      cycle_id: state.cycleId,
      teacher_id: state.teacherId,
    })
    state.slots = data?.data || []
  } catch (e) {
    const status = e?.response?.status
    if (status === 403) {
      ElMessage.error('权限不足')
    } else {
      ElMessage.error(e?.response?.data?.message || '预排数据拉取失败')
    }
    state.slots = []
  } finally {
    state.loading = false
  }
}

// 根据 weekday + time 精确落格（同一格可能多条）
const cellItems = (weekdayNum, start, end) => {
  return (state.slots || []).filter(s =>
    Number(s.weekday) === Number(weekdayNum) &&
    String(s.start_time).slice(0,5) === start &&
    String(s.end_time).slice(0,5) === end
  )
}

const chipTitle = (it) => {
  const t = []
  if (it.subject) t.push(it.subject)
  if (it.class_group_name) t.push(it.class_group_name)
  t.push(`${(it.start_time||'').slice(0,5)}-${(it.end_time||'').slice(0,5)}`)
  return t.join('｜')
}

// —— 创建对话框 —— //
const dlg = reactive({
  visible: false,
  saving: false,
  form: {
    weekday: 1,
    start_time: '08:00',
    end_time: '10:00',
  }
})

function openCreate(weekdayNum, slot) {
  if (!state.cycleId || !state.teacherId) {
    ElMessage.warning('请先选择 校区/年份/学期/老师')
    return
  }
  dlg.form.weekday = weekdayNum
  dlg.form.start_time = slot.start
  dlg.form.end_time = slot.end
  dlg.visible = true
}

function toMinutes(hhmm) {
  const [h, m] = String(hhmm).split(':').map(x => parseInt(x || '0', 10))
  return (h * 60) + (m || 0)
}

async function savePreplan() {
  if (!dlg.form.start_time || !dlg.form.end_time) {
    ElMessage.warning('请选择时间')
    return
  }
  const dur = Math.max(0, toMinutes(dlg.form.end_time) - toMinutes(dlg.form.start_time))
  if (!dur) {
    ElMessage.warning('结束时间必须大于开始时间')
    return
  }
  dlg.saving = true
  try {
    await createPreplanSlot({
      cycle_id: state.cycleId,
      teacher_id: state.teacherId,
      weekday: dlg.form.weekday,           // 1~7
      start_time: dlg.form.start_time,     // "HH:mm"
      end_time: dlg.form.end_time,         // "HH:mm"
      duration_minutes: dur,
      // 如你后端支持 subject/grade/class_group_id，可在后续步骤加到表单
    })
    ElMessage.success('已创建')
    dlg.visible = false
    await fetchSlots()
  } catch (e) {
    const msg = e?.response?.data?.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    dlg.saving = false
  }
}
</script>

<style scoped>
.p-4 { padding: 16px; }
.mb-3 { margin-bottom: 12px; }

.grid-wrap { width: 100%; overflow-x: auto; }
.grid {
  display: grid;
  grid-template-columns: 140px repeat(7, minmax(160px, 1fr));
  border-left: 1px solid var(--el-border-color);
}
.grid-header .cell {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.grid-row .cell { min-height: 64px; }
.cell {
  border-right: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 8px;
  display: flex; align-items: flex-start; gap: 6px; flex-wrap: wrap;
}
.time-col {
  background: var(--el-fill-color-lighter);
  font-weight: 500;
}
.chip {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 10px;
  border: 1px dashed var(--el-border-color);
  cursor: default;
}
</style>
