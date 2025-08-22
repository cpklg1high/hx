<template>
  <div class="navbar">
    <div class="right">
      <el-dropdown>
        <span class="el-dropdown-link">
          <el-avatar :size="36" :src="avatarUrl" />
          <span class="username">{{ auth.user?.username || '未登录' }}</span>
          <el-icon class="el-icon--right"><i class="el-icon-arrow-down" /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="goProfile">个人中心</el-dropdown-item>
            <el-dropdown-item divided @click="logout">安全退出</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api/http.js'
import { useAuthStore } from '../../store/auth.js'

const router = useRouter()
const auth = useAuthStore()

const avatarUrl = computed(() => {
  // 先用占位；如果后端给了头像字段，按你的字段拼接
  return auth.user?.avatar ? ('http://localhost:8000/media/userAvatar/' + auth.user.avatar) : ''
})

function goProfile() {
  // 你之后建“个人中心”页面再改这里
  router.push('/')
}

async function logout() {
  try { await api.post('auth/logout') } catch {}
  auth.clear()
  router.replace('/login')
}
</script>

<style scoped>
.navbar { height: 60px; display: flex; align-items: center; }
.right { margin-left: auto; }
.el-dropdown-link { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.username { font-size: 14px; }
</style>
