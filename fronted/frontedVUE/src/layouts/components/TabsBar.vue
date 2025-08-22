<template>
  <el-tabs type="card" v-model="active">
    <el-tab-pane label="首页" name="/"></el-tab-pane>
  </el-tabs>
</template>
<script setup>
import { ref } from 'vue'
const active = ref('/')
</script>
