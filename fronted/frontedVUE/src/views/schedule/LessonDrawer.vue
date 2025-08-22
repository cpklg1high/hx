<template>
  <el-drawer v-model="visible" title="课次详情" size="600px">
    <template v-if="lesson">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="班级">{{ lesson.title }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ lesson.date }} {{ lesson.start_time }} ~ {{ lesson.end_time }}（{{ lesson.duration }} 分）</el-descriptions-item>
        <el-descriptions-item label="老师">{{ lesson.teacher }}</el-descriptions-item>
        <el-descriptions-item label="教室">{{ lesson.room || '—' }}</el-descriptions-item>
        <el-descriptions-item label="人数">{{ lesson.enrolled }}{{ lesson.capacity?`/${lesson.capacity}`:'' }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="lesson.status==='finished'?'success':(lesson.status==='canceled'?'info':'')">{{ lesson.status }}</el-tag></el-descriptions-item>
      </el-descriptions>

      <div class="actions">
        <el-button @click="loadAttendance" :loading="loading">刷新名单</el-button>
        <el-button type="warning" @click="oneKeyLeave" :disabled="!canLeave" :loading="loading">一键请假(课前)</el-button>
        <el-button type="primary" @click="oneKeySign" :disabled="!canSign" :loading="loading">一键签到(课后)</el-button>
        <el-popconfirm title="确认撤销本节已提交的签到？" @confirm="doRevert">
          <template #reference>
            <el-button type="danger" :disabled="!canRevert" :loading="loading">撤销消课(仅admin)</el-button>
          </template>
        </el-popconfirm>
      </div>

      <el-table :data="rows" border style="width:100%; margin-top:8px">
        <el-table-column prop="student_name" label="学生" width="140" />
        <el-table-column prop="preleave" label="已请假" width="90">
          <template #default="{row}"><el-tag v-if="row.preleave" type="warning">请假</el-tag><span v-else>—</span></template>
        </el-table-column>
        <el-table-column prop="status" label="签到状态" width="120">
          <template #default="{row}">
            <el-select v-model="row.status" placeholder="未提交" style="width:110px">
              <el-option label="签到" value="present" />
              <el-option label="请假" value="leave" />
              <el-option label="缺席" value="absent" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>

      <div class="submit-bar">
        <el-button type="primary" @click="submit" :disabled="!canSign" :loading="loading">提交签到</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { getAttendance, commitAttendance, setLeave, revertAttendance } from '../../api/schedule'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({ modelValue: Boolean, lesson: Object })
const emits = defineEmits(['update:modelValue','changed'])

const visible = computed({ get:()=>props.modelValue, set:(v)=>emits('update:modelValue', v) })

const rows = ref([])
const loading = ref(false)

const canLeave = computed(()=>{
  if (!props.lesson) return false
  const start = dayjs(`${props.lesson.date}T${props.lesson.start_time}`)
  return dayjs().isBefore(start) && props.lesson.status === 'scheduled'
})
const canSign = computed(()=>{
  if (!props.lesson) return false
  const end = dayjs(`${props.lesson.date}T${props.lesson.end_time}`)
  return dayjs().isAfter(end) && props.lesson.status !== 'finished'
})
const canRevert = computed(()=> props.lesson && props.lesson.status === 'finished')

watch(()=>props.lesson, (v)=>{ if (v) loadAttendance() })

async function loadAttendance(){
  if (!props.lesson) return
  loading.value = true
  try{
    const { data } = await getAttendance(props.lesson.id)
    const list = data.data?.students || []
    rows.value = list.map(i => ({ ...i, status: i.status || (i.preleave ? 'leave' : 'absent') }))
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '加载失败')
  }finally{
    loading.value = false
  }
}

async function oneKeyLeave(){
  if (!props.lesson) return
  try{ await ElMessageBox.confirm('将为本班“所有在读学生”设置请假，确定？','提示',{type:'warning'}) }catch{return}
  loading.value = true
  try{
    const { data } = await setLeave(props.lesson.id, { all:true, reason:'批量请假' })
    ElMessage.success(data.message || '已请假')
    await loadAttendance()
    emits('changed')
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '操作失败')
  }finally{ loading.value = false }
}

async function oneKeySign(){
  if (!props.lesson) return
  loading.value = true
  try{
    const { data } = await commitAttendance(props.lesson.id, { all_present: true })
    ElMessage.success(data.message || '已签到')
    emits('changed'); props.lesson.status = 'finished'
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '提交失败')
  }finally{ loading.value = false }
}

async function submit(){
  if (!props.lesson) return
  loading.value = true
  try{
    const items = rows.value.map(r => ({ student_id: r.student_id, status: r.status }))
    const { data } = await commitAttendance(props.lesson.id, { items })
    ElMessage.success(data.message || '已提交')
    emits('changed'); props.lesson.status = 'finished'
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '提交失败')
  }finally{ loading.value = false }
}

async function doRevert(){
  if (!props.lesson) return
  loading.value = true
  try{
    const { data } = await revertAttendance(props.lesson.id)
    ElMessage.success(data.message || '已撤销')
    emits('changed'); props.lesson.status = 'scheduled'
  }catch(err){
    ElMessage.error(err?.response?.data?.message || '撤销失败')
  }finally{ loading.value = false }
}
</script>

<style scoped>
.actions { display:flex; gap:8px; margin-top: 10px; flex-wrap: wrap; }
.submit-bar { display:flex; justify-content:flex-end; margin-top: 8px; }
</style>
