import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth.js'

import AppLayout from '../layouts/AppLayout.vue'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'

import StudentsList from '../views/students/StudentsList.vue'
import StudentCourses from '../views/students/StudentCourses.vue'
import StudentBilling from '../views/students/StudentBilling.vue'
import StudentAttendance from '../views/students/StudentAttendance.vue'

import Courses from '../views/courses/Courses.vue'
import Schedule from '../views/schedule/ScheduleBoard.vue'

import Teachers from '../views/teachers/Teachers.vue'
import TeacherHourStats from '../views/teachers/TeacherHourStats.vue'

import Campus from '../views/campus/Campus.vue'
import CampusCalendar from '../views/campus/CampusCalendar.vue'


const routes = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', component: Home, meta: { title: '首页' } },

      { path: 'students', name: 'students', component: StudentsList, meta: { title: '学生档案' } },
      { path: 'students/courses', name: 'student-courses', component: StudentCourses, meta: { title: '在读课程' } },
      { path: 'students/billing', name: 'student-billing', component: StudentBilling, meta: { title: '购买/退费' } },
      { path: 'students/attendance', name: 'student-attendance', component: StudentAttendance, meta: { title: '签到与消课' } },

      { path: 'courses', name: 'courses', component: Courses, meta: { title: '课程列表' } },
      { path: 'schedule', name: 'schedule', component: Schedule, meta: { title: '可视化排课' } },

      { path: 'teachers', name: 'teachers', component: Teachers, meta: { title: '教师列表' } },
      { path: 'teachers/hour-stats', name: 'teacher-hour-stats', component: TeacherHourStats, meta: { title: '教师课时统计' } },

      { path: 'campus', name: 'campus', component: Campus, meta: { title: '校区/教室' } },
      { path: 'campus/calendar', name: 'campus-calendar', component: CampusCalendar, meta: { title: '学期/假期设置' } },

    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) return next()
  if (auth.isAuthenticated) return next()
  next({ path: '/login', query: { redirect: to.fullPath || '/' } })
})

export default router
