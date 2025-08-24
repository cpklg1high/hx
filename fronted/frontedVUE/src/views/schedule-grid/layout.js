// src/views/schedule-grid/layout.js

/**
 * 对每列事件做并发布局，返回带 leftPct/widthPct/y/h 的事件数组
 * cfg: { dayStart, pxPerMin }
 */
export function layoutByColumns(events, columns, cfg) {
  const byCol = new Map()
  for (const col of columns) byCol.set(col.key, [])
  for (const ev of events) {
    if (!byCol.has(ev.colKey)) byCol.set(ev.colKey, [])
    byCol.get(ev.colKey).push(ev)
  }

  const result = []
  for (const col of columns) {
    const list = byCol.get(col.key) || []
    list.sort((a,b) => (a.date === b.date ? (a.start_time.localeCompare(b.start_time)) : (a.date.localeCompare(b.date))))

    // 同列内做贪心分道
    const laid = layoutLanes(list)
    // 写入像素值
    for (const ev of laid) {
      const yPx = Math.max(0, (minutesSinceStart(ev.start_time, cfg.dayStart) * cfg.pxPerMin))
      const hPx = Math.max(12, ev.h * cfg.pxPerMin) // 最小高度 12px
      result.push({ ...ev, y: yPx, h: hPx })
    }
  }
  return result
}

// 计算从 dayStart 起的分钟数
function minutesSinceStart(hhmmss, dayStart) {
  const [h,m] = (hhmmss || '00:00:00').split(':').map(n=>parseInt(n,10))
  return h*60 + m - dayStart
}

// 单列内分道：返回每个事件的 lane 与同簇最大道数，继而折算为 left/width 百分比
function layoutLanes(list) {
  // 每个日期单独处理，避免跨日错误
  const byDate = new Map()
  for (const ev of list) {
    if (!byDate.has(ev.date)) byDate.set(ev.date, [])
    byDate.get(ev.date).push(ev)
  }

  const out = []
  for (const [date, arr] of byDate.entries()) {
    arr.sort((a,b)=> a.start_time.localeCompare(b.start_time))

    // 最小堆替代：用 lanes 数组存每道的最后结束时间
    let lanesEnd = []   // 每道的 end_time 字符串
    let lanes = []      // 对应的事件数组

    function timeLE(a,b){ return a <= b } // 字符串比较即可（"HH:MM:SS"）

    // 为每个事件分配 lane
    for (const ev of arr) {
      let placed = false
      for (let i=0;i<lanesEnd.length;i++){
        if (timeLE(lanesEnd[i], ev.start_time)) {
          // 放到第 i 道
          lanes[i].push(ev); lanesEnd[i] = ev.end_time; placed = true; ev._lane = i; break
        }
      }
      if (!placed) {
        lanesEnd.push(ev.end_time); lanes.push([ev]); ev._lane = lanesEnd.length - 1
      }
    }

    // 以“重叠簇”为单位计算 maxLanes，再转成百分比
    // 简化处理：这里直接使用总 lanes 数作为并排宽度（对同日同一时间段足够）
    const maxLanes = lanes.length || 1
    const gapPct = 2 // 百分比间距（总列宽的 2%）
    const widthPct = (100 - (maxLanes - 1) * gapPct) / maxLanes

    for (const ev of arr) {
      ev.leftPct = ev._lane * (widthPct + gapPct)
      ev.widthPct = widthPct
      out.push(ev)
    }
  }
  return out
}
