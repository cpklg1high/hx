<template>
  <div class="page">
    <!-- 调试提示，可保留 -->
    <div class="tip">
      ✅ Grid · 视图：{{ state.viewMode }} · 周：{{ state.range.from }} ~ {{ state.range.to }}
    </div>

    <!-- 工具栏（稳定版：不用 segmented，日期用原生 input） -->
    <div class="toolbar">
      <!-- 学期 -->
      <el-select v-model="state.termId" placeholder="选择学期/季度" style="width:240px" @change="reloadRangeAndFetch">
        <el-option v-for="t in terms" :key="t.id" :label="t.name + `（${t.start_date}~${t.end_date}）`" :value="t.id" />
      </el-select>

      <!-- 视图切换 -->
      <el-radio-group v-model="state.viewMode" class="ml" @change="fetchLessons">
        <el-radio-button label="grade">按年级</el-radio-button>
        <el-radio-button label="teacher">按老师</el-radio-button>
      </el-radio-group>

      <!-- 初中/高中，仅年级视图显示 -->
      <el-radio-group v-if="state.viewMode==='grade'" v-model="state.tab" class="ml" @change="fetchLessons">
        <el-radio-button label="junior">初中(含小学)</el-radio-button>
        <el-radio-button label="senior">高中</el-radio-button>
      </el-radio-group>

      <div class="flex-1" />

      <!-- 日期/周控制（日期用原生 input，避免依赖差异） -->
      <label class="mr">日期：</label>
      <input type="date" v-model="anchorStr" @change="onAnchorChange" />

      <el-button class="ml" @click="gotoPrevWeek">上一周</el-button>
      <el-button @click="gotoThisWeek">本周</el-button>
      <el-button @click="gotoNextWeek">下一周</el-button>

      <el-button type="primary" class="ml" @click="openCreateDialog()">新建班级</el-button>
    </div>

    <div class="range-hint">当前周：{{ state.range.from }} ~ {{ state.range.to }}（落地日期：{{ activeDate }}）</div>

    <!-- 网格画布 -->
    <GridCanvas
      :range="state.range"
      :columns="columns"
      :events="layoutedEvents"
      :px-per-min="cfg.pxPerMin"
      :day-start="cfg.dayStart"
      :day-end="cfg.dayEnd"
      @event-click="onEventClick"
      @blank-click="onBlankClick"
    />

    <!-- 抽屉：查看/操作课程 -->
    <LessonDrawer v-model="dlg.lesson" :lesson="currentLesson" @changed="fetchLessons" />

    <!-- 新建班级弹窗（带预填） -->
    <CreateClassDialog
      v-model="dlg.create"
      :term-id="state.termId"
      :subjects="subjects"
      :rooms="[]"
      :teachers="teachers"
      :preset="preset"
      @success="onCreatedClass"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { listTerms, listTeachers, listSubjects, listLessons } from '../../api/schedule'
import { getGrades } from '../../api/dicts'

import GridCanvas from './GridCanvas.vue'
import LessonDrawer from '../schedule/LessonDrawer.vue'
import CreateClassDialog from '../schedule/CreateClassDialog.vue'

import { useGridSchedule } from './useGridSchedule'
import { layoutByColumns } from './layout'

const terms = ref([]); const teachers = ref([]); const subjects = ref([]); const grades = ref([])

const state = reactive({
  termId: undefined,
  viewMode: 'grade',   // 'grade' | 'teacher'
  tab: 'junior',
  anchor: new Date(),
  range: { from: '', to: '' }
})

const cfg = reactive({ dayStart: 7 * 60, dayEnd: 22 * 60, pxPerMin: 1.5 })

const anchorStr = computed({
  get(){ return state.anchor.toISOString().slice(0,10) },
  set(v){ state.anchor = new Date(v + 'T00:00:00') }
})
function onAnchorChange(){ computeRange(); fetchLessons() }

const activeDate = ref('')

function computeRange() {
  const d = new Date(state.anchor)
  const dow = (d.getDay() + 6) % 7
  const mon = new Date(d); mon.setDate(d.getDate() - dow)
  const sun = new Date(mon); sun.setDate(mon.getDate() + 6)
  const from = mon.toISOString().slice(0,10), to = sun.toISOString().slice(0,10)
  state.range = { from, to }
  const anchorStr_ = state.anchor.toISOString().slice(0,10)
  activeDate.value = (anchorStr_ >= from && anchorStr_ <= to) ? anchorStr_ : from
}

async function initDicts() {
  try {
    const [t, te, s, g] = await Promise.all([listTerms(), listTeachers(), listSubjects(), getGrades()])
    terms.value    = t.data.data || []
    teachers.value = te.data.data || []   // 0 也没关系
    subjects.value = s.data.data || []
    grades.value   = g.data.data || []
    if (!state.termId && terms.value.length) state.termId = terms.value[0].id
  } catch (err) {
    console.warn('dicts error', err?.response?.status, err?.response?.data || err)
  }
}

const { normalizeLessons, buildGradeColumns, buildTeacherColumns, attachColKey } = useGridSchedule()
const rawEvents = ref([]); const columns = ref([]); const layoutedEvents = ref([])

async function fetchLessons() {
  if (!state.termId) return
  const params = { term_id: state.termId, date_from: state.range.from, date_to: state.range.to, view: state.viewMode }
  try{
    const { data } = await listLessons(params)
    let arr = data.data || []

    if (state.viewMode==='grade') {
      const junior = new Set([1,2,3,4,5,6,7,8,9]); const senior = new Set([10,11,12])
      arr = arr.filter(x => state.tab === 'junior' ? junior.has(x.grade) : senior.has(x.grade))
    }

    const evs = normalizeLessons(arr, cfg.dayStart)

    columns.value = (state.viewMode==='grade')
      ? buildGradeColumns(arr, grades.value)
      : buildTeacherColumns(arr)

    const bound = attachColKey(evs, columns.value, state.viewMode)

    rawEvents.value = bound
    layoutedEvents.value = layoutByColumns(rawEvents.value, columns.value, cfg)
  }catch(err){
    console.warn('lessons error', err?.response?.status, err?.response?.data || err)
  }
}

function reloadRangeAndFetch(){ computeRange(); fetchLessons() }
function gotoThisWeek(){ state.anchor = new Date(); reloadRangeAndFetch() }
function gotoPrevWeek(){ const d=new Date(state.anchor); d.setDate(d.getDate()-7); state.anchor = d; reloadRangeAndFetch() }
function gotoNextWeek(){ const d=new Date(state.anchor); d.setDate(d.getDate()+7); state.anchor = d; reloadRangeAndFetch() }

/* 点击行为：打开抽屉/弹窗（已稳定） */
const dlg = reactive({ lesson: false, create: false })
const currentLesson = ref(null)
function onEventClick(evRaw) { currentLesson.value = evRaw; dlg.lesson = true }

const preset = ref(null)
function onBlankClick(payload){
  const absMin = cfg.dayStart + Math.max(0, Math.min(payload.minute, cfg.dayEnd - cfg.dayStart))
  const snap = Math.round(absMin / 10) * 10
  const hh = String(Math.floor(snap/60)).padStart(2,'0'), mm = String(snap % 60).padStart(2,'0')

  const base = { course_mode:'small_class', date: activeDate.value, start_time: `${hh}:${mm}:00`, duration_minutes: 100 }

  if (state.viewMode==='grade') {
    const gid = Number(String(payload.colKey).split(':')[1] || 0)
    preset.value = { ...base, grade: gid || undefined }
  } else {
    const tid = String(payload.colKey).split(':')[1]
    const teacherId = /^\d+$/.test(tid) ? Number(tid) : undefined
    preset.value = { ...base, teacher_main_id: teacherId }
  }
  dlg.create = true
}
function openCreateDialog(){
  preset.value = { course_mode:'small_class', date: activeDate.value, start_time:'18:00:00', duration_minutes:100 }
  dlg.create = true
}
function onCreatedClass(){ dlg.create=false; fetchLessons() }

onMounted(async () => {
  computeRange()
  await initDicts()
  await fetchLessons()
})
</script>

<style scoped>
.page { padding: 10px; display:flex; flex-direction: column; height: calc(100vh - 100px); }
.toolbar { display:flex; align-items:center; gap:8px; margin-bottom: 8px; flex-wrap: wrap; }
.flex-1 { flex: 1; }
.ml { margin-left: 8px; }
.mr { margin-right: 6px; }
.range-hint { color:#666; font-size:12px; margin-bottom: 8px; }
.tip { background:#f6ffed;border:1px solid #b7eb8f;color:#389e0d;padding:6px 10px;border-radius:6px;margin-bottom:8px; }
</style>
