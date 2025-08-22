<template>
  <el-dialog
    v-model="visible"
    title="新建班级"
    width="720px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="学期">
        <el-input :value="termLabel" disabled />
      </el-form-item>

      <el-form-item label="班型">
        <el-select v-model="form.course_mode" style="width:220px" @change="onModeChange">
          <el-option label="一对一" value="one_to_one" />
          <el-option label="一对二(≤4人)" value="one_to_two" />
          <el-option label="小班" value="small_class" />
        </el-select>
      </el-form-item>

      <el-form-item label="年级">
        <el-select v-model="form.grade" style="width:220px" filterable>
          <el-option v-for="g in grades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="科目">
        <el-select v-model="form.subject_id" style="width:220px" filterable>
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="老师">
        <el-select v-model="form.teacher_main_id" style="width:220px" filterable>
          <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="教室">
        <el-select v-model="form.room_default_id" style="width:220px" clearable filterable>
          <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="form.course_mode==='one_to_two'" label="容量(≤4)">
        <el-input-number v-model="form.capacity" :min="1" :max="4" />
        <span class="hint">（1v2 默认 2，最多 4）</span>
      </el-form-item>

      <el-form-item label="班级名称">
        <el-input v-model="form.name" placeholder="可选：如 初二数学暑期班A" />
      </el-form-item>

      <el-divider>排课规则</el-divider>

      <el-radio-group v-model="form.rule_type">
        <el-radio label="weekly">每周循环</el-radio>
        <el-radio label="custom">自定义多段</el-radio>
      </el-radio-group>

      <!-- 每周循环 -->
      <template v-if="form.rule_type==='weekly'">
        <div class="row">
          <el-checkbox-group v-model="weekly.days">
            <el-checkbox :label="1">周一</el-checkbox>
            <el-checkbox :label="2">周二</el-checkbox>
            <el-checkbox :label="3">周三</el-checkbox>
            <el-checkbox :label="4">周四</el-checkbox>
            <el-checkbox :label="5">周五</el-checkbox>
            <el-checkbox :label="6">周六</el-checkbox>
            <el-checkbox :label="7">周日</el-checkbox>
          </el-checkbox-group>
        </div>
        <div class="row">
          <el-time-picker
            v-model="weekly.start_time"
            placeholder="开始时间"
            arrow-control
            value-format="HH:mm:ss"
          />
          <el-input-number v-model="weekly.duration_minutes" :min="30" :step="10" class="ml" />
          <span class="hint ml">分钟（小班建议 100）</span>
        </div>
      </template>

      <!-- 自定义多段 -->
      <template v-else>
        <div v-for="(e,i) in customs" :key="i" class="row">
          <el-date-picker
            v-model="e.date"
            type="date"
            placeholder="日期"
            value-format="YYYY-MM-DD"
          />
          <el-time-picker
            v-model="e.start_time"
            placeholder="开始时间"
            class="ml"
            arrow-control
            value-format="HH:mm:ss"
          />
          <el-input-number v-model="e.duration_minutes" :min="30" :step="10" class="ml" />
          <span class="hint ml">分钟</span>
          <el-button text type="danger" class="ml" @click="removeCustom(i)">删除</el-button>
        </div>
        <el-button class="mt" @click="addCustom">+ 增加一段</el-button>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="submit" :loading="loading">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createClassGroup } from '../../api/schedule'
import { getGrades } from '../../api/dicts'

/**
 * props 说明：
 * - termId: 学期ID（必需）
 * - subjects/rooms/teachers: 字典数组（父层传入即可）
 * - preset: 预填（可选）{ course_mode?, grade?, date?, start_time?, duration_minutes? }
 */
const props = defineProps({
  modelValue: Boolean,
  termId: Number,
  subjects: Array,
  rooms: Array,
  teachers: Array,
  preset: Object
})
const emits = defineEmits(['update:modelValue','success'])

const visible = computed({
  get:()=>props.modelValue,
  set:(v)=>emits('update:modelValue', v)
})

const termLabel = computed(()=> `ID: ${props.termId ?? '-'}`)

// 字典：年级（本组件内自取，以兼容父组件未传入）
const grades = ref([])
getGrades().then(({data}) => { grades.value = data?.data || [] })

// 表单
const form = reactive({
  course_mode: 'small_class',
  grade: undefined,
  subject_id: undefined,
  room_default_id: undefined,
  teacher_main_id: undefined,
  name: '',
  capacity: 2,          // 1v2 默认 2
  rule_type: 'weekly'   // weekly | custom
})
const weekly = reactive({ days:[2,4], start_time:'18:00:00', duration_minutes:100 })
const customs = ref([{ date:'', start_time:'18:00:00', duration_minutes:100 }])

function onModeChange(){
  // 切换班型时，给个合理的默认时长
  if (form.rule_type === 'weekly') {
    weekly.duration_minutes = (form.course_mode === 'small_class') ? 100 : 90
  } else if (customs.value.length) {
    customs.value[0].duration_minutes = (form.course_mode === 'small_class') ? 100 : 90
  }
}

watch(() => props.modelValue, (v) => {
  if (!v) return
  // 重置默认
  form.rule_type = 'weekly'
  weekly.days = [2,4]
  weekly.start_time = '18:00:00'
  weekly.duration_minutes = (form.course_mode==='small_class')?100:90
  customs.value = [{ date:'', start_time:'18:00:00', duration_minutes: (form.course_mode==='small_class')?100:90 }]

  // —— 应用预填（如果传入）——
  if (props.preset) {
    if (props.preset.course_mode) form.course_mode = props.preset.course_mode
    if (props.preset.grade) form.grade = props.preset.grade
    // 若带了日期/时间/时长，则切到自定义模式并套用
    const d  = props.preset.date || ''
    const st = props.preset.start_time || '18:00:00'
    const du = props.preset.duration_minutes ?? ((form.course_mode==='small_class')?100:90)
    if (d || st || du) {
      form.rule_type = 'custom'
      customs.value = [{ date: d, start_time: st, duration_minutes: du }]
    }
  }
})

function addCustom(){ customs.value.push({ date:'', start_time:'18:00:00', duration_minutes:100 }) }
function removeCustom(i){ customs.value.splice(i,1) }

const loading = ref(false)

async function submit(){
  // 基础校验（后端也会再校验）
  if (!props.termId) return ElMessage.warning('请先选择学期')
  if (!form.grade) return ElMessage.warning('请选择年级')
  if (!form.subject_id) return ElMessage.warning('请选择科目')
  if (!form.teacher_main_id) return ElMessage.warning('请选择老师')

  // 组装 payload
  const payload = {
    term_id: props.termId,
    course_mode: form.course_mode,
    grade: form.grade,
    subject_id: form.subject_id,
    room_default_id: form.room_default_id || null,
    teacher_main_id: form.teacher_main_id,
    name: form.name || '',
    rule_type: form.rule_type
  }
  if (form.course_mode === 'one_to_two') {
    payload.capacity = Math.max(1, Math.min(4, Number(form.capacity || 2)))
  }

  if (form.rule_type === 'weekly') {
    if (!weekly.days.length) return ElMessage.warning('请选择周几')
    payload.weekly = {
      days: weekly.days,
      start_time: weekly.start_time,            // 'HH:mm:ss'
      duration_minutes: Number(weekly.duration_minutes) || 100
    }
  } else {
    if (!customs.value.length) return ElMessage.warning('请至少添加一段')
    const cs = customs.value.map(e => ({
      date: e.date,                              // 'YYYY-MM-DD'
      start_time: e.start_time,                  // 'HH:mm:ss'
      duration_minutes: Number(e.duration_minutes) || 100
    }))
    // 简单校验：有日期与开始时间
    for (const c of cs) {
      if (!c.date || !c.start_time) return ElMessage.warning('请完善“日期/时间”')
    }
    payload.custom = cs
  }

  loading.value = true
  try{
    const { data } = await createClassGroup(payload)
    ElMessage.success(data?.message || '创建成功')
    emits('success')
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '创建失败')
  }finally{
    loading.value = false
  }
}

function close(){ emits('update:modelValue', false) }

// 供模板使用的只读字典
const subjects = computed(()=> props.subjects || [])
const rooms    = computed(()=> props.rooms || [])
const teachers = computed(()=> props.teachers || [])
</script>

<style scoped>
.row { display:flex; align-items:center; gap:8px; margin:6px 0; flex-wrap: wrap; }
.mt { margin-top: 8px; }
.ml { margin-left: 8px; }
.hint { color:#888; font-size:12px; }
</style>
