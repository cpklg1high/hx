<template>
  <el-drawer
    v-model="visible"
    title="管理名册"
    size="560px"
    destroy-on-close
  >
    <div v-if="!cycleId" class="hint">请选择一个周期后再进行名册操作。</div>

    <el-form v-else label-width="88px" :model="form" :disabled="submitting">
      <el-form-item label="班级">
        <el-select
          v-model="form.classGroupId"
          placeholder="选择班级"
          filterable
          style="width:100%;"
        >
          <el-option
            v-for="opt in classGroups"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="类型">
        <el-radio-group v-model="form.type">
          <el-radio label="normal">正常</el-radio>
          <el-radio label="trial">试听</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="轨道" v-if="showTrack">
        <el-radio-group v-model="form.track">
          <el-radio label="A">A</el-radio>
          <el-radio label="B">B</el-radio>
        </el-radio-group>
        <div class="note">（暑/寒 AB 班可选；春/秋可不选）</div>
      </el-form-item>

      <el-form-item label="学生">
        <el-select
          v-model="form.studentIds"
          multiple
          filterable
          remote
          reserve-keyword
          clearable
          :remote-method="remoteSearch"
          :loading="searchLoading"
          placeholder="按姓名搜索（支持单字）"
          style="width:100%;"
        >
          <el-option
            v-for="s in options"
            :key="s.id"
            :label="s.label"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="submit"
      >
        添加到名册
      </el-button>
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { addCycleRoster } from '../../../api/cycle'
import { searchStudents } from '../../../api/schedule'

/** v-model */
const visible = defineModel({ type: Boolean, default: false })

/** props */
const props = defineProps({
  cycleId: { type: [String, Number], required: true },
  classGroups: { type: Array, default: () => [] }, // [{value,label}]
})

/** emits */
const emit = defineEmits(['changed'])

const submitting = ref(false)
const searchLoading = ref(false)
const options = ref([])

const form = ref({
  classGroupId: null,
  type: 'normal',   // normal | trial
  track: null,      // 'A' | 'B' | null
  studentIds: [],
})

/** 是否展示轨道选项：由你的业务控制。
 *  简单起见：当选择的班级名称里包含“暑 / 寒”字样时显示（你也可以根据周期类型在父组件传参控制）
 */
const showTrack = computed(() => {
  const opt = props.classGroups.find(x => x.value === form.value.classGroupId)
  if (!opt?.label) return false
  return /暑|寒/i.test(opt.label)
})

const canSubmit = computed(() =>
  !!props.cycleId &&
  !!form.value.classGroupId &&
  Array.isArray(form.value.studentIds) &&
  form.value.studentIds.length > 0
)

/** 远程搜索（仅姓名模糊） */
let seq = 0
async function remoteSearch(keyword) {
  const q = (keyword || '').trim()
  const mySeq = ++seq
  options.value = []
  if (!q) return
  searchLoading.value = true
  try {
    // 复用你现有的 /students 搜索接口；支持单字
    const { data } = await searchStudents({ q, page: 1, page_size: 20 })
    const list = data?.data?.results || data?.results || data?.data || []
    const arr = list.map(i => ({
      id: i.id,
      label: `${i.name}${i.grade_name ? '｜' + i.grade_name : ''}${i.school ? '｜' + i.school : ''}`,
    }))
    if (mySeq === seq) options.value = arr
  } catch (err) {
    if (mySeq === seq) options.value = []
    ElMessage.error(err?.response?.data?.message || '学生搜索失败')
  } finally {
    if (mySeq === seq) searchLoading.value = false
  }
}

watch(visible, (v) => {
  if (v) {
    // 打开时清空上次选择，避免误操作
    form.value = { classGroupId: null, type: 'normal', track: null, studentIds: [] }
    options.value = []
  }
})

/** 提交到后端 */
async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const payload = {
      students: form.value.studentIds.slice(),
      type: form.value.type,
      track: form.value.track || undefined,
    }
    await addCycleRoster(props.cycleId, form.value.classGroupId, payload)
    ElMessage.success('已添加到名册')
    emit('changed')
    // 可选：清空选中，方便连续添加
    form.value.studentIds = []
  } catch (err) {
    const msg = err?.response?.data?.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.hint { color:#909399; padding: 8px 0; }
.note { color:#909399; margin-left: 12px; }
</style>
