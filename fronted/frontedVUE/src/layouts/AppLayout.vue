<template>
  <div class="app-wrapper">
    <el-container>
      <el-aside width="200px" class="sidebar-container">
        <Sidebar />
      </el-aside>
      <el-container>
        <el-header class="header-container">
          <HeaderBar />
        </el-header>
        <el-main class="main-container">
          <Breadcrumb />
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import HeaderBar from './components/HeaderBar.vue'
import Breadcrumb from './components/Breadcrumb.vue'
</script>

<style scoped>
.app-wrapper { position: relative; width: 100%; height: 100%; }
.sidebar-container { background-color: #2d3a4b; height: 100%; }
.header-container { padding: 0 12px; background: #f5f5f5; box-shadow: 0 1px 4px rgba(0,21,41,.08); }
.main-container { padding: 12px; }
:deep(.el-menu) { border-right: 0; }
</style>
