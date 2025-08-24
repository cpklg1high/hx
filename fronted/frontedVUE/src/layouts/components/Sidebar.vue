<template>
  <el-menu
    router
    :default-active="activePath"
    background-color="#2d3a4b"
    text-color="#fff"
    active-text-color="#ffd04b"
  >
    <el-menu-item index="/">
      <el-icon><i class="el-icon-house" /></el-icon>
      <span>首页</span>
    </el-menu-item>

    <el-sub-menu index="/students">
      <template #title>
        <el-icon><i class="el-icon-user" /></el-icon>
        <span>学生管理</span>
      </template>
      <el-menu-item index="/students">学生档案</el-menu-item>
      <el-menu-item index="/students/courses">在读课程</el-menu-item>
      <el-menu-item index="/students/billing">购买/退费</el-menu-item>
      <el-menu-item index="/students/attendance">签到与消课</el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="/courses">
      <template #title>
        <el-icon><i class="el-icon-notebook-2" /></el-icon>
        <span>课程管理</span>
      </template>
      <el-menu-item index="/courses">课程列表</el-menu-item>
      <el-menu-item index="/schedule">排课</el-menu-item>

    </el-sub-menu>

    <el-sub-menu index="/teachers">
      <template #title>
        <el-icon><i class="el-icon-coordinate" /></el-icon>
        <span>教师管理</span>
      </template>
      <el-menu-item index="/teachers">教师列表</el-menu-item>
      <el-menu-item index="/teachers/hour-stats">课时统计</el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="/campus">
      <template #title>
        <el-icon><i class="el-icon-office-building" /></el-icon>
        <span>校区管理</span>
      </template>
      <el-menu-item index="/campus">校区/教室</el-menu-item>
      <el-menu-item index="/campus/calendar">学期/假期设置</el-menu-item>
    </el-sub-menu>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const activePath = computed(() => route.path)
</script>

<style scoped>
:deep(.el-sub-menu__title) { color: #fff; }
</style>
