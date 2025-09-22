// src/api/preplan.js
import request from './http'

// 与你现有 schedule.js 一致的前缀逻辑，确保 baseURL 安全拼接
const base = (request.defaults && request.defaults.baseURL) || ''
const needApiPrefix = !/\/api\/?$/i.test(base)
const API = (p) => (needApiPrefix ? `/api${p}` : p)

// —— 基础筛选所需 ——
// 校区
export const listCampuses = (params) =>
  request.get(API('/schedule/cycle-schedule/campuses'), { params })

// 周期
export const listCycles = (params) =>
  request.get(API('/schedule/cycle-schedule/cycles'), { params })

// 老师（沿用后端 teachers）
export const listTeachers = () =>
  request.get(API('/schedule/teachers'))

// —— 预排槽（缓冲池） ——
// 查询
export const listPreplanSlots = (params) =>
  request.get(API('/schedule/cycle-schedule/preplan/slots'), { params })

// 创建
export const createPreplanSlot = (data) =>
  request.post(API('/schedule/cycle-schedule/preplan/slots'), data)

// 详情（当前用不上，预留）
export const getPreplanSlot = (id) =>
  request.get(API(`/schedule/cycle-schedule/preplan/slots/${id}`))

// 删除（当前不做删除入口，预留）
export const deletePreplanSlot = (id) =>
  request.delete(API(`/schedule/cycle-schedule/preplan/slots/${id}`))
