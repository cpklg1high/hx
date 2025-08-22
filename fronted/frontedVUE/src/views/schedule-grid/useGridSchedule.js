// 路径：src/views/schedule-grid/useGridSchedule.js
export function useGridSchedule() {
  /**
   * 把后端 lesson 变为统一的轻量对象（不绑定列键，列键在后面按视图挂接）
   */
  function normalizeLessons(list, dayStartMinutes = 420) {
    return list.map(it => {
      const [sh, sm] = (it.start_time || '00:00:00').split(':').map(n => parseInt(n,10))
      const [eh, em] = (it.end_time   || '00:00:00').split(':').map(n => parseInt(n,10))
      const startMin = sh*60 + sm, endMin = eh*60 + em
      const h = Math.max(1, endMin - startMin)
      return {
        id: String(it.id),
        raw: it,           // 原始对象（用于抽屉）
        // 基础维度
        date: it.date,
        start_time: it.start_time,
        end_time: it.end_time,
        duration: it.duration,
        subject: it.subject,
        course_mode: it.course_mode,
        teacher: it.teacher,
        teacher_id: it.teacher_id,   // <—— 请确保后端 listLessons 返回（若没有，前端也能显示 teacher 名称）
        room: it.room,
        enrolled: it.enrolled,
        capacity: it.capacity,
        status: it.status,
        grade: it.grade,
        // 布局尺寸
        y: (startMin - dayStartMinutes),
        h,
        // 列布局（稍后按视图赋值）
        colKey: '',
        leftPct: 0,
        widthPct: 100,
      }
    })
  }

  /**
   * 年级列集合（只取当前周内出现过的年级，按 id 升序）
   */
  function buildGradeColumns(lessons, allGrades) {
    const used = new Set(lessons.map(x => x.grade))
    const nameMap = new Map(allGrades.map(g => [g.id, g.name]))
    return Array.from(used).sort((a,b)=>a-b).map(gid => ({
      key: `grade:${gid}`,
      label: nameMap.get(gid) || `年级${gid}`,
      type: 'grade',
      value: gid,
    }))
  }

  /**
   * 老师列集合（只取当前周内出现过的老师，按名称排序）
   * 需要后端 listLessons 在每条课里含 teacher 与 teacher_id（若没有 id，就先用名称聚合）
   */
  function buildTeacherColumns(lessons) {
    const map = new Map()
    for (const x of lessons) {
      const key = (x.teacher_id != null) ? `teacher:${x.teacher_id}` : `teacher:${x.teacher}`
      if (!map.has(key)) {
        map.set(key, {
          key,
          label: x.teacher || '未指定老师',
          type: 'teacher',
          value: (x.teacher_id != null) ? x.teacher_id : x.teacher,
        })
      }
    }
    return Array.from(map.values()).sort((a,b)=> String(a.label).localeCompare(String(b.label)))
  }

  /**
   * 根据当前视图给每个事件挂接 colKey
   * viewMode: 'grade' | 'teacher'
   */
  function attachColKey(events, columns, viewMode) {
    if (viewMode === 'grade') {
      for (const ev of events) ev.colKey = `grade:${ev.grade}`
    } else {
      for (const ev of events) {
        const key = (ev.teacher_id != null) ? `teacher:${ev.teacher_id}` : `teacher:${ev.teacher}`
        ev.colKey = key
      }
    }
    // 只保留落在本视图列集合中的事件（避免孤儿事件）
    const allow = new Set(columns.map(c => c.key))
    return events.filter(e => allow.has(e.colKey))
  }

  return { normalizeLessons, buildGradeColumns, buildTeacherColumns, attachColKey }
}
