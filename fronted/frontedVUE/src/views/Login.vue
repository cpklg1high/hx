<template>
  <div class="login-page">
    <el-card class="login-card">
      <h3 class="title">edu 管理系统</h3>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0" @submit.prevent="onSubmit">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="账号"
            @input="clearServerError"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            placeholder="密码"
            type="password"
            show-password
            @input="clearServerError"
          />
          <!-- 内联错误：稳定显示在密码输入框下方 -->
          <div
            v-if="serverError"
            class="form-error"
            role="alert"
            aria-live="polite"
          >{{ serverError }}</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" 
          :loading="loading" 
          native-type="submit" 
          style="width:100%">
          登 录
        </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http.js'
import { useAuthStore } from '../store/auth.js'

const formRef = ref(null)
const loading = ref(false)
const serverError = ref('')   // 用于内联错误文本
const form = ref({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const clearServerError = () => { if (serverError.value) serverError.value = '' }

const onSubmit = () => {
  if (loading.value) return
  serverError.value = '' // 提交前清理旧错误
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const resp = await api.post('auth/login', form.value)
      const { code, data, message } = resp?.data || {}
      if (code === 200 && data?.access && data?.user) {
        auth.setAuth({ access: data.access, user: data.user })
        const redirect = route.query.redirect || '/'
        router.replace(String(redirect))
      } else {
        // 后端业务非 200 的兜底
        serverError.value = message || '用户名或密码错误'
      }
    } catch (e) {
      // 从拦截器/后端取安全可展示的文案
      serverError.value =
        e?.message ||
        e?.response?.data?.message ||
        e?.response?.data?.detail ||
        '用户名或密码错误'
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f0f2f5; }
.login-card { width: 360px; }
.title { text-align: center; margin-bottom: 16px; color: #606266; }
.form-error { color: #f56c6c; font-size: 12px; line-height: 1; padding-top: 4px; }
</style>

<!-- 错误消息为element弹窗，为英文，上面的版本是直接在输入框下提示用户名或密码错误 -->
<!-- <template>
  <div class="login-page">
    <el-card class="login-card">
      <h3 class="title">edu 管理系统</h3>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="账号" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" placeholder="密码" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width:100%" @click="onSubmit">登 录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/http.js'
import { useAuthStore } from '../store/auth.js'

const formRef = ref(null)
const loading = ref(false)
const form = ref({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const onSubmit = () => {
  // 防重复点击
  if (loading.value) return
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const resp = await api.post('auth/login', form.value)
      const { code, data, message } = resp?.data || {}
      if (code === 200 && data?.access && data?.user) {
        auth.setAuth({ access: data.access, user: data.user })
        ElMessage.success(message || '登录成功')
        const redirect = route.query.redirect || '/'
        router.replace(String(redirect))
      } else {
        // 非 200 但无异常抛出时的兜底
        ElMessage.error(message || '用户名或密码错误')
      }
    } catch (e) {
      // 统一从后端取 message/detail；没有就给出安全的通用提示
      const msg =
        e?.response?.data?.message ||
        e?.response?.data?.detail ||
        e?.message ||
        '用户名或密码错误'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  })
}
</script>


<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f0f2f5; }
.login-card { width: 360px; }
.title { text-align: center; margin-bottom: 16px; color: #606266; }
</style> -->
