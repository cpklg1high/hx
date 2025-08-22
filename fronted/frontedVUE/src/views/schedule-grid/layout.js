// 路径：src/views/schedule-grid/layout.js
export function layoutByColumns(events, columns, cfg) {
  const byCol = new Map(); for (const c of columns) byCol.set(c.key, [])
  for (const e of events) (byCol.get(e.colKey) || byCol.set(e.colKey, []).get(e.colKey)).push(e)

  const out = []
  for (const col of columns) {
    const list = (byCol.get(col.key) || []).slice().sort((a,b)=> a.date===b.date ? a.start_time.localeCompare(b.start_time) : a.date.localeCompare(b.date))
    const laid = layoutLanes(list)
    for (const ev of laid) {
      const yPx = Math.max(0, (minutesSinceStart(ev.start_time, cfg.dayStart) * cfg.pxPerMin))
      const hPx = Math.max(12, ev.h * cfg.pxPerMin)
      out.push({ ...ev, y: yPx, h: hPx })
    }
  }
  return out
}
function minutesSinceStart(hhmmss, dayStart) { const [h,m]= (hhmmss||'00:00:00').split(':').map(n=>parseInt(n,10)); return h*60 + m - dayStart }
function layoutLanes(list) {
  const byDate = new Map(); for (const ev of list) (byDate.get(ev.date) || byDate.set(ev.date,[]).get(ev.date)).push(ev)
  const out = []
  for (const [, arr] of byDate.entries()) {
    arr.sort((a,b)=> a.start_time.localeCompare(b.start_time))
    let lanesEnd=[], lanes=[]
    for (const ev of arr) {
      let placed=false
      for (let i=0;i<lanesEnd.length;i++){
        if (lanesEnd[i] <= ev.start_time) { lanes[i].push(ev); lanesEnd[i]=ev.end_time; ev._lane=i; placed=true; break }
      }
      if (!placed){ lanesEnd.push(ev.end_time); lanes.push([ev]); ev._lane=lanesEnd.length-1 }
    }
    const maxLanes = lanes.length || 1
    const gapPct = (maxLanes > 1) ? 2 : 0    // 只有多车道时才加列间距
    const widthPct=(100-(maxLanes-1)*gapPct)/maxLanes
    for (const ev of arr){ ev.leftPct = ev._lane*(widthPct+gapPct); ev.widthPct=widthPct; out.push(ev) }
  }
  return out
}
