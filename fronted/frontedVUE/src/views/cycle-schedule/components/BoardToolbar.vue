<template>
  <div class="toolbar">
    <el-segmented
      :options="[
        { label: '按教师', value: 'teacher' },
        { label: '按学科', value: 'subject' }
      ]"
      v-model="innerMode"
      @change="emit('update:view-mode', innerMode)"
    />
    <el-input
      class="ml-2"
      style="width: 260px"
      v-model="innerSearch"
      placeholder="搜索老师姓名（包含匹配）"
      clearable
      @input="emit('update:search', innerSearch)"
    >
      <template #prefix><el-icon><i class="el-icon-search" /></el-icon></template>
    </el-input>
    <el-button class="ml-2" :loading="loading" @click="$emit('refresh')">刷新</el-button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  viewMode: { type: String, default: 'teacher' },
  searchText: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['update:view-mode', 'update:search', 'refresh'])

const innerMode = ref(props.viewMode)
const innerSearch = ref(props.searchText)

watch(() => props.viewMode, v => innerMode.value = v)
watch(() => props.searchText, v => innerSearch.value = v)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.ml-2 { margin-left: 8px; }
</style>
