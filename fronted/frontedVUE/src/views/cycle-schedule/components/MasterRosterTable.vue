<template>
  <div>
    <el-alert
      v-if="!cycleId"
      type="info"
      :closable="false"
      title="请选择一个有效周期后查看总名册"
      class="mb-2"
    />
    <div v-else>
      <el-table
        v-loading="loading"
        :data="rows"
        border
        style="width: 100%"
      >
        <el-table-column prop="student_name" label="学生" min-width="120" />
        <el-table-column prop="class_group_name" label="班级" min-width="140" />
        <el-table-column prop="subject_name" label="学科" width="100" />
        <el-table-column prop="teacher_name" label="老师" width="120" />
        <el-table-column prop="course_mode" label="班型" width="110" />
        <el-table-column prop="grade" label="年级" width="80" />
        <el-table-column prop="track" label="轨道" width="70" />
        <el-table-column prop="type" label="类型" width="90" />
      </el-table>

      <div class="flex mt-3 justify-end">
        <el-pagination
          background
          layout="prev, pager, next, jumper, ->, total"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="onPageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCycleMasterRoster } from '../../../api/cycle'

const props = defineProps({
  cycleId: { type: [Number, String], default: null },
})

const loading = ref(false)
const rows = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function fetchData() {
  if (!props.cycleId) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const { data } = await getCycleMasterRoster(props.cycleId, {
      page: page.value,
      page_size: pageSize.value,
      // 首版只读，不做筛选；后面我们再加筛选栏再传参
    })
    const payload = data?.data || { results: [], count: 0 }
    rows.value = payload.results || []
    total.value = payload.count || 0
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '总名册加载失败')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onPageChange(p) {
  page.value = p
  fetchData()
}

// 周期变化时重置分页并拉取
watch(() => props.cycleId, () => {
  page.value = 1
  fetchData()
})

onMounted(fetchData)
</script>

<style scoped>
.mt-3 { margin-top: 12px; }
.mb-2 { margin-bottom: 8px; }
.flex { display: flex; }
.justify-end { justify-content: flex-end; }
</style>
