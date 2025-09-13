<template>
  <el-drawer v-model="visible" title="课次详情" size="600px">
    <template v-if="lesson">
      <!-- 基本信息 -->
      <el-descriptions :column="1" border>
        <el-descriptions-item label="班级">{{ lesson.title }}</el-descriptions-item>
        <el-descriptions-item label="时间">
          {{ lesson.date }} {{ lesson.start_time }} ~ {{ lesson.end_time }}（{{ lesson.duration }} 分）
        </el-descriptions-item>
        <el-descriptions-item label="老师">{{ lesson.teacher }}</el-descriptions-item>
        <el-descriptions-item label="教室">{{ lesson.room || '—' }}</el-descriptions-item>
        <el-descriptions-item label="人数">
          {{ rows.length }}<template v-if="lesson.capacity">/{{ lesson.capacity }}</template>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="lesson.status==='finished'?'success':(lesson.status==='canceled'?'info':'')">
            {{ lesson.status }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 操作区 -->
      <div class="actions">
        <el-button @click="loadAttendance" :loading="loading">刷新名单</el-button>
        <el-button type="warning" @click="oneKeyLeave" :disabled="!canLeave" :loading="loading">一键请假(课前)</el-button>
        <el-button type="primary" @click="oneKeySign" :disabled="!canSign" :loading="loading">一键签到(课后)</el-button>
        <el-popconfirm title="确认撤销本节已提交的签到？" @confirm="doRevert">
          <template #reference>
            <el-button type="danger" :disabled="!canRevert" :loading="loading">撤销消课(仅admin)</el-button>
          </template>
        </el-popconfirm>

        <div class="flex-1" />
        <el-button type="primary" plain @click="openAddDlg">添加学生</el-button>
      </div>

      <!-- 名单表 -->
      <el-table :data="rows" border style="width:100%; margin-top:8px">
        <el-table-column prop="student_name" label="学生" min-width="160" />
        <el-table-column prop="preleave" label="已请假" width="90">
          <template #default="{row}">
            <el-tag v-if="row.preleave" type="warning">请假</el-tag><span v-else>—</span>
          </template>
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
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-popconfirm title="确认将该学生移出本班？" @confirm="removeOne(row.student_id)">
              <template #reference>
                <el-button type="danger" link :loading="removingId===row.student_id">移除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="submit-bar">
        <el-button type="primary" @click="submit" :disabled="!canSign" :loading="loading">提交签到</el-button>
      </div>

      <!-- 添加学生弹窗（远程搜索：仅按姓名；1个字即搜） -->
      <el-dialog v-model="dlgAdd" title="添加学生" width="520px" destroy-on-close>
        <el-form label-width="80px">
          <el-form-item label="搜索">
            <el-select
              v-model="addIds"
              multiple
              filterable
              remote
              clearable
              :remote-method="remoteSearch"
              :loading="searchLoading"
              :remote-show-suffix="true"
              :fit-input-width="true"
              placeholder="输入姓名关键字（支持1个字）"
              style="width: 100%;"
            >
              <el-option
                v-for="s in options"
                :key="s.id"
                :value="s.id"
                :label="`${s.school || '未知学校'}｜${s.grade_name || gradeMap[s.grade] || (s.grade ?? '未知年级')}｜${s.name}`"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dlgAdd=false">取消</el-button>
          <el-button type="primary" :loading="adding" @click="confirmAdd">确定添加</el-button>
        </template>
      </el-dialog>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import dayjs from 'dayjs'
import {
  getAttendance,
  commitAttendance,
  setLeave,
  revertAttendance,
  enrollStudentsToClassGroup,
  unenrollStudentsFromClassGroup,
  searchStudents
} from '../../api/schedule'
import { getGrades } from '../../api/dicts'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({ modelValue: Boolean, lesson: Object })
const emits = defineEmits(['update:modelValue','changed'])

const visible = computed({
  get:()=>props.modelValue,
  set:(v)=>emits('update:modelValue', v)
})

const rows = ref([])
const loading = ref(false)

/** ===== 添加/搜索/移除 相关状态（注意：options 只声明一次） ===== */
const dlgAdd = ref(false)
const addIds = ref([])
const options = ref([])            // [{id,name,grade,grade_name,school}]
const searchLoading = ref(false)
const adding = ref(false)
const removingId = ref(null)
const gradeMap = ref({})           // 年级 id->name

/** ===== 远程搜索（立即触发，支持1个字；只按“姓名”匹配） ===== */
let querySeq = 0 // 竞态保护序号
async function remoteSearch(query) {
  const q = (query ?? '').trim()
  const mySeq = ++querySeq

  if (!q) {
    options.value = []
    return
  }

  searchLoading.value = true
  try {
    // 确保 API 把查询放在 params：/students?q=...
    const { data } = await searchStudents({ q, page: 1, page_size: 20 })

    // 兼容常见返回结构
    const list = data?.data?.results || data?.results || data?.data || []

    // 只保留“姓名包含关键字”的记录
    const filteredByName = list.filter(i => String(i.name || '').includes(q))

    const mapped = filteredByName.map(i => ({
      id: i.id,
      name: i.name,
      grade: i.grade ?? i.grade_id ?? null,
      grade_name: i.grade_name ?? i.grade__name ?? null,
      school: i.school ?? i.school_name ?? null,
    }))

    if (mySeq === querySeq) options.value = mapped
  } catch (err) {
    if (mySeq === querySeq) options.value = []
    ElMessage.error(err?.response?.data?.message || err?.message || '学生搜索失败')
  } finally {
    if (mySeq === querySeq) searchLoading.value = false
  }
}

/** ===== 生命周期 / 字典 ===== */
onMounted(async ()=>{
  try {
    const { data } = await getGrades()
    const arr = data?.data || []
    const m = {}
    arr.forEach(g => { m[g.id] = g.name })
    gradeMap.value = m
  } catch (e) {
    // 字典失败不阻塞主流程
  }
})

/** ===== 课前/课后控制 ===== */
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

/** ===== 名单加载/提交/撤销 ===== */
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
  try{
    await ElMessageBox.confirm('将为本班“所有在读学生”设置请假，确定？','提示',{type:'warning'})
  }catch{return}
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

/** ===== 学生添加/移除 ===== */
function openAddDlg(){
  addIds.value = []
  options.value = []
  dlgAdd.value = true
}

async function confirmAdd(){
  if(!props.lesson?.class_group_id) return ElMessage.warning('缺少 class_group_id')
  if(!addIds.value.length)          return ElMessage.warning('请选择学生')

  const selected = options.value.filter(o => addIds.value.includes(o.id))
  const fmt = (o)=> `${o.school || '未知学校'}｜${o.grade_name || gradeMap.value[o.grade] || (o.grade ?? '未知年级')}｜${o.name}`
  const msg = (selected.length === 1)
    ? `你确定将「${fmt(selected[0])}」添加到该课程么？`
    : `你确定将「${fmt(selected[0])}」等${selected.length}人添加到该课程么？`
  try { await ElMessageBox.confirm(msg, '确认添加', { type: 'warning' }) } catch { return }

  adding.value = true
  try{
    await enrollStudentsToClassGroup(props.lesson.class_group_id, addIds.value)
    ElMessage.success('添加成功')
    dlgAdd.value = false
    await loadAttendance()
    emits('changed')
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '添加失败')
  } finally {
    adding.value = false
  }
}

async function removeOne(studentId){
  if(!props.lesson?.class_group_id) return ElMessage.warning('缺少 class_group_id')
  removingId.value = studentId
  try{
    await unenrollStudentsFromClassGroup(props.lesson.class_group_id, [studentId])
    ElMessage.success('已移除')
    await loadAttendance()
    emits('changed')
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '移除失败')
  } finally {
    removingId.value = null
  }
}
</script>

<style scoped>
.actions { display:flex; gap:8px; margin-top: 10px; flex-wrap: wrap; align-items:center; }
.flex-1 { flex: 1; }
.submit-bar { display:flex; justify-content:flex-end; margin-top: 8px; }
</style>
