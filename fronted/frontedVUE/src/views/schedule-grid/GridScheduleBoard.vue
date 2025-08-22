<template>
  <div class="page">
    <!-- 顶部筛选 -->
    <div class="toolbar">
      <el-select v-model="state.termId" placeholder="选择学期/季度" style="width:240px" @change="reloadRangeAndFetch">
        <el-option v-for="t in terms" :key="t.id" :label="t.name + `（${t.start_date}~${t.end_date}）`" :value="t.id" />
      </el-select>

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
    </div>

    <!-- Grid 画布 -->
    <GridCanvas
      :range="state.range"
      :columns="columns"
      :events="layoutedEvents"
      :px-per-min="cfg.pxPerMin"
      :day-start="cfg.dayStart"
      :day-end="cfg.dayEnd"
      @event-click="onEventClick"
    />

    <!-- 课次抽屉（沿用你已有组件） -->
    <LessonDrawer v-model="dlg.lesson" :lesson="currentLesson" @changed="fetchLessons" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

import { listTerms, listTeachers, listSubjects, listLessons } from '../../api/schedule'
import { getGrades } from '../../api/dicts'

import GridCanvas from './GridCanvas.vue'
import LessonDrawer from '../schedule/LessonDrawer.vue'

import { useGridSchedule } from './useGridSchedule'
import { layoutByColumns } from './layout'

// 基础字典
const terms = ref([]); const teachers = ref([]); const subjects = ref([]); const grades = ref([])

// 参数与状态
const state = reactive({
  termId: undefined,
  tab: 'junior',              // 'junior'（含小学） | 'senior'
  anchor: new Date(),         // 锚定日期
  range: { from: '', to: '' } // 本周 Mon~Sun
})
const filters = reactive({ gradeIds: [], teacherIds: [], subjectIds: [] })

// UI 配置：时间轴范围与缩放
const cfg = reactive({
  dayStart: 7 * 60,     // 07:00 -> 分钟
  dayEnd: 22 * 60,      // 22:00 -> 分钟
  pxPerMin: 1.5         // 1 分钟对应像素（100 分钟≈150px）
})

// 年级选项（注意：如你的 GRADE_CHOICES ID 与此不同，请告诉我我会同步调整）
const gradeOptionsByTab = computed(() => {
  const juniorIds = new Set([1,2,3,4,5,6,7,8,9]) // 小学+初中
  const seniorIds = new Set([10,11,12])         // 高中
  const list = grades.value.map(g => ({ label: g.name, value: g.id }))
  return list.filter(i => (state.tab === 'junior' ? juniorIds.has(i.value) : seniorIds.has(i.value)))
})

// 计算当前周范围
function computeRange() {
  const d = new Date(state.anchor)
  const dow = (d.getDay() + 6) % 7 // 周一=0
  const mon = new Date(d); mon.setDate(d.getDate() - dow)
  const sun = new Date(mon); sun.setDate(mon.getDate() + 6)
  state.range = { from: mon.toISOString().slice(0,10), to: sun.toISOString().slice(0,10) }
}

// 初始化字典
async function initDicts() {
  try {
    const [t, te, s, g] = await Promise.all([listTerms(), listTeachers(), listSubjects(), getGrades()])
    terms.value = t.data.data || []
    teachers.value = te.data.data || []
    subjects.value = s.data.data || []
    grades.value = g.data.data || []
    if (!state.termId && terms.value.length) state.termId = terms.value[0].id
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '加载字典失败')
  }
}

// —— 数据拉取与布局 —— //
const { normalizeLessons, buildGradeColumns } = useGridSchedule()
const rawEvents = ref([])        // 原始 lesson 列表（规范化）
const columns = ref([])          // 列（年级）
const layoutedEvents = ref([])   // 已布局的事件（含像素位置）

async function fetchLessons() {
  if (!state.termId) return
  const params = {
    term_id: state.termId,
    date_from: state.range.from,
    date_to: state.range.to,
    view: 'grade'
  }
  if (filters.teacherIds.length) params.teachers = filters.teacherIds
  if (filters.subjectIds.length) params.subjects = filters.subjectIds
  if (filters.gradeIds.length)   params.grades   = filters.gradeIds

  try{
    const { data } = await listLessons(params)
    const arr = data.data || []
    // Tab 过滤：初中(含小学)/高中
    const juniorSet = new Set([1,2,3,4,5,6,7,8,9])
    const seniorSet = new Set([10,11,12])
    const filtered = arr.filter(x => state.tab === 'junior' ? juniorSet.has(x.grade) : seniorSet.has(x.grade))
    // 规范化
    rawEvents.value = normalizeLessons(filtered, cfg.dayStart)
    // 构建列（年级）
    columns.value = buildGradeColumns(filtered, grades.value)
    // 布局（按列做并发分道）
    layoutedEvents.value = layoutByColumns(rawEvents.value, columns.value, cfg)
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '加载课表失败')
  }
}

function reloadRangeAndFetch(){ computeRange(); fetchLessons() }
function gotoThisWeek(){ state.anchor = new Date(); reloadRangeAndFetch() }
function gotoPrevWeek(){ const d=new Date(state.anchor); d.setDate(d.getDate()-7); state.anchor = d; reloadRangeAndFetch() }
function gotoNextWeek(){ const d=new Date(state.anchor); d.setDate(d.getDate()+7); state.anchor = d; reloadRangeAndFetch() }

// 事件点击 -> 打开抽屉
const dlg = reactive({ lesson: false })
const currentLesson = ref(null)
function onEventClick(evRaw) {
  currentLesson.value = evRaw
  dlg.lesson = true
}

onMounted(async () => {
  await initDicts()
  computeRange()
  fetchLessons()
})
</script>

<style scoped>
.page { padding: 10px; display:flex; flex-direction: column; height: calc(100vh - 100px); }
.toolbar { display:flex; align-items:center; gap:8px; margin-bottom: 10px; }
.flex-1 { flex: 1; }
.ml { margin-left: 8px; }
</style>
