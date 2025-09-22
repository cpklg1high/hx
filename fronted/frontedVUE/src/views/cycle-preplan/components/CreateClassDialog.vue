<template>
  <el-dialog
    v-model="visible"
    title="创建预排班级"
    width="560px"
    destroy-on-close
  >
    <el-form :model="form" ref="formRef" label-width="96px">
      <el-form-item label="学期(只读)">
        <el-tag type="info">{{ termId || '未选择' }}</el-tag>
      </el-form-item>

      <el-form-item label="老师">
        <el-select v-model="form.teacher_main" placeholder="选择老师" filterable style="width:100%">
          <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id"/>
        </el-select>
      </el-form-item>

      <el-form-item label="科目">
        <el-select v-model="form.subject" placeholder="选择科目" filterable style="width:100%">
          <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id"/>
        </el-select>
      </el-form-item>

      <el-form-item label="年级">
        <el-select v-model="form.grade" placeholder="选择年级" filterable style="width:100%">
          <el-option v-for="(name,id) in grades" :key="id" :label="name" :value="Number(id)"/>
        </el-select>
      </el-form-item>

      <el-form-item label="班型">
        <el-radio-group v-model="form.course_mode">
          <el-radio label="small_class">小班</el-radio>
          <el-radio label="one_to_two">一对二/三/四</el-radio>
          <el-radio label="one_to_one">一对一</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="默认教室">
        <el-select v-model="form.room_default" placeholder="可选" clearable filterable style="width:100%">
          <el-option v-for="r in rooms" :key="r.id" :label="r.name" :value="r.id"/>
        </el-select>
      </el-form-item>

      <el-form-item label="班级名称">
        <el-input v-model="form.name" placeholder="可选，如：初二数学1班"/>
      </el-form-item>

      <el-form-item label="容量(可选)">
        <el-input v-model.number="form.capacity" type="number" placeholder="留空按班型默认/不限"/>
      </el-form-item>

      <!-- 仅用于记录预排意图，不参与后端排课逻辑（后续步骤再做按周规则） -->
      <el-form-item label="预排信息">
        <el-input
          v-model="form.remark"
          type="textarea"
          :rows="2"
          placeholder="会写入班级remark，便于识别这批预排（可修改）"
        />
        <div class="hint">示例：周{{ weekdayLabel }} {{ slotLabel }}（点击格默认填入，可修改）</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible=false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listTeachers, listRooms, listSubjects, createClassGroup } from '../../../api/schedule'
import { getGrades } from '../../../api/dicts'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  termId: { type: Number, required: true },          // 来自当前 Cycle
  defaultTeacherId: { type: Number, default: null },  // 来自点击格
  defaultWeekday: { type: String, default: null },    // 'Mon'..'Sun'
  defaultStart: { type: String, default: null },      // '08:00'
  defaultEnd: { type: String, default: null },        // '10:00'
})
const emit = defineEmits(['update:modelValue','created'])

const visible = computed({
  get:()=>props.modelValue,
  set:v=>emit('update:modelValue', v)
})

const formRef = ref()
const submitting = ref(false)
const teachers = ref([])
const rooms = ref([])
const subjects = ref([])
const grades = ref({})

const weekdayLabel = computed(()=>{
  const map = {Mon:'一', Tue:'二', Wed:'三', Thu:'四', Fri:'五', Sat:'六', Sun:'日'}
  return map[props.defaultWeekday] || '一'
})
const slotLabel = computed(()=> props.defaultStart && props.defaultEnd ? `${props.defaultStart} - ${props.defaultEnd}` : '')

const form = ref({
  term: null,            // 必填
  teacher_main: null,    // 必填
  subject: null,         // 必填
  grade: null,           // 必填
  course_mode: 'small_class',
  room_default: null,    // 可空
  name: '',
  capacity: null,        // 可空
  remark: '',            // 记录“预排意图”，便于后续识别
})

async function loadOptions(){
  try{
    const [t, r, s, g] = await Promise.all([
      listTeachers(), listRooms(), listSubjects(), getGrades()
    ])
    teachers.value = t.data?.data || []
    rooms.value = r.data?.data || []
    subjects.value = s.data?.data || []
    const arr = g.data?.data || []
    const m = {}
    arr.forEach(x=>{ m[x.id]=x.name })
    grades.value = m
  }catch(e){
    ElMessage.error('下拉选项拉取失败')
  }
}

watch(()=>props.modelValue, (v)=>{
  if(v){
    // 预填：term + teacher + remark
    form.value.term = props.termId
    form.value.teacher_main = props.defaultTeacherId || null
    form.value.remark = `预排：周${weekdayLabel.value} ${slotLabel.value}`.trim()
  }
})

onMounted(loadOptions)

async function onSubmit(){
  if(!form.value.term || !form.value.teacher_main || !form.value.subject || !form.value.grade){
    ElMessage.warning('请完整选择学期、老师、科目、年级')
    return
  }
  submitting.value = true
  try{
    // 直接把表单丢给后端，不在前端做业务加工
    const payload = { ...form.value }
    const { data } = await createClassGroup(payload)
    ElMessage.success(data?.message || '创建成功')
    emit('created', data?.data || null)  // 通知父页面刷新或提示
    visible.value = false
  }catch(e){
    ElMessage.error(e?.response?.data?.message || '创建失败')
  }finally{
    submitting.value = false
  }
}
</script>

<style scoped>
.hint{ font-size:12px; color:#909399; margin-top:4px; }
</style>
