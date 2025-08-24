// src/api/schedule.js
import request from './http'

// 根据 axios 实例的 baseURL 智能决定是否拼接 "/api"
const base = (request.defaults && request.defaults.baseURL) || ''
const needApiPrefix = !/\/api\/?$/i.test(base)   // baseURL 不是 /api 或没设置 → 需要拼前缀
const API = (p) => (needApiPrefix ? `/api${p}` : p)

// ---- 基础字典与学期 ----
export const listTerms     = () => request.get(API('/schedule/terms'))
export const createTerm    = (data) => request.post(API('/schedule/terms'), data)

export const listSubjects  = () => request.get(API('/schedule/subjects'))
export const createSubject = (data) => request.post(API('/schedule/subjects'), data)

export const listRooms     = () => request.get(API('/schedule/rooms'))
export const createRoom    = (data) => request.post(API('/schedule/rooms'), data)

export const listTeachers  = () => request.get(API('/schedule/teachers'))

// ---- 班级 ----
export const createClassGroup   = (data) => request.post(API('/schedule/class-groups'), data)
export const listClassGroups    = (params) => request.get(API('/schedule/class-groups'), { params })
export const enrollClassGroup   = (id, data) => request.post(API(`/schedule/class-groups/${id}/enroll`), data)
export const unenrollClassGroup = (id, data) => request.post(API(`/schedule/class-groups/${id}/unenroll`), data)

// ---- 课次（日/周拉取）----
export const listLessons = (params) => request.get(API('/schedule/lessons'), { params })

// ---- 请假 ----
export const setLeave    = (lessonId, data) => request.post(API(`/schedule/lessons/${lessonId}/leave`), data)
export const revokeLeave = (lessonId, data) => request.delete(API(`/schedule/lessons/${lessonId}/leave`), { data })

// ---- 签到/消课 ----
export const getAttendance    = (lessonId) => request.get(API(`/schedule/lessons/${lessonId}/attendance`))
export const commitAttendance = (lessonId, data) => request.post(API(`/schedule/lessons/${lessonId}/attendance`), data)
export const revertAttendance = (lessonId) => request.post(API(`/schedule/lessons/${lessonId}/attendance/revert`))


// ---- 排课中增删学生 ----
export function enrollStudentsToClassGroup(classGroupId, studentIds) {
  return request.post(`/api/schedule/class-groups/${classGroupId}/enroll`, {
    student_ids: studentIds,
  })
}

export function unenrollStudentsFromClassGroup(classGroupId, studentIds) {
  return request.post(`/api/schedule/class-groups/${classGroupId}/unenroll`, {
    student_ids: studentIds,
  })
}

export const searchStudents = ({ q = '', page = 1, page_size = 20 } = {}) =>
  request.get('/students', { params: { q, page, page_size } })