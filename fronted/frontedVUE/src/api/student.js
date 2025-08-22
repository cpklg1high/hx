// src/api/student.js
import api from './http'

export function listStudents(params) {
  return api.get('students/', { params })
}

export function createStudent(payload) {
  return api.post('students/', payload)
}

export function updateStudent(id, payload) {
  return api.put(`students/${id}/`, payload)
}

export function deleteStudent(id) {
  return api.delete(`students/${id}/`)
}

// 在读学员搜索（用于转介绍选择）
export function searchReferralCandidates(keyword) {
  return api.get('students/search', { params: { keyword } })
}
// 查询该学生是否有转介绍奖励（验收用，可选）
export function getReferralRewardByStudent(studentId) {
  return api.get(`referral/reward-by-student/${studentId}`)
}

// 补充：学校远程搜索（按拼音排序由后端保证）
export function searchSchools(keyword) {
  return api.get('schools', { params: { keyword } })
}