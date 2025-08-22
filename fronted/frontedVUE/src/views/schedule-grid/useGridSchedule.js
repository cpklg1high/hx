// src/views/schedule-grid/useGridSchedule.js

export function useGridSchedule() {
  // 把后端 lesson 列表标准化为绘制需要的结构
  function normalizeLessons(list, dayStartMinutes = 420 /*07:00*/) {
    return list.map(it => {
      const [sh, sm] = (it.start_time || '00:00:00').split(':').map(n => parseInt(n, 10))
      const [eh, em] = (it.end_time   || '00:00:00').split(':').map(n => parseInt(n, 10))
      const startMin = sh * 60 + sm
      const endMin   = eh * 60 + em
      const y = (startMin - dayStartMinutes) * 1   // pxPerMin 由组件再乘
      const h = Math.max(1, endMin - startMin)     // 分钟
      return {
        // 基本字段
        id: String(it.id),
        raw: it,
        colKey: `grade:${it.grade}`, // 年级列键
        date: it.date,
        start_time: it.start_time,
        end_time: it.end_time,
        duration: it.duration,
        subject: it.subject,
        course_mode: it.course_mode,
        teacher: it.teacher,
        room: it.room,
        enrolled: it.enrolled,
        capacity: it.capacity,
        status: it.status,
        grade: it.grade,
        // 几何（初值，后面 layout 填充）
        y,
        h,           // 分钟单位（真正 px 由组件用 pxPerMin 转）
        leftPct: 0,
        widthPct: 100
      }
    })
  }

  // 生成年级列（按当前 Tab 的年级集合）
  function buildGradeColumns(lessons, allGrades) {
    const used = new Set(lessons.map(x => x.grade))
    const map = new Map(allGrades.map(g => [g.id, g.name]))
    const cols = Array.from(used).sort((a,b)=>a-b).map(gid => ({
      key: `grade:${gid}`,
      label: map.get(gid) || `年级${gid}`,
      grade: gid
    }))
    return cols
  }

  return { normalizeLessons, buildGradeColumns }
}
