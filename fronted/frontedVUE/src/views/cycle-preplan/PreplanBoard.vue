<template>
  <div class="p-4">
    <!-- 过滤器：校区 / 年份 / 学期 / 周期（草稿/已发布） -->
    <el-card shadow="never">
      <CycleFilters @change="onFiltersChange" />
    </el-card>

    <div class="toolbar mt-3">
      <div class="left-tools">
        <el-segmented v-model="state.viewMode" :options="viewOptions" />
        <el-button :loading="state.boardLoading" @click="refreshBoard">刷新</el-button>
      </div>

      <div class="right-tools">
        <!-- 选择班级，用于打开名册面板（数据来自后端 listClassGroups，仅按 term 过滤，不在前端拼装） -->
        <el-select v-model="state.selectedClassGroupId" placeholder="选择班级后管理名册" filterable style="width: 280px">
          <el-option
            v-for="cg in state.classGroups"
            :key="cg.id"
            :label="formatCG(cg)"
            :value="cg.id"
          />
        </el-select>
        <el-segmented v-model="displayMode" :options="[
            {label: '预排网格', value: 'grid'},
            {label: '已有课次', value: 'board'}
            ]" />
        <el-button
          type="primary"
          plain
          :disabled="!state.cycleId || !state.selectedClassGroupId"
          @click="rosterOpen = true"
        >管理名册</el-button>

        <el-divider direction="vertical" />

        <el-button
          type="success"
          :disabled="!state.cycleId"
          @click="openPublish"
        >发布（映射到具体日期）</el-button>
      </div>
    </div>

    <!-- 看板统计（来自后端字段，前端不算） -->
    <el-alert
      v-if="state.board && state.board.dates"
      type="info"
      :closable="false"
      class="mb-2"
      :title="`区间：${state.board.dates[0]} ~ ${state.board.dates[state.board.dates.length-1]} | 模式：${state.board.pattern} | 休息日：${state.board.rest_weekday}`"
    />

    <!-- 空态 -->
    <el-empty
      v-if="!state.cycleId || state.yearDisplay === '无年份'"
      description="请选择一个有效的周期（校区/年份/学期）后查看预排看板"
      class="mt-4"
    />

    <!-- 看板主体：两种视图二选一（仅展示，不做合并/重算） -->
    <template v-if="displayMode==='grid'">
    <PreplanGrid
      :board="state.board"
      @create-at="onCreateAt"
    />

    <CreateClassDialog
    v-model="createDlg.visible"
    :term-id="state.cycle?.term"
    :default-teacher-id="createDlg.teacherId"
    :default-weekday="createDlg.weekday"
    :default-start="createDlg.start"
    :default-end="createDlg.end"
    @created="handleCreated"
    />
    </template>
    <div v-else>
      <TeacherBoard
        v-if="state.viewMode==='teacher'"
        :board="state.board"
        :loading="state.boardLoading"
        :error="state.boardError"
        @open-lesson="handleOpenLesson"
      />
      <SubjectBoard
        v-else
        :board="state.board"
        :loading="state.boardLoading"
        :error="state.boardError"
        @open-lesson="handleOpenLesson"
      />
    </div>

    <!-- 抽屉：课次详情（严格复用你现有 LessonDrawer；内部会用 getAttendance） -->
    <LessonDrawer
      v-model="state.drawerVisible"
      :lesson="state.drawerLesson"
      @changed="onLessonChanged"
    />

    <!-- 抽屉：名册（仅编辑名册，不出现签到按钮） -->
    <RosterPanel
      v-model="rosterOpen"
      :cycle-id="state.cycleId"
      :class-groups="asRosterPanelOptions"
      mode="roster-only"
      @changed="refreshBoard"
    />

    <!-- 发布对话框：只收集“weekday → 日期数组”及 scope，原样提交后端 -->
    <el-dialog v-model="publishOpen" title="发布周期（将预排映射到具体日期）" width="640px" destroy-on-close>
      <el-form label-width="120px">
        <el-form-item label="发布范围">
          <el-radio-group v-model="publishForm.scope">
            <el-radio label="future_only">仅今天之后</el-radio>
            <el-radio label="include_today">包含今天</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="模式">
          <el-segmented v-model="publishForm.mode" :options="[{label:'按参与者', value:'participants'}]" />
        </el-form-item>

        <el-divider>日期映射（按周几→自然日）</el-divider>

        <div class="weekday-mapper">
          <div v-for="w in weekdays" :key="w.value" class="weekday-row">
            <div class="w-label">{{ w.label }}</div>
            <el-date-picker
              v-model="publishForm.map[w.value]"
              type="dates"
              placeholder="选择要映射到的日期（可多选）"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              :disabled="!state.cycleId"
              :clearable="true"
              style="flex: 1"
            />
          </div>
        </div>

        <el-alert
          type="warning"
          :closable="false"
          class="mt-2"
          title="该映射仅作为“缓冲池→具体日期”的发布规则；后续打分/扣课仍以正式课表和签到为准。"
        />
      </el-form>

      <template #footer>
        <el-button @click="publishOpen=false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="doPublish">发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 你已有的通用组件（保持路径一致）
import CycleFilters from '../cycle-schedule/components/CycleFilters.vue'
import TeacherBoard from '../cycle-schedule/components/TeacherBoard.vue'
import SubjectBoard from '../cycle-schedule/components/SubjectBoard.vue'
import RosterPanel from '../cycle-schedule/components/RosterPanel.vue'
import LessonDrawer from '../schedule/LessonDrawer.vue'
import PreplanGrid from './components/PreplanGrid.vue'
import CreateClassDialog from './components/CreateClassDialog.vue'  


//  API：全部复用你已有模块
import { getCycle, getCycleBoard, publishCycle } from '../../api/cycle'
import { listClassGroups, listLessons } from '../../api/schedule'

const viewOptions = [
  { label: '按老师', value: 'teacher' },
  { label: '按学科', value: 'subject' },
]

const weekdays = [
  { label: '周一 (Mon)', value: 'Mon' },
  { label: '周二 (Tue)', value: 'Tue' },
  { label: '周三 (Wed)', value: 'Wed' },
  { label: '周四 (Thu)', value: 'Thu' },
  { label: '周五 (Fri)', value: 'Fri' },
  { label: '周六 (Sat)', value: 'Sat' },
  { label: '周日 (Sun)', value: 'Sun' },
]

// ------- 页面状态（仅保存接口返回，不做业务计算） -------
const state = reactive({
  // 由 CycleFilters 下发
  campusId: null,
  year: null,
  yearDisplay: null,
  termType: null,
  cycleId: null,
  cycle: null, // 包含 term/id 等

  // 看板
  board: null,
  boardLoading: false,
  boardError: null,

  // 视图
  viewMode: 'teacher',

  // 班级下拉（来自后端 listClassGroups?term_id）
  classGroups: [],
  selectedClassGroupId: null,

  // 抽屉
  drawerVisible: false,
  drawerLesson: null,
})

// 名册抽屉
const rosterOpen = ref(false)

// 发布对话框
const publishOpen = ref(false)
const publishing = ref(false)
const publishForm = reactive({
  scope: 'future_only',
  mode: 'participants',
  map: { Mon: [], Tue: [], Wed: [], Thu: [], Fri: [], Sat: [], Sun: [] },
  tracks: {}, // 暂不收集，后端支持时可扩展
})

// RosterPanel 需要 [{value,label}] 结构，不做额外拼装逻辑只做简单映射
const asRosterPanelOptions = computed(() => {
  return state.classGroups.map(cg => ({
    value: cg.id,
    label: formatCG(cg),
  }))
})

const createDlg = ref({
  visible: false,
  teacherId: null,
  weekday: null,
  start: null,
  end: null,
})

// 来自 <PreplanGrid @create-at="onCreateAt">
function onCreateAt(payload) {
  // payload: { teacherId, weekday, weekdayIdx, start, end, sourceDate, allDates }
  createDlg.value = {
    visible: true,
    teacherId: payload.teacherId || null,
    weekday: payload.weekday || null,
    start: payload.start || null,
    end: payload.end || null,
  }
}

// 创建成功后的回调（可刷新班级列表/提示）
function handleCreated() {
  // 这里不强制刷新看板，因为当前是“预排模板”；是否刷新由你决定
}

const displayMode = ref('grid')

function formatCG(cg) {
  const parts = []
  if (cg.name) parts.push(cg.name)
  if (cg.subject_name) parts.push(cg.subject_name)
  if (cg.course_mode) parts.push(cg.course_mode)
  return parts.join('｜') || `班级#${cg.id}`
}

// function onCreateAt(payload) {
//   // payload: { teacherId, weekday, weekdayIdx, start, end, sourceDate, allDates }
//   // 这里先做最小行为：打开“创建班级”弹窗时，把 sourceDate 作为默认日期传给后端表单；
//   // 后续你要让用户在弹窗里改成其它日期，可用 allDates 作为候选列表。
//   ElMessage.info(
//     `创建班级：老师#${payload.teacherId}｜${payload.weekday}｜${payload.start}-${payload.end}｜默认日期=${payload.sourceDate || '无'}`
//   )
//   // TODO（下一步）：弹出创建班级表单 → 调用后端 createClassGroup / 创建规则 / 预排记录
// }

// 接收筛选器回调
async function onFiltersChange(payload) {
  Object.assign(state, payload || {})
  // 拉取 cycle 详情（获取 term id 等元数据）
  if (state.cycleId) {
    try {
      const { data } = await getCycle(state.cycleId)
      state.cycle = data?.data || null
    } catch (e) {
      state.cycle = null
    }
  } else {
    state.cycle = null
  }

  // 同步刷新看板 & 班级列表
  await Promise.all([refreshBoard(), refreshClassGroups()])
}

// 看板：完全交给后端返回结构展示
async function refreshBoard() {
  if (!state.cycleId) {
    state.board = null
    state.boardError = null
    return
  }
  state.boardLoading = true
  state.boardError = null
  try {
    const { data } = await getCycleBoard(state.cycleId)
    state.board = data?.data || null
  } catch (err) {
    state.boardError = err
    state.board = null
    const status = err?.response?.status
    if (status === 403) {
      ElMessage.error('权限不足：仅主管可访问或发布后可见')
    } else {
      ElMessage.error(err?.response?.data?.message || '看板拉取失败')
    }
  } finally {
    state.boardLoading = false
  }
}

// 班级列表：只按 term 过滤，前端不做容量/冲突等逻辑
async function refreshClassGroups() {
  state.classGroups = []
  state.selectedClassGroupId = null
  const termId = state.cycle?.term
  if (!termId) return
  try {
    const { data } = await listClassGroups({ term_id: termId })
    // 直接使用后端返回，不重算
    state.classGroups = data?.data || []
  } catch (e) {
    state.classGroups = []
  }
}

// 点击课块：用已存在 /schedule/lessons?term_id&date=当天 拉取，再定位 id
async function handleOpenLesson({ lessonId, date }) {
  if (!state.cycle?.term) {
    ElMessage.warning('缺少 term 信息，无法拉取课次详情')
    return
  }
  try {
    const params = { term_id: state.cycle.term, date_from: date, date_to: date }
    const { data } = await listLessons(params)
    const rows = data?.data || []
    const found = rows.find(it => String(it.id) === String(lessonId))
    if (!found) {
      ElMessage.warning('未找到课次详情（可能已取消或不在当前学期）')
      return
    }
    state.drawerLesson = {
      id: found.id,
      class_group_id: found.class_group_id,
      title: found.title,
      date: found.date,
      start_time: found.start_time,
      end_time: found.end_time,
      duration: found.duration,
      status: found.status,
      teacher: found.teacher,
      room: found.room,
      capacity: found.capacity,
    }
    state.drawerVisible = true
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '加载课次详情失败')
  }
}
function onLessonChanged() {
  // 抽屉内提交后，刷新看板以同步状态
  refreshBoard()
}

// 打开发布对话框：初始化空映射（不做自动推断，遵守“前端不处理数据”）
function openPublish() {
  if (!state.cycleId) return
  publishOpen.value = true
  publishing.value = false
  publishForm.scope = 'future_only'
  publishForm.mode = 'participants'
  publishForm.map = { Mon: [], Tue: [], Wed: [], Thu: [], Fri: [], Sat: [], Sun: [] }
  publishForm.tracks = {}
}

// 执行发布：把映射原样送给后端，让后端做一切判断与落库
async function doPublish() {
  if (!state.cycleId) return
  // 最少要选一个 weekday 有日期，避免空发布
  const hasAny = Object.values(publishForm.map || {}).some(arr => Array.isArray(arr) && arr.length > 0)
  if (!hasAny) {
    ElMessage.warning('请至少为一个周几选择映射日期')
    return
  }

  publishing.value = true
  try {
    const payload = {
      scope: publishForm.scope,
      mode: publishForm.mode,
      map: publishForm.map,
      tracks: publishForm.tracks, // 暂空
      dry_run: false,
    }
    const { data } = await publishCycle(state.cycleId, payload)
    const add = data?.data?.added?.length || 0
    const remove = data?.data?.removed?.length || 0
    ElMessage.success(`发布完成：新增 ${add}，删除 ${remove}`)
    publishOpen.value = false
    refreshBoard()
  } catch (err) {
    const msg = err?.response?.data?.message || '发布失败'
    ElMessage.error(msg)
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
.mt-3 { margin-top: 12px; }
.mb-2 { margin-bottom: 8px; }
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.left-tools { display: flex; gap: 8px; align-items: center; }
.right-tools { display: flex; gap: 8px; align-items: center; }
.weekday-mapper { display: flex; flex-direction: column; gap: 10px; }
.weekday-row { display: flex; align-items: center; gap: 12px; }
.w-label { width: 110px; color: #606266; }
</style>
