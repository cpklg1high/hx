<template>
  <div class="filters">
    <el-form :inline="true" :model="form" label-width="80px">
      <el-form-item label="校区">
        <el-select v-model="form.campusId" placeholder="选择校区" style="width: 220px" @change="loadCycles">
          <el-option
            v-for="c in campuses"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="年份">
        <el-input
          v-model="form.year"
          placeholder="如：2025"
          style="width: 120px"
          @change="loadCycles"
        />
      </el-form-item>

      <el-form-item label="学期">
        <el-select v-model="form.termType" placeholder="选择学期" style="width: 160px" @change="loadCycles">
          <el-option label="春季" value="spring" />
          <el-option label="暑假" value="summer" />
          <el-option label="秋季" value="autumn" />
          <el-option label="寒假" value="winter" />
        </el-select>
      </el-form-item>

      <el-form-item label="周期">
        <el-select
          v-model="form.cycleId"
          :placeholder="cycles.length ? '选择周期' : '无可用周期'"
          style="width: 260px"
          :loading="cyclesLoading"
          :disabled="!cycles.length"
          @change="emitChange"
        >
          <el-option
            v-for="cy in cycles"
            :key="cy.id"
            :label="cy.name"
            :value="cy.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { listCampuses, listCycles, getCycle } from '../../../api/cycle'

const emit = defineEmits(['change'])

const campuses = ref([])
const cycles = ref([])
const cyclesLoading = ref(false)
const noCycles = ref(false) // ✅ 新增：当前筛选下是否无周期

const nowYear = dayjs().year()

const form = reactive({
  campusId: null,
  year: String(nowYear),
  termType: 'autumn',
  cycleId: null
})

onMounted(async () => {
  try {
    const { data } = await listCampuses({ active: true })
    campuses.value = data?.data || []
  } catch {
    ElMessage.error('拉取校区失败')
  }
})

async function loadCycles() {
  // 条件不完整 → 清空周期并向外发“无年份”
  if (!form.campusId || !form.year || !form.termType) {
    cycles.value = []
    form.cycleId = null
    noCycles.value = true
    emit('change', {
      campusId: form.campusId,
      year: form.year,
      termType: form.termType,
      cycleId: null,
      cycle: null,
      yearDisplay: '无年份' // ✅ 通知父组件显示“无年份”
    })
    return
  }

  try {
    cyclesLoading.value = true
    const { data } = await listCycles({
      campus: form.campusId,
      year: form.year,
      term_type: form.termType
    })
    cycles.value = data?.data || []

    if (!cycles.value.length) {
      // ✅ 没有任何周期：禁用下拉、抛出“无年份”
      form.cycleId = null
      noCycles.value = true
      ElMessage.info('该校区/年份/学期下暂无周期')
      emit('change', {
        campusId: form.campusId,
        year: form.year,
        termType: form.termType,
        cycleId: null,
        cycle: null,
        yearDisplay: '无年份'
      })
      return
    }

    // 有周期：自动选第一个便于快速浏览
    noCycles.value = false
    form.cycleId = cycles.value[0]?.id ?? null
    await emitChange()
  } catch {
    ElMessage.error('拉取周期失败')
    // 出错时也标记为无周期
    cycles.value = []
    form.cycleId = null
    noCycles.value = true
    emit('change', {
      campusId: form.campusId,
      year: form.year,
      termType: form.termType,
      cycleId: null,
      cycle: null,
      yearDisplay: '无年份'
    })
  } finally {
    cyclesLoading.value = false
  }
}

async function emitChange() {
  // 根据 noCycles 决定 yearDisplay
  const yearDisplay = noCycles.value ? '无年份' : form.year

  if (!form.cycleId) {
    emit('change', {
      campusId: form.campusId,
      year: form.year,
      termType: form.termType,
      cycleId: null,
      cycle: null,
      yearDisplay
    })
    return
  }
  try {
    const { data } = await getCycle(form.cycleId)
    emit('change', {
      campusId: form.campusId,
      year: form.year,
      termType: form.termType,
      cycleId: form.cycleId,
      cycle: data?.data || null,
      yearDisplay
    })
  } catch {
    emit('change', {
      campusId: form.campusId,
      year: form.year,
      termType: form.termType,
      cycleId: null,
      cycle: null,
      yearDisplay
    })
  }
}
</script>

<style scoped>
.filters { padding: 8px 4px; }
</style>
