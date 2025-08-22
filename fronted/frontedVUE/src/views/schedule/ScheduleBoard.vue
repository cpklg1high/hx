<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="state.termId" placeholder="选择学期/季度" style="width:220px" @change="reloadRangeAndFetch">
        <el-option v-for="t in terms" :key="t.id" :label="t.name + `（${t.start_date}~${t.end_date}）`" :value="t.id" />
      </el-select>

      <el-segmented v-model="state.view" :options="[{label:'周',value:'week'},{label:'日',value:'day'}]" class="ml" @change="refreshCalendar" />
      <el-segmented v-model="state.tab" :options="[{label:'初中(含小学)',value:'junior'},{label:'高中',value:'senior'}]" class="ml" @change="fetchLessons" />

      <el-select v-model="filters.teacherIds" multiple collapse-tags placeholder="老师" style="width:220px" class="ml" @change="fetchLessons">
        <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-select v-model="filters.subjectIds" multiple collapse-tags placeholder="科目" style="width:180px" class="ml" @change="fetchLessons">
        <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-select v-model="filters.gradeIds" multiple collapse-tags placeholder="年级(可多选)" style="width:220px" class="ml" @change="fetchLessons">
        <el-option v-for="g in gradeOptionsByTab" :key="g.value" :label="g.label" :value="g.value" />
      </el-select>

      <div class="flex-1" />
      <el-button @click="gotoPrevWeek">上一周</el-button>
      <el-button @click="gotoThisWeek">本周</el-button>
      <el-button @click="gotoNextWeek">下一周</el-button>
      <el-button type="primary" @click="openCreateDialog()">新建班级</el-button>
    </div>

    <div ref="calEl" class="calendar"></div>

    <CreateClassDialog v-model="dlg.create" :term-id="state.termId" :subjects="subjects" :rooms="rooms" :teachers="teachers" @success="onCreatedClass" />
    <LessonDrawer v-model="dlg.lesson" :lesson="currentLesson" @changed="fetchLessons" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import Calendar from '@toast-ui/calendar'
import '@toast-ui/calendar/dist/toastui-calendar.min.css'

import { listTerms, listTeachers, listSubjects, listRooms, listLessons } from '../../api/schedule'
import { getGrades } from '../../api/dicts'
import CreateClassDialog from './CreateClassDialog.vue'
import LessonDrawer from './LessonDrawer.vue'
import { ElMessage } from 'element-plus'

const calEl = ref(null)
let cal = null

const terms = ref([])
const teachers = ref([])
const subjects = ref([])
const rooms = ref([])
const grades = ref([])

const state = reactive({
  termId: undefined,
  view: 'week',   // 'week' | 'day'
  tab: 'junior',  // 'junior' | 'senior'
  anchor : new Date(),
  range: { from:'', to:'' },   // 当前视图的日期范围
})
const filters = reactive({ gradeIds: [], teacherIds: [], subjectIds: [] })

const gradeOptionsByTab = computed(() => {
  const juniorIds = new Set([1,2,3,4,5,6,7,8,9])   // 小学+初中
  const seniorIds = new Set([10,11,12])           // 高中
  const list = grades.value.map(g => ({ label: g.name, value: g.id }))
  return list.filter(i => (state.tab === 'junior' ? juniorIds.has(i.value) : seniorIds.has(i.value)))
})

function computeRange() {
  const now = new Date(state.anchor)
  if (state.view === 'day') {
    const ymd = now.toISOString().slice(0,10)
    state.range = { from: ymd, to: ymd }
  } else {
    const d = new Date(now)
    const dow = (d.getDay() + 6) % 7
    const mon = new Date(d); mon.setDate(d.getDate() - dow)
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6)
    state.range = { from: mon.toISOString().slice(0,10), to: sun.toISOString().slice(0,10) }
  }
}

function gotoThisWeek(){
  state.anchor = new Date()
  cal && cal.setDate(state.anchor)   // 同步日历视图
  computeRange(); fetchLessons()
}
function gotoPrevWeek(){
  const d = new Date(state.anchor); d.setDate(d.getDate() - 7)
  state.anchor = d; cal && cal.setDate(d)
  computeRange(); fetchLessons()
}
function gotoNextWeek(){
  const d = new Date(state.anchor); d.setDate(d.getDate() + 7)
  state.anchor = d; cal && cal.setDate(d)
  computeRange(); fetchLessons()
}


async function initDicts() {
  const [t, te, s, r, g] = await Promise.all([ listTerms(), listTeachers(), listSubjects(), listRooms(), getGrades() ])
  terms.value = t.data.data || []
  teachers.value = te.data.data || []
  subjects.value = s.data.data || []
  rooms.value = r.data.data || []
  grades.value = g.data.data || []
  if (!state.termId && terms.value.length) state.termId = terms.value[0].id
}

function buildEvent(l) {
  return {
    id: String(l.id),
    calendarId: 'default',
    title: `${l.subject}-${l.course_mode}｜${l.teacher}${l.room ? '｜'+l.room : ''}｜${l.enrolled}${l.capacity?'/'+l.capacity:''}`,
    start: `${l.date}T${l.start_time}`,
    end: `${l.date}T${l.end_time}`,
    category: 'time',
    raw: l
  }
}

async function fetchLessons() {
  if (!state.termId) return
  const params = { term_id: state.termId, date_from: state.range.from, date_to: state.range.to, view: 'grade' }
  if (filters.teacherIds.length) params.teachers = filters.teacherIds
  if (filters.subjectIds.length) params.subjects = filters.subjectIds
  if (filters.gradeIds.length) params.grades = filters.gradeIds
  const { data } = await listLessons(params)
  const arr = data.data || []
  const juniorSet = new Set([1,2,3,4,5,6,7,8,9])
  const seniorSet = new Set([10,11,12])
  const filtered = arr.filter(x => state.tab === 'junior' ? juniorSet.has(x.grade) : seniorSet.has(x.grade))
  cal.clear()
  cal.createEvents(filtered.map(buildEvent))
}

function refreshCalendar() {
  if (!cal) return
  cal.changeView(state.view === 'day' ? 'day' : 'week', true)
  computeRange()
  fetchLessons()
}
function reloadRangeAndFetch(){ computeRange(); fetchLessons() }

const dlg = reactive({ create:false, lesson:false })
const currentLesson = ref(null)
function onSelectDateTime(){ openCreateDialog() }
function onClickEvent(ev){ currentLesson.value = ev.event.raw; dlg.lesson = true }
function openCreateDialog(){ if(!state.termId) return ElMessage.warning('请先选择学期/季度'); dlg.create = true }
function onCreatedClass(){ dlg.create=false; fetchLessons() }

onMounted(async () => {
  await initDicts()
  computeRange()

  cal = new Calendar(calEl.value, {
    defaultView: state.view,    // 'week' | 'day'
    usageStatistics: false,

    // —— 周视图设置 ——（这里才是 v2 接受 task/eventView 的地方）
    week: {
      startDayOfWeek: 1,
      workweek: false,
      hourStart: 7,
      hourEnd: 22,
      taskView: false,         // ❌ 隐藏 milestone / task
      eventView: ['time'],     // ❌ 隐藏 allday，只显示 time 区域
    },

    // —— 日视图也要同步配置，否则切到 day 还是会出现三行 —— 
    day: {
      hourStart: 7,
      hourEnd: 22,
      taskView: false,
      eventView: ['time'],
    },

    template: {
      // 事件卡片文案
      time(event) {
        const r = event.raw || {}
        const room = r.room ? `｜${r.room}` : ''
        const cap  = r.capacity ? `/${r.capacity}` : ''
        return `${r.subject}｜${r.course_mode}｜${r.teacher}${room}｜${r.enrolled}${cap}`
      },
    },
  })

  cal.on('selectDateTime', onSelectDateTime)
  cal.on('clickEvent', onClickEvent)
  fetchLessons()
})

onBeforeUnmount(() => { if (cal) { cal.destroy(); cal = null } })
watch(() => state.view, refreshCalendar)

</script>

<style scoped>
.page { padding: 10px; display:flex; flex-direction: column; height: calc(100vh - 100px); }
.toolbar { display:flex; align-items:center; gap:8px; margin-bottom: 10px; }
.flex-1 { flex: 1; }
.calendar { flex: 1; min-height: 520px; border: 1px solid #eee; border-radius: 8px; overflow: hidden; }
.ml { margin-left: 8px; }
</style>
