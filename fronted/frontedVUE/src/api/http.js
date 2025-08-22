// /api/http.js
import axios from 'axios'
import { useAuthStore } from '../store/auth.js'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/',
  withCredentials: true,   // 发送 refresh_token 与 csrftoken 等 Cookie
  timeout: 15000,
})

export function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : null
}

// 首次进入时，为浏览器种下 csrftoken
export function ensureCsrf() {
  return api.get('auth/csrf')
}

// ====== NEW: 小工具函数（不改变安全边界，仅做消息提取/标记）======
const isLoginReq   = (cfg) => (cfg?.url || '').includes('auth/login')
const isRefreshReq = (cfg) => (cfg?.url || '').includes('auth/refresh')
const isCsrfReq    = (cfg) => (cfg?.url || '').includes('auth/csrf')

function pickServerMsg(resp) {
  // 兼容后端可能的字段：message / info / detail
  return resp?.data?.message || resp?.data?.info || resp?.data?.detail || ''
}

function withFriendlyMsg(error, fallback) {
  const msg = fallback || pickServerMsg(error.response) || '请求失败'
  // 标准化可读消息；不暴露后台敏感细节
  error.message = msg
  error.__friendlyMsg = msg
  return error
}
// ============================================================

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = 'Bearer ' + auth.accessToken
  }
  return config
})

let isRefreshing = false
let queue = []

async function doRefresh() {
  const csrf = getCookie('csrftoken')
  return api.post('auth/refresh', null, {
    headers: { 'X-CSRFToken': csrf || '' },
  })
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const { response, config } = error
    if (!response) throw error

    const status = response.status

    // ====== NEW: 登录接口的错误提示与防误触发刷新 ======
    // 对登录失败（400/401/403 等），统一友好提示“账号或密码错误”
    if ((status === 400 || status === 401 || status === 403) && isLoginReq(config)) {
      throw withFriendlyMsg(error, '账号或密码错误')
    }
    // 刷新/获取CSRF出错不参与自动刷新，直接按后端信息返回
    if (isRefreshReq(config) || isCsrfReq(config)) {
      throw withFriendlyMsg(error)
    }
    // ===================================================

    // 仅对“非登录接口”的 401 做自动刷新与重放
    if (status === 401 && !config.__isRetryRequest) {
      const auth = useAuthStore()

      if (isRefreshing) {
        // 队列等待新的 access
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject })
        }).then((token) => {
          config.headers.Authorization = 'Bearer ' + token
          config.__isRetryRequest = true
          return api(config)
        })
      }

      isRefreshing = true
      try {
        const r = await doRefresh()
        const newToken = r.data?.data?.access
        if (newToken) {
          auth.setAccessToken(newToken)
          // 释放队列
          queue.forEach(p => p.resolve(newToken))
          queue = []
          // 重放当前请求
          config.headers.Authorization = 'Bearer ' + newToken
          config.__isRetryRequest = true
          return api(config)
        }
      } catch (e) {
        // 刷新失败：清空队列、清理本地并跳登录（保持原有逻辑）
        queue.forEach(p => p.reject(e))
        queue = []
        auth.clear()
        if (window.location.pathname !== '/login') {
          const search = new URLSearchParams({ redirect: window.location.pathname }).toString()
          window.location.href = '/login?' + search
        }
        throw e
      } finally {
        isRefreshing = false
      }
    }

    // ====== NEW: 其它 4xx/5xx 统一挂载可读消息，不改变原有抛错行为 ======
    throw withFriendlyMsg(error)
    // ======================================================
  }
)

export default api
