// src/api/cycle.js
import request from './http'

// 和 schedule.js 一样的前缀策略，避免出现 /api/api
const base = (request.defaults && request.defaults.baseURL) || ''
const needApiPrefix = !/\/api\/?$/i.test(base)
const API = (p) => (needApiPrefix ? `/api${p}` : p)

// ---- 校区 ----
export const listCampuses = (params) =>
  request.get(API('/schedule/cycle-schedule/campuses'), { params })

// ---- 周期 ----
export const listCycles = (params) =>
  request.get(API('/schedule/cycle-schedule/cycles'), { params })

export const getCycle = (id) =>
  request.get(API(`/schedule/cycle-schedule/cycles/${id}`))

// ✅ 周期看板（老师 × 日期）
export const getCycleBoard = (id) =>
  request.get(API(`/schedule/cycle-schedule/cycles/${id}/board`))

// （后续步骤会用到的接口，先留着）
// export const getCycleRoster = (cycleId, classGroupId, params) =>
//   request.get(API(`/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`), { params })

// export const addCycleRoster = (cycleId, classGroupId, data) =>
//   request.post(API(`/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`), data)

// export const delCycleRoster = (cycleId, classGroupId, data) =>
//   request.delete(API(`/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`), { data })

// export const publishCycle = (cycleId, data) =>
//   request.post(API(`/schedule/cycle-schedule/cycles/${cycleId}/publish`), data)

/** 获取某周期某班级的名册 */
export function getCycleRoster(cycleId, classGroupId, params = {}) {
  return request.get(API(`/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`), {
    params,
  })
}

// POST /api/schedule/cycle-schedule/cycles/{cycleId}/class-groups/{classGroupId}/roster
export const addCycleRoster = (cycleId, classGroupId, data) =>
  request.post(`/api/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`, data)

/** 批量从名册移除（仅删除 CycleRoster，不影响 Lesson/Attendance） */
export function deleteCycleRoster(cycleId, classGroupId, studentIds, track = null) {
  const data = { students: studentIds }
  if (track) data.track = track
  return request.delete(API(`/schedule/cycle-schedule/cycles/${cycleId}/class-groups/${classGroupId}/roster`), {
    data,
  })
}

export function getCycleMasterRoster(cycleId, params = {}) {
  return request.get(API(`/schedule/cycle-schedule/cycles/${cycleId}/roster`), {
    params,
  })
}

export const publishCycle = (id, payload) =>
  request.post(`/schedule/cycle-schedule/cycles/${id}/publish`, payload)
