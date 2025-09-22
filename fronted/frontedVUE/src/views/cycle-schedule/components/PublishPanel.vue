<template>
  <el-drawer v-model="visible" :title="title" size="720px" destroy-on-close>
    <div v-if="cycle" class="mb-3">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="校区">{{ cycle?.campus?.name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="学期">{{ cycle?.term_type || '—' }}</el-descriptions-item>
        <el-descriptions-item label="年份">{{ cycle?.year ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ cycle?.name || `#${cycle?.id}` }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="说明"
      description="先打通接口：支持一键从看板日期生成周几→日期映射；可预演与发布。下一步再做精细可视化日期编辑与A/B轨。"
      class="mb-3"
    />

    <el-form label-width="108px">
      <el-form-item label="范围(scope)">
        <el-radio-group v-model="scope">
          <el-radio-button label="future_only">仅未来</el-radio-button>
          <el-radio-button label="include_today">含今天</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="模式(mode)">
        <el-segmented v-model="mode" :options="['participants']" />
        <div class="tip">当前仅支持 participants</div>
      </el-form-item>

      <el-form-item label="映射(map)">
        <div class="map-toolbar">
          <el-button size="small" @click="generateMapFromBoard" :disabled="!board?.dates?.length">从看板生成</el-button>
          <el-button size="small" link type="primary" @click="clearMap">清空</el-button>
        </div>

        <!-- 轻量展示：每个周几显示日期数量，点击可展开查看 -->
        <el-collapse class="map-preview" v-model="openPanels">
          <el-collapse-item v-for="wk in weekdayOrder" :key="wk" :name="wk">
            <template #title>
              <b style="width:64px;display:inline-block">{{ wk }}</b>
              <span>共 {{ (map[wk] || []).length }} 天</span>
            </template>
            <div class="dates-wrap" v-if="(map[wk] || []).length">
              <el-tag
                v-for="d in map[wk]"
                :key="d"
                class="date-tag"
                disable-transitions
              >{{ d }}</el-tag>
            </div>
            <div v-else class="empty-line">（无）</div>
          </el-collapse-item>
        </el-collapse>
      </el-form-item>

      <el-form-item label="分轨(tracks)">
        <el-alert
          type="warning"
          :closable="false"
          title="A/B 轨将在下一步提供编辑 UI。当前发布将仅使用上面的 map。"
        />
      </el-form-item>
    </el-form>

    <el-divider />

    <!-- 上次预演摘要（可选显示） -->
    <div v-if="lastResult" class="mb-2">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="建议新增">{{ lastResult.add ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="建议移除">{{ lastResult.remove ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="缺失课次">{{ lastResult.missing_lessons?.length ?? 0 }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="(lastResult.missing_lessons || []).length" class="missing-box">
        <div class="missing-title">缺失课次（仅列出前 10 条）</div>
        <ul>
          <li v-for="(m, idx) in lastResult.missing_lessons.slice(0,10)" :key="idx">
            {{ m.date }} ｜ class_group_id={{ m.class_group_id }}
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <div class="footer-actions">
        <el-button @click="onSaveDraft" :loading="loading" plain>保存草稿（dry-run留痕）</el-button>
        <el-button @click="onDryRun" type="warning" :loading="loading" plain>预演</el-button>
        <el-button @click="onPublish" type="primary" :loading="loading">确认发布</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { publishCycle } from '../../../api/cycle'

// props：父级会把当前选中周期和看板透传进来
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  cycle: { type: Object, default: null },
  board: { type: Object, default: null }, // { dates:[], rows:[] ... } 用于一键生成 map
})
const emits = defineEmits(['update:modelValue', 'saved', 'dryrun', 'published'])

const visible = computed({
  get: () => props.modelValue,
  set: v => emits('update:modelValue', v),
})

const title = computed(() => `发布：${props.cycle?.name || `#${props.cycle?.id || ''}`}`)
const loading = ref(false)

// —— 基础参数 —— //
const scope = ref('future_only')     // future_only / include_today
const mode = ref('participants')     // 当前仅 participants

// —— 周几 → 日期 的映射（最小可用：从看板 dates 自动分桶） —— //
const weekdayOrder = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
const map = ref({})         // { Mon:[YYYY-MM-DD,...], ... }
const openPanels = ref(['Mon']) // 展开面板：默认展开周一

function clearMap() {
  map.value = {}
  lastResult.value = null
}

function weekdayName(d) {
  return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][dayjs(d).day()] // day()：0=Sun
}

function generateMapFromBoard() {
  const dates = props.board?.dates || []
  const m = { Mon:[], Tue:[], Wed:[], Thu:[], Fri:[], Sat:[], Sun:[] }
  for (const d of dates) {
    const wk = weekdayName(d)  // Sun/Mon/...
    const key = (wk === 'Sun') ? 'Sun' : wk
    if (!m[key]) m[key] = []
    m[key].push(d)
  }
  // 只保留有值的项，避免冗余
  const slim = {}
  for (const k of Object.keys(m)) {
    if (m[k]?.length) slim[k] = Array.from(new Set(m[k])).sort()
  }
  map.value = slim
  openPanels.value = Object.keys(slim)
  ElMessage.success('已根据看板日期生成映射')
}

// —— 结果摘要 —— //
const lastResult = ref(null)

// —— 调后端：dry-run / publish —— //
async function callPublish({ dryRun }) {
  if (!props.cycle?.id) {
    ElMessage.warning('缺少周期ID')
    return
  }
  // 保障最小输入：至少有一个周几有日期
  const hasAny = Object.values(map.value || {}).some(arr => (arr && arr.length))
  if (!hasAny) {
    ElMessage.warning('请先生成/编辑周几→日期映射')
    return
  }

  const payload = {
    scope: scope.value,
    mode: mode.value,
    dry_run: !!dryRun,
    map: map.value,
    // tracks：下一步接入
  }

  loading.value = true
  try {
    const { data } = await publishCycle(props.cycle.id, payload)
    const body = data?.data || {}
    lastResult.value = {
      add: body.add ?? body.added?.length ?? 0,
      remove: body.remove ?? body.removed?.length ?? 0,
      missing_lessons: body.missing_lessons || [],
    }
    if (dryRun) {
      ElMessage.success(`预演完成：建议新增 ${lastResult.value.add}，移除 ${lastResult.value.remove}`)
      emits('dryrun', lastResult.value)
    } else {
      ElMessage.success(`发布完成：新增 ${body.added?.length || 0}，移除 ${body.removed?.length || 0}`)
      emits('published', body)
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || '发布接口调用失败')
  } finally {
    loading.value = false
  }
}

function onSaveDraft() {
  // 与 dry-run 相同，只是语义为“保存草稿记录”
  callPublish({ dryRun: true }).then(() => emits('saved', lastResult.value))
}
function onDryRun()  { callPublish({ dryRun: true }) }
function onPublish() { callPublish({ dryRun: false }) }
</script>

<style scoped>
.mb-3 { margin-bottom: 12px; }
.mb-2 { margin-bottom: 8px; }
.footer-actions { display: flex; gap: 8px; justify-content: flex-end; }
.tip { color: #909399; margin-left: 12px; }
.map-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.map-preview { border: 1px solid var(--el-border-color); border-radius: 6px; padding: 8px; }
.date-tag { margin: 4px 6px 0 0; }
.dates-wrap { padding: 4px 0 6px; }
.empty-line { color: #b1b3b8; }
.missing-box { margin-top: 8px; }
.missing-title { font-weight: 600; margin-bottom: 4px; }
</style>
