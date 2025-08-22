<template>
  <div class="page">
    <!-- 顶部筛选 -->
    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="姓名/备注/学校" clearable @keyup.enter="fetchData" style="width:240px" />
      <el-select v-model="query.grade_id" placeholder="年级" clearable style="width:140px" class="ml">
        <el-option v-for="g in grades" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
      <el-select v-model="query.academic_status" placeholder="学籍状态" clearable style="width:140px" class="ml">
        <el-option label="在读" value="active" />
        <el-option label="停课" value="paused" />
        <el-option label="结课" value="finished" />
        <el-option label="退费清" value="refunded" />
        <el-option label="潜在/未入学" value="inactive" />
      </el-select>
      <el-button class="ml" type="primary" @click="fetchData">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <div class="flex-1" />
      <el-button type="success" @click="openCreate">新增学生</el-button>
    </div>

    <!-- 表格 -->
    <el-table
      :data="rows"
      border
      style="width:100%"
      :header-cell-style="{ textAlign: 'center' }"
      :cell-style="{ textAlign: 'center' }"
    >
      <el-table-column prop="name" label="姓名" min-width="120" />
      <el-table-column prop="grade_label" label="年级" width="90" />
      <el-table-column prop="school_name" label="学校" min-width="160" />
      <el-table-column label="主联系人" min-width="180">
        <template #default="{ row }">
          <span v-if="row.primary_contact">
            {{ row.primary_contact.relation_label }} {{ row.primary_contact.phone }}
          </span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="班主任" min-width="120">
        <template #default="{ row }">
          <span v-if="row.current_salesperson">{{ row.current_salesperson.name }}</span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="学籍状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.academic_status)">{{ statusText(row.academic_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="来访渠道" min-width="110">
        <template #default="{ row }">
          <el-tag effect="plain">
            {{ row.visit_channel_label || channelText(row.visit_channel) || '—' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="created_at" label="创建时间" min-width="140">
        <template #default="{ row }">
          {{ (row.created_at || '').slice(0, 10) }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" disabled>编辑（下一步）</el-button>
          <el-button text size="small" @click="openCourseInfo(row)">课程信息</el-button>
          <el-button text size="small" type="primary" @click="openPurchase(row)">购买课程</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="mt flex items-center justify-end">
      <el-pagination
        background layout="prev, pager, next, sizes, total"
        :total="total" :current-page="query.page" :page-size="query.page_size"
        @current-change="(p)=>{ query.page=p; fetchData() }"
        @size-change="(s)=>{ query.page_size=s; query.page=1; fetchData() }"
      />
    </div>

    <!-- 新增弹窗 -->
    <StudentForm v-model="dlg.create" mode="create" @success="onCreated" />

    <!-- 课程信息（加入操作人展示） -->
    <el-dialog v-model="dlg.course" :title="`课程信息 - ${currentStudent?.name||''}`" width="900px">
      <div v-if="courseErr" class="text-danger" style="margin-bottom:8px">{{ courseErr }}</div>

      <el-card shadow="never" class="mb-2">
        <template #header>
          <div class="card-header">在读账户汇总（含赠送）</div>
        </template>
        <el-table :data="courseSummary" size="small" border>
          <el-table-column label="班型" prop="course_mode" width="120">
            <template #default="{row}">{{ modeText(row.course_mode) }}</template>
          </el-table-column>
          <el-table-column label="单位" prop="unit" width="90">
            <template #default="{row}">{{ row.unit==='hours'?'小时':'节' }}</template>
          </el-table-column>
          <el-table-column label="付费剩余" prop="remaining_paid" />
          <el-table-column label="赠送剩余" prop="remaining_gift" />
          <el-table-column label="合计" prop="remaining_total" />
          <el-table-column label="累计实付(￥)" prop="amount_total" />
          <el-table-column label="最近一笔" width="260">
            <template #default="{row}">
              <span v-if="row.last_purchase">
                {{ (row.last_purchase.created_at || '').slice(0,19).replace('T',' ') }}
                ｜{{ row.last_purchase.qty }}+赠{{ row.last_purchase.gift_qty }}
                <template v-if="row.last_purchase.operator_name">｜操作人：{{ row.last_purchase.operator_name }}</template>
              </span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">最近购买记录</div>
        </template>
        <el-table :data="purchaseList" size="small" border>
          <el-table-column label="时间" width="170">
            <template #default="{row}">{{ (row.created_at||'').slice(0,19).replace('T',' ') }}</template>
          </el-table-column>
          <el-table-column label="班型" width="120">
            <template #default="{row}">{{ modeText(row.course_mode) }}</template>
          </el-table-column>
          <el-table-column label="数量">
            <template #default="{row}">{{ row.qty }} {{ row.unit==='hours'?'小时':'节' }}</template>
          </el-table-column>
          <el-table-column label="赠送" prop="gift_qty" width="90" />
          <el-table-column label="单价(￥)" prop="unit_price" width="100" />
          <el-table-column label="实付(￥)" prop="total_payable" width="120" />
          <!-- 新增：操作人 -->
          <el-table-column label="操作人" width="120">
            <template #default="{row}">
              {{ row.operator_name || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="备注" prop="remark" />
        </el-table>
      </el-card>
    </el-dialog>

    <!-- 购买课程弹窗（保持不变） -->
    <el-dialog
      v-model="dlg.purchase"
      width="560px"
      :title="`给【${currentStudent?.name || ''}】购买课程`"
      destroy-on-close
    >
      <el-form
        ref="purchaseFormRef"
        :model="purchaseForm"
        :rules="purchaseRules"
        label-width="100px"
        @keydown.enter.prevent="submitPurchase"
      >
        <el-form-item label="学生">
          <el-input :model-value="currentStudent?.name || ''" disabled />
        </el-form-item>

        <el-form-item label="班型" prop="course_mode">
          <el-select v-model="purchaseForm.course_mode" style="width: 220px" @change="onCourseModeChange">
            <el-option label="一对一（按小时）" value="one_to_one" />
            <el-option label="一对二（按小时）" value="one_to_two" />
            <el-option label="小班（按节）" value="small_class" />
          </el-select>
        </el-form-item>

        <el-form-item :label="qtyLabel" prop="qty">
          <el-input-number
            v-model="purchaseForm.qty"
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
          <el-input-number v-model="purchaseForm.discount_percent" :min="0" :max="100" :step="1" :precision="2" />
        </el-form-item>

        <el-form-item label="立减￥" prop="direct_off">
          <el-input-number v-model="purchaseForm.direct_off" :min="0" :step="10" :precision="2" />
        </el-form-item>

        <el-form-item label="应付">
          <el-input :model-value="totalText" disabled />
        </el-form-item>

        <el-form-item label="支付方式">
          <el-select v-model="purchaseForm.payment_method" style="width: 220px" clearable placeholder="可不选">
            <el-option label="现金" value="cash" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="微信" value="wechat" />
            <el-option label="对公转账" value="bank_transfer" />
          </el-select>
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="purchaseForm.remark" type="textarea" placeholder="备注（选填）" />
        </el-form-item>

        <el-alert
          v-if="purchaseError"
          :title="purchaseError"
          type="error"
          show-icon
          :closable="false"
          class="mb-2"
        />
      </el-form>

      <template #footer>
        <el-button @click="dlg.purchase=false">取消</el-button>
        <el-button type="primary" :loading="purchaseSubmitting" @click="submitPurchase">确定购买</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/http'
import { listStudents } from '../../api/student'
import { getGrades } from '../../api/dicts'
import { getUnitPriceByStudent, createPurchase } from '../../api/billing'
import StudentForm from '../../layouts/components/StudentForm.vue'

const query = reactive({ keyword:'', grade_id: undefined, academic_status: undefined, page:1, page_size:10 })
const rows = ref([]); const total = ref(0); const grades = ref([])

async function fetchData() {
  const { data } = await listStudents(query)
  rows.value = data.data?.results || []
  total.value = data.data?.count || 0
}
function resetQuery() {
  query.keyword=''; query.grade_id=undefined; query.academic_status=undefined; query.page=1; fetchData()
}

function statusText(s){ return ({active:'在读',paused:'停课',finished:'结课',refunded:'退费清',inactive:'潜在/未入学'})[s] || s }
function statusType(s){ return ({active:'success',paused:'warning',finished:'info',refunded:'danger',inactive:''})[s] || '' }
function channelText(c){ return ({referral:'转介绍',walk_in:'直访',other:'其他'})[c] || c }
function modeText(m){ return ({one_to_one:'一对一', one_to_two:'一对二', small_class:'小班'})[m] || m }

const dlg = reactive({ create:false, course:false, purchase:false })
function openCreate(){ dlg.create = true }
function onCreated(){ dlg.create=false; fetchData() }

/** 课程信息 */
const currentStudent = ref(null)
const courseSummary = ref([])
const purchaseList = ref([])
const courseErr = ref('')

async function openCourseInfo(row){
  currentStudent.value = row
  courseErr.value = ''
  courseSummary.value = []
  purchaseList.value = []
  dlg.course = true
  try{
    const s = await api.get('billing/enrollment-summary', { params: { student_id: row.id } })
    courseSummary.value = s.data?.data || []
    const p = await api.get('billing/purchases/list', { params: { student_id: row.id, page_size: 20 } })
    purchaseList.value = p.data?.data?.results || []
  }catch(e){
    courseErr.value = e?.response?.data?.message || e?.__friendlyMsg || '加载课程信息失败'
  }
}

/** 购买课程（保持一致） */
function openPurchase(row){
  currentStudent.value = row
  initPurchaseForm()
  dlg.purchase = true
}

const purchaseFormRef = ref(null)
const purchaseForm = ref({
  student_id: null,
  course_mode: 'small_class',
  qty: 1,
  discount_percent: 0,
  direct_off: 0,
  remark: '',
  payment_method: '',
})
const purchaseRules = {
  course_mode: [{ required: true, message: '请选择班型', trigger: 'change' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  discount_percent: [{ type: 'number', min: 0, max: 100, message: '折扣应在 0~100 之间' }],
  direct_off: [{ type: 'number', min: 0, message: '立减金额不能小于 0' }],
}

const unitOfMode = { one_to_one: 'hours', one_to_two: 'hours', small_class: 'sessions' }
const qtyLabel = computed(()=> unitOfMode[purchaseForm.value.course_mode] === 'hours' ? '购买小时' : '购买节数')
const stepQty = computed(()=> unitOfMode[purchaseForm.value.course_mode] === 'hours' ? 0.5 : 1)
const precisionQty = computed(()=> unitOfMode[purchaseForm.value.course_mode] === 'hours' ? 1 : 0)
const minQty = computed(()=> 1)

const unitPrice = ref(0)
const unitText = computed(()=> unitOfMode[purchaseForm.value.course_mode] === 'hours' ? '小时' : '节')
const unitPriceText = computed(()=> `￥${unitPrice.value.toFixed(2)} / ${unitText.value}`)
const subtotalText = computed(()=>{
  const sub = Number(purchaseForm.value.qty || 0) * Number(unitPrice.value || 0)
  return `￥${sub.toFixed(2)}`
})
const totalText = computed(()=>{
  const sub = Number(purchaseForm.value.qty || 0) * Number(unitPrice.value || 0)
  const afterDiscount = sub * (100 - Number(purchaseForm.value.discount_percent || 0)) / 100
  const total = Math.max(0, afterDiscount - Number(purchaseForm.value.direct_off || 0))
  return `￥${total.toFixed(2)}`
})

const purchaseError = ref('')
function onCourseModeChange(){ purchaseForm.value.qty = 1 }

async function fetchUnitPrice(){
  purchaseError.value = ''
  if (!currentStudent.value?.id) return
  try{
    const { data } = await getUnitPriceByStudent(currentStudent.value.id, purchaseForm.value.course_mode, purchaseForm.value.qty || 1)
    unitPrice.value = Number(data?.data?.unit_price || 0)
  }catch(e){
    unitPrice.value = 0
    purchaseError.value = (e?.response?.data?.detail) || (e?.__friendlyMsg) || '无法获取单价，请检查价格规则'
  }
}
watch(()=>[purchaseForm.value.course_mode, purchaseForm.value.qty], ()=>{
  clearTimeout(fetchUnitPrice._t)
  fetchUnitPrice._t = setTimeout(fetchUnitPrice, 200)
})

function initPurchaseForm(){
  purchaseForm.value = {
    student_id: currentStudent.value?.id,
    course_mode: 'small_class',
    qty: 1,
    discount_percent: 0,
    direct_off: 0,
    remark: '',
    payment_method: '',
  }
  unitPrice.value = 0
  purchaseError.value = ''
  fetchUnitPrice()
}

const purchaseSubmitting = ref(false)
async function submitPurchase(){
  purchaseError.value = ''
  await purchaseFormRef.value?.validate()
  purchaseSubmitting.value = true
  try{
    await createPurchase({ ...purchaseForm.value })
    ElMessage.success('购买成功')
    dlg.purchase = false
    fetchData()
  }catch(e){
    purchaseError.value = (e?.response?.data?.detail) || (e?.__friendlyMsg) || '提交失败，请稍后再试'
  }finally{
    purchaseSubmitting.value = false
  }
}

onMounted(async () => {
  const { data } = await getGrades(); grades.value = data.data || []
  fetchData()
})
</script>

<style scoped>
.page { padding: 8px; }
.toolbar { display:flex; align-items:center; gap:8px; margin-bottom: 10px; }
.flex-1 { flex: 1; }
.ml { margin-left: 8px; }
.mt { margin-top: 12px; }
.text-muted { color:#888; }
.text-danger { color:#c45656; }
.mb-2 { margin-bottom: 8px; }
:deep(.el-form-item) { margin-bottom: 10px; }
.card-header{ font-weight:600; }
</style>
