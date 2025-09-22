<!-- 直接覆盖整个文件 -->
<template>
  <div class="p-4">
    <el-card shadow="never">
      <CycleFilters @change="onFiltersChange" />
    </el-card>

    <div class="toolbar-right" style="margin: 8px 0;">
      <el-button
        type="primary"
        plain
        :disabled="!state.cycleId"
        @click="rosterOpen = true"
      >
        管理名册
      </el-button>

      <el-button
        type="success"
        plain
        :disabled="!state.cycleId"
        @click="publishOpen = true"
        style="margin-left: 8px;"
      >
        发布
      </el-button>
    </div>

    <el-card class="mt-3" shadow="never">
      <BoardToolbar
        :view-mode="state.viewMode"
        :search-text="state.searchText"
        :loading="state.boardLoading"
        @update:view-mode="v => state.viewMode = v"
        @update:search="v => state.searchText = v"
        @refresh="refreshBoard"
      />

      <div style="margin: 8px 0;">
        <BoardStats :board="state.board" />
      </div>

      <div v-if="!state.cycleId || state.yearDisplay === '无年份'" class="placeholder">
        请选择一个有效周期（校区 / 年份 / 学期）后查看看板。
      </div>

      <div v-else>
        <template v-if="state.viewMode === 'teacher'">
          <TeacherBoard
            :board="state.board"
            :loading="state.boardLoading"
            :error="state.boardError"
            :filter-text="state.searchText"
            @open-lesson="handleOpenLesson"
          />
        </template>

        <template v-else>
          <SubjectBoard
            :board="state.board"
            :loading="state.boardLoading"
            :error="state.boardError"
            :filter-text="state.searchText"
            @open-lesson="handleOpenLesson"
          />
        </template>
      </div>
    </el-card>

    <!-- ✅ 课次详情抽屉（沿用你原来的） -->
    <LessonDrawer
      v-model="state.drawerVisible"
      :lesson="state.drawerLesson"
      @changed="onLessonChanged"
    />

    <!-- ✅ 名册管理抽屉：放到最外层，两个视图都能用 -->
    <RosterPanel
      v-model="rosterOpen"
      :cycle-id="state.cycleId"
      :class-groups="classGroupOptions"
      @changed="handleRosterChanged"
    />

    <PublishPanel
      v-model="publishOpen"
      :cycle="state.cycle"
      :board="state.board"
    />
  </div>

  <div class="p-4">
    <el-card shadow="never">
      <CycleFilters @change="onFiltersChange" />
    </el-card>

    <div class="toolbar-right">
      <el-button
        type="primary"
        plain
        :disabled="!state.cycleId"
        @click="rosterOpen = true"
      >
        管理名册
      </el-button>
    </div>

    <el-card class="mt-3" shadow="never">
      <!-- ✅ 顶部页签：看板 / 总名册 -->
      <el-tabs v-model="viewTab" class="mb-2">
        <el-tab-pane label="看板" name="board" />
        <el-tab-pane label="总名册" name="roster" />
      </el-tabs>

      <!-- ============ 看板页签内容 ============ -->
      <div v-show="viewTab === 'board'">
        <BoardToolbar
          :view-mode="state.viewMode"
          :search-text="state.searchText"
          :loading="state.boardLoading"
          @update:view-mode="v => state.viewMode = v"
          @update:search="v => state.searchText = v"
          @refresh="refreshBoard"
        />

        <div style="margin: 8px 0;">
          <BoardStats :board="state.board" />
        </div>

        <div v-if="!state.cycleId || state.yearDisplay === '无年份'" class="placeholder">
          请选择一个<strong>有效周期</strong>（校区 / 年份 / 学期）后查看看板。
        </div>

        <div v-else>
          <template v-if="state.viewMode === 'teacher'">
            <TeacherBoard
              :board="state.board"
              :loading="state.boardLoading"
              :error="state.boardError"
              :filter-text="state.searchText"
              @open-lesson="handleOpenLesson"
            />
          </template>
          <template v-else>
            <SubjectBoard
              :board="state.board"
              :loading="state.boardLoading"
              :error="state.boardError"
              :filter-text="state.searchText"
              @open-lesson="handleOpenLesson"
            />
          </template>
        </div>
      </div>

      <!-- ============ 总名册页签内容 ============ -->
      <div v-show="viewTab === 'roster'">
        <MasterRosterTable :cycle-id="state.cycleId" />
      </div>

      <!-- 名册侧栏（你已有的） -->
      <RosterPanel
        v-model="rosterOpen"
        :cycle-id="state.cycleId"
        :class-groups="classGroupOptions"
        @changed="handleRosterChanged"
      />
    </el-card>

    <!-- 复用课次抽屉 -->
    <LessonDrawer
      v-model="state.drawerVisible"
      :lesson="state.drawerLesson"
      @changed="onLessonChanged"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

import CycleFilters from '../cycle-schedule/components/CycleFilters.vue'
import BoardToolbar from '../cycle-schedule/components/BoardToolbar.vue'   // ← 修正拼写
import TeacherBoard from '../cycle-schedule/components/TeacherBoard.vue'
import SubjectBoard from '../cycle-schedule/components/SubjectBoard.vue'
import BoardStats from '../cycle-schedule/components/BoardStats.vue'
import RosterPanel from '../cycle-schedule/components/RosterPanel.vue'
import LessonDrawer from '../schedule/LessonDrawer.vue'
import MasterRosterTable from '../cycle-schedule/components/MasterRosterTable.vue'
import PublishPanel from '../cycle-schedule/components/PublishPanel.vue'


import { getCycleBoard } from '../../api/cycle'
import { listLessons } from '../../api/schedule'

// —— 名册抽屉开关
const rosterOpen = ref(false)

// 新增：页签状态
const viewTab = ref('board')  // 'board' | 'roster'

const publishOpen = ref(false)

// —— 页面状态
const state = reactive({
  campusId: null,
  year: null,
  yearDisplay: null,     // 可能是“无年份”
  termType: null,
  cycleId: null,
  cycle: null,           // 包含 term 字段

  // 看板
  board: null,           // { dates:[], rows:[], pattern, rest_weekday }
  boardLoading: false,
  boardError: null,

  // 视图与搜索
  viewMode: 'teacher',
  searchText: '',

  // 抽屉
  drawerVisible: false,
  drawerLesson: null
})


// —— 从当前“未过滤的看板数据”提取班级列表（供名册抽屉选择）
const classGroupOptions = computed(() => {
  const b = state.board
  if (!b?.rows?.length || !b?.dates?.length) return []
  const map = new Map()
  for (const r of b.rows) {
    for (const d of b.dates) {
      for (const c of (r.days?.[d] || [])) {
        if (c?.class_group_id && !map.has(c.class_group_id)) {
          map.set(c.class_group_id, {
            value: c.class_group_id,
            label: `${c.class_group_name || '班级'}｜${c.subject || ''}｜${r.teacher_name || ''}`
          })
        }
      }
    }
  }
  return Array.from(map.values()).sort((a,b)=> String(a.label).localeCompare(String(b.label),'zh-Hans-CN'))
})

function onFiltersChange(payload) {
  Object.assign(state, payload || {})
  if (state.cycleId) {
    refreshBoard()
  } else {
    state.board = null
    state.boardError = null
  }
}

async function refreshBoard() {
  if (!state.cycleId) return
  state.boardLoading = true
  state.boardError = null
  try {
    const { data } = await getCycleBoard(state.cycleId)
    state.board = data?.data || null
  } catch (err) {
    const status = err?.response?.status
    if (status === 403) {
      ElMessage.error('权限不足：仅主管可访问或发布后可见')
    } else {
      ElMessage.error(err?.response?.data?.message || '看板拉取失败')
    }
    state.boardError = err
    state.board = null
  } finally {
    state.boardLoading = false
  }
}

// —— 点击课程块：复用 listLessons（按当天）→ 找到该课次对象 → 打开抽屉
async function handleOpenLesson({ lessonId, date }) {
  try {
    if (!state.cycle?.term) {
      ElMessage.warning('缺少 term 信息，无法拉取课次详情')
      return
    }
    const params = {
      term_id: state.cycle.term,
      date_from: date,
      date_to: date
    }
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
      capacity: found.capacity
    }
    state.drawerVisible = true
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '加载课次详情失败')
  }
}

function onLessonChanged() {
  // 课次在抽屉内被签到/撤销后，刷新看板联动
  refreshBoard()
}

function handleRosterChanged() {
  // 名册变更后（删除/后续的添加）可以选择刷新看板
  // refreshBoard()
}
</script>

<style scoped>
.mt-3 { margin-top: 12px; }
.placeholder { padding: 16px; color: #909399; }
.toolbar-right { display: flex; justify-content: flex-end; }
</style>
