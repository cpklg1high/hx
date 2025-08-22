<template>
  <div class="bc-wrap">
    <el-breadcrumb separator="/">
      <el-breadcrumb-item v-for="(m, i) in matched" :key="i">
        <span>{{ m.meta?.title || m.name || m.path }}</span>
      </el-breadcrumb-item>
    </el-breadcrumb>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const matched = computed(() => route.matched.filter(r => r.path !== ''))
</script>

<style scoped>
.bc-wrap { padding: 8px 0 16px; }
</style>
