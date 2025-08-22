<template>
  <el-dialog
    v-model="visible"
    width="560px"
    :title="title"
    destroy-on-close
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      @keydown.enter.prevent="onSubmit"
    >
      <el-form-item label="学生">
        <el-input :model-value="student?.name || ''" disabled />
      </el-form-item>

      <el-form-item label="班型" prop="course_mode">
        <el-select v-model="form.course_mode" style="width: 220px" @change="onCourseModeChange">
          <el-option label="一对一（按小时）" value="one_to_one" />
          <el-option label="一对二（按小时）" value="one_to_two" />
          <el-option label="小班（按节）" value="small_class" />
        </el-select>
      </el-form-item>

      <el-form-item :label="qtyLabel" prop="qty">
        <el-input-number
          v-model="form.qty"
          :min="minQty"
          :step="stepQty"
          :precision="precisionQty"
          controls-position="right"
          style="width: 220px"
        />
      </el-form-item>

      <el-divider>金额（展示用，最终以后端计算为准）</el-divider>

      <el-form-item label="单价">
        <el-input :model-value="unitPriceText" disabled />
      </el-form-item>

      <el-form-item label="小计">
        <el-input :model-value="subtotalText" disabled />
      </el-form-item>

      <el-form-item label="折扣%" prop="discount_percent">
        <el-input-number v-model="form.discount_percent" :min="0" :max="100" :step="1" :precision="2" />
      </el-form-item>

      <el-form-item label="立减￥" prop="direct_off">
        <el-input-number v-model="form.direct_off" :min="0" :step="10" :precision="2" />
      </el-form-item>

      <el-form-item label="应付">
        <el-input :model-value="totalText" disabled />
      </el-form-item>

      <el-form-item label="支付方式">
        <el-select v-model="form.payment_method" style="width: 220px" clearable placeholder="可不选">
          <el-option label="现金" value="cash" />
          <el-option label="支付宝" value="alipay" />
          <el-option label="微信" value="wechat" />
          <el-option label="对公转账" value="bank_transfer" />
        </el-select>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" placeholder="备注（选填）" />
      </el-form-item>

      <el-alert
        v-if="errorMsg"
        :title="errorMsg"
        type="error"
        show-icon
        :closable="false"
        class="mb-2"
      />
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">确定购买</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getUnitPriceByStudent, createPurchase } from '@/api/billing'

/**
 * props & emits
 */
const props = defineProps({
  visible: { type: Boolean, default: false },
  student: { type: Object, default: null }, // 至少需要 { id, name, grade }
})
const emits = defineEmits(['update:visible', 'success'])

const visible = ref(false)
watch(() => props.visible, v => { visible.value = v; if (v) init() })
function close () { emits('update:visible', false) }

/**
 * 表单
 */
const formRef = ref(null)
const form = ref({
  student_id: null,
  course_mode: 'small_class',  // 默认小班；你也可以改成 'one_to_one'
  qty: 1,
  discount_percent: 0,
  direct_off: 0,
  remark: '',
  payment_method: '', // 'cash' | 'alipay' | 'wechat' | 'bank_transfer'
})

const rules = {
  course_mode: [{ required: true, message: '请选择班型', trigger: 'change' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  discount_percent: [
    { type: 'number', min: 0, max: 100, message: '折扣应在 0~100 之间', trigger: 'change' },
  ],
  direct_off: [
    { type: 'number', min: 0, message: '立减金额不应小于 0', trigger: 'change' },
  ],
}

const student = computed(() => props.student || {})
const errorMsg = ref('')

/**
 * 计量单位 & 数量输入行为
 */
const unitOfMode = {
  one_to_one: 'hours',
  one_to_two: 'hours',
  small_class: 'sessions',
}
const qtyLabel = computed(() => {
  const u = unitOfMode[form.value.course_mode]
  return u === 'hours' ? '购买小时' : '购买节数'
})
const stepQty = computed(() => unitOfMode[form.value.course_mode] === 'hours' ? 0.5 : 1)
const precisionQty = computed(() => unitOfMode[form.value.course_mode] === 'hours' ? 1 : 0)
const minQty = computed(() => 1)

/**
 * 单价 / 金额联动（从后端取价）
 */
const unitPrice = ref(0)
const unitText = computed(() => unitOfMode[form.value.course_mode] === 'hours' ? '小时' : '节')
const unitPriceText = computed(() => `￥${unitPrice.value.toFixed(2)} / ${unitText.value}`)

const subtotalText = computed(() => {
  const sub = Number(form.value.qty || 0) * Number(unitPrice.value || 0)
  return `￥${sub.toFixed(2)}`
})
const totalText = computed(() => {
  const sub = Number(form.value.qty || 0) * Number(unitPrice.value || 0)
  const afterDiscount = sub * (100 - Number(form.value.discount_percent || 0)) / 100
  const total = Math.max(0, afterDiscount - Number(form.value.direct_off || 0))
  return `￥${total.toFixed(2)}`
})

async function fetchUnitPrice () {
  errorMsg.value = ''
  if (!student.value?.id) return
  try {
    const { data } = await getUnitPriceByStudent(student.value.id, form.value.course_mode, form.value.qty || 1)
    unitPrice.value = Number(data?.data?.unit_price || 0)
  } catch (e) {
    unitPrice.value = 0
    errorMsg.value = (e?.response?.data?.detail) || (e?.__friendlyMsg) || '无法获取单价，请检查价格规则'
  }
}

watch(() => [form.value.course_mode, form.value.qty], () => {
  // 防抖（简单版）：数量变化频繁时避免频繁请求
  clearTimeout(fetchUnitPrice._t)
  fetchUnitPrice._t = setTimeout(fetchUnitPrice, 200)
})

function onCourseModeChange () {
  // 切换班型后，数量回到 1，避免从 1.5 小时切到小班时的小数残留
  form.value.qty = 1
}

function init () {
  form.value = {
    student_id: student.value.id,
    course_mode: 'small_class',
    qty: 1,
    discount_percent: 0,
    direct_off: 0,
    remark: '',
    payment_method: '',
  }
  unitPrice.value = 0
  errorMsg.value = ''
  fetchUnitPrice()
}

const submitting = ref(false)
async function onSubmit () {
  errorMsg.value = ''
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = { ...form.value }
    const { data } = await createPurchase(payload)
    ElMessage.success('购买成功')
    emits('success', data?.data)
    close()
  } catch (e) {
    errorMsg.value = (e?.response?.data?.detail) || (e?.__friendlyMsg) || '提交失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.mb-2 { margin-bottom: 8px; }
:deep(.el-form-item) { margin-bottom: 10px; }
</style>
