<template>
  <el-dialog
    v-model="visible"
    :title="mode==='create'?'新增学生':'编辑学生'"
    width="720px"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" status-icon>
      <!-- 基本信息 -->
      <el-form-item label="学生姓名" prop="name">
        <el-input v-model="form.name" maxlength="50" />
      </el-form-item>

      <el-form-item label="年级" prop="grade_id">
        <el-select v-model="form.grade_id" placeholder="请选择年级" style="width: 220px">
          <el-option v-for="g in grades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
      </el-form-item>

      <!-- 学校（必填，远程搜索，按拼音排序由后端保证；仅显示汉字） -->
      <el-form-item label="学校" prop="school_id">
        <el-select
          v-model="form.school_id"
          filterable remote clearable reserve-keyword
          placeholder="请输入学校名称"
          :remote-method="onSearchSchool"
          :loading="schoolLoading"
          style="width: 420px">
          <el-option
            v-for="s in schoolList"
            :key="s.id"
            :label="s.name"
            :value="s.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="班主任(可选)">
        <el-select
          v-model="form.current_salesperson_id"
          filterable remote reserve-keyword
          placeholder="输入姓名搜索"
          :remote-method="onSearchSalesperson"
          :loading="spLoading" style="width: 260px">
          <el-option v-for="u in spList" :key="u.id" :label="u.name" :value="u.id" />
        </el-select>
      </el-form-item>

      <!-- 来访渠道 -->
      <el-form-item label="来访渠道" prop="visit_channel">
        <el-radio-group v-model="form.visit_channel">
          <el-radio label="referral">转介绍</el-radio>
          <el-radio label="walk_in">直访</el-radio>
          <el-radio label="other">其他方式</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="form.visit_channel==='referral'" label="推荐学员" prop="referral_student_id">
        <el-select v-model="form.referral_student_id"
          filterable remote reserve-keyword :remote-method="onSearchReferral"
          placeholder="搜索在读学员（姓名）如非在读状态无法添加" :loading="refLoading"
          style="width: 420px">
          <el-option
            v-for="s in referralList" :key="s.id" :label="formatReferral(s)" :value="s.id" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="form.visit_channel==='other'" label="其他方式说明" prop="visit_channel_other_text">
        <el-input v-model="form.visit_channel_other_text" maxlength="100" placeholder="例如：社区活动/地推/小红书…" />
      </el-form-item>

      <!-- 备注 -->
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="3" maxlength="500" show-word-limit />
      </el-form-item>

      <!-- 监护人子表 -->
      <div class="subsection">监护人</div>
      <el-form-item required>
        <el-table :data="guardians" border style="width: 100%">
          <el-table-column label="关系" width="120">
            <template #default="{ row }">
              <el-select v-model="row.relation_code" style="width: 100%">
                <el-option v-for="r in relations" :key="r.code" :label="r.label" :value="r.code" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="姓名" width="160">
            <template #default="{ row }">
              <el-input v-model="row.guardian_name" maxlength="50" />
            </template>
          </el-table-column>
          <el-table-column label="手机号" width="180">
            <template #default="{ row }">
              <el-input v-model="row.phone" maxlength="20" placeholder="11位手机号" />
            </template>
          </el-table-column>
          <el-table-column label="主联系人" width="110" align="center">
            <template #default="{ $index }">
              <el-radio v-model="primaryIndex" :label="$index"></el-radio>
            </template>
          </el-table-column>
          <el-table-column label="备注">
            <template #default="{ row }">
              <el-input v-model="row.remark" maxlength="200" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ $index }">
              <el-button text type="danger" @click="removeGuardian($index)" :disabled="guardians.length<=1">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="mt-2">
          <el-button text type="primary" @click="addGuardian">+ 新增联系人</el-button>
        </div>
      </el-form-item>

      <!-- 隐形规则校验位 -->
      <el-form-item prop="guardiansMeta" class="hidden-item">
        <span />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible=false">取消</el-button>
      <el-button type="primary" @click="onSubmit" :loading="saving">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getGrades, getRelations, getVisitChannels } from '../../api/dicts'
import { searchSalespersons } from '../../api/users'
import { searchReferralCandidates, createStudent, searchSchools } from '../../api/student'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'create' },
})
const emit = defineEmits(['update:modelValue','success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/** —— 统一的默认表单 —— */
const getDefaultForm = () => ({
  name: '',
  grade_id: undefined,
  school_id: undefined,
  current_salesperson_id: null,
  visit_channel: 'walk_in',
  referral_student_id: null,
  visit_channel_other_text: '',
  remark: '',
})
const formRef = ref()
const form = reactive(getDefaultForm())

/** —— 字典与下拉列表 —— */
const grades = ref([]), relations = ref([]), channels = ref([])
const schoolLoading = ref(false), schoolList = ref([])
const spLoading = ref(false), spList = ref([])
const refLoading = ref(false), referralList = ref([])

/** —— 监护人数据 —— */
const guardians = ref([{ relation_code: 'mother', guardian_name: '', phone: '', is_primary: true, remark: '' }])
const primaryIndex = ref(0)

/** —— 校验规则 —— */
const rules = {
  name: [{ required: true, message: '请输入学生姓名', trigger: 'blur' }],
  grade_id: [{ required: true, message: '请选择年级', trigger: 'change' }],
  school_id: [{ required: true, message: '请选择学校', trigger: 'change' }],
  visit_channel: [{ required: true, message: '请选择来访渠道', trigger: 'change' }],
  referral_student_id: [
    { validator: (_, v, cb) => (form.visit_channel==='referral' && !v) ? cb(new Error('请选择推荐学员')) : cb(), trigger: 'change' }
  ],
  visit_channel_other_text: [
    { validator: (_, v, cb) => (form.visit_channel==='other' && !v) ? cb(new Error('请填写其他方式说明')) : cb(), trigger: 'blur' }
  ],
  guardiansMeta: [
    { validator: (_, __, cb) => {
        if (guardians.value.length < 1) return cb(new Error('至少添加一位联系人'))
        if (primaryIndex.value == null || primaryIndex.value < 0 || primaryIndex.value >= guardians.value.length)
          return cb(new Error('必须选择一位主联系人'))
        for (const g of guardians.value) {
          if (!g.phone) return cb(new Error('联系人手机号必填'))
          if (!/^1\d{10}$/.test(g.phone)) return cb(new Error('手机号格式不正确'))
        }
        cb()
      }, trigger: 'change'
    }
  ],
}

/** —— 行为：新增/删除联系人 —— */
function addGuardian() {
  guardians.value.push({ relation_code: 'other', guardian_name: '', phone: '', is_primary: false, remark: '' })
}
function removeGuardian(idx) {
  guardians.value.splice(idx, 1)
  if (primaryIndex.value === idx) primaryIndex.value = 0
  if (primaryIndex.value > idx) primaryIndex.value -= 1
}

/** —— 远程搜索 —— */
function onSearchSalesperson(q) {
  spLoading.value = true
  searchSalespersons(q || '').then(({ data }) => {
    spList.value = data.data || []
  }).finally(() => spLoading.value = false)
}
function onSearchReferral(q) {
  refLoading.value = true
  searchReferralCandidates(q || '').then(({ data }) => {
    referralList.value = data.data || []
  }).finally(() => refLoading.value = false)
}
function onSearchSchool(q) {
  schoolLoading.value = true
  searchSchools(q || '').then(({ data }) => {
    schoolList.value = data.data || []
  }).finally(() => schoolLoading.value = false)
}
function formatReferral(s) {
  const pc = s.primary_contact
  const tail = pc ? `（${pc.relation_label} ${pc.phone_mask||''}）` : ''
  return `${s.name} / ${s.grade_label}${tail}`
}

/** —— 依赖字段联动 —— */
watch(() => form.visit_channel, (v) => {
  if (v !== 'referral') form.referral_student_id = null
  if (v !== 'other') form.visit_channel_other_text = ''
})

/** —— 重置方法（核心） —— */
function resetForm() {
  // 重置表单字段
  Object.assign(form, getDefaultForm())
  // 重置联系人
  guardians.value = [{ relation_code: 'mother', guardian_name: '', phone: '', is_primary: true, remark: '' }]
  primaryIndex.value = 0
  // 清空校验提示
  nextTick(() => formRef.value?.clearValidate?.())
}

/** —— 提交 —— */
const saving = ref(false)
async function onSubmit() {
  await formRef.value.validate()
  const gs = guardians.value.map((g, idx) => ({ ...g, is_primary: idx === primaryIndex.value }))
  const payload = { ...form, guardians: gs }
  saving.value = true
  try {
    const { data } = await createStudent(payload)
    if (data.code === 200) {
      ElMessage.success('保存成功')
      visible.value = false   // 触发 @closed → onClosed → resetForm()
      emit('success', data.data?.id)
    } else {
      throw new Error(data.message || '保存失败')
    }
  } catch (err) {
    const resp = err?.response?.data
    const msg = resp?.message || Object.values(resp || {})?.[0]?.[0] || err.message || '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

/** —— 打开/关闭时机的重置 —— */
function onOpen() {
  // 仅在“新增”模式时确保每次打开都是干净的
  if (props.mode === 'create') resetForm()
  // 打开时顺便拉一波远程下拉
  onSearchSalesperson('')
  onSearchReferral('')
  onSearchSchool('')
}
function onClosed() {
  // 关闭后再保险清空一次（避免残留）
  if (props.mode === 'create') resetForm()
}

/** —— 首次挂载：拉取字典 —— */
onMounted(async () => {
  const [g, r, c] = await Promise.all([getGrades(), getRelations(), getVisitChannels()])
  grades.value = g.data.data || []
  relations.value = r.data.data || []
  channels.value = c.data.data || []
})
</script>

<style scoped>
.subsection { margin: 8px 0; font-weight: 600; color: #333; }
.mt-2 { margin-top: 8px; }
.hidden-item :deep(.el-form-item__content) { display: none; }
</style>
