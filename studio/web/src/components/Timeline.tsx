import { useMemo, useRef } from 'react'
import { duration, type Project } from '../types'

const PX = 90 // px mỗi giây
const LABEL_W = 90
const SNAP = 0.12

interface Props {
  project: Project
  time: number
  selected: string | null
  onSelect: (id: string | null) => void
  onSeek: (t: number) => void
  update: (fn: (p: Project) => Project, record?: boolean) => void
}

export default function Timeline({ project: p, time, selected, onSelect, onSeek, update }: Props) {
  const total = Math.max(duration(p), 8)
  const width = total * PX + 80
  const wrap = useRef<HTMLDivElement>(null)

  // điểm bắt dính: 0, hết mỗi câu, hết giọng
  const snaps = useMemo(() => {
    const s = [0]
    for (const w of p.words) if (/[.!?]$/.test(w.text.trim())) s.push(w.end)
    if (p.words.length) s.push(p.words[p.words.length - 1].end)
    return s
  }, [p.words])
  const snap = (t: number) => {
    let best = t, d = SNAP
    for (const s of snaps) if (Math.abs(s - t) < d) { d = Math.abs(s - t); best = s }
    return best
  }

  const seekFromEvent = (e: React.MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect()
    onSeek(Math.max(0, (e.clientX - r.left + wrap.current!.scrollLeft - LABEL_W) / PX))
  }

  const drag = (e: React.PointerEvent, id: string, mode: 'move' | 'resize') => {
    e.stopPropagation(); e.preventDefault()
    onSelect(id)
    const c0 = p.clips.find(c => c.id === id)!
    const x0 = e.clientX
    const move = (ev: PointerEvent) => {
      const dt = (ev.clientX - x0) / PX
      update(prj => {
        const c = prj.clips.find(c => c.id === id)!
        if (mode === 'move') {
          const s = Math.max(0, c0.start + dt)
          const a = snap(s), b = snap(s + c0.dur) - c0.dur
          c.start = Math.max(0, Math.abs(a - s) <= Math.abs(b - s) ? a : b)
        } else {
          c.dur = Math.max(0.2, snap(c0.start + c0.dur + dt) - c0.start)
        }
        return prj
      }, false)
    }
    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
      update(prj => prj, true) // chốt 1 bước undo
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }

  const ticks = Array.from({ length: Math.ceil(total) + 1 }, (_, i) => i)
  const voiceEnd = p.words.length ? p.words[p.words.length - 1].end : 0
  const videoClips = p.clips.filter(c => (c.track || 'video') === 'video')
  const overlayClips = p.clips.filter(c => c.track === 'overlay')

  const Row = ({ label, children, h = 38 }: { label: string; children: React.ReactNode; h?: number }) => (
    <div className="flex border-b border-white/5" style={{ height: h }}>
      <div className="sticky left-0 z-20 flex shrink-0 items-center bg-zinc-900 px-2.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400" style={{ width: LABEL_W }}>{label}</div>
      <div className="relative" style={{ width }}>{children}</div>
    </div>
  )

  return (
    <div ref={wrap} className="relative h-full overflow-auto bg-zinc-900/60" onClick={() => onSelect(null)}>
      <div style={{ width: width + LABEL_W }}>
        <div className="sticky top-0 z-30 flex h-6 cursor-pointer border-b border-white/10 bg-zinc-900" onClick={e => { e.stopPropagation(); seekFromEvent(e) }}>
          <div className="sticky left-0 shrink-0 bg-zinc-900" style={{ width: LABEL_W }} />
          <div className="relative" style={{ width }}>
            {ticks.map(t => (
              <div key={t} className="absolute top-0 h-full border-l border-white/10 pl-1 text-[10px] text-zinc-500" style={{ left: t * PX }}>{t}s</div>
            ))}
          </div>
        </div>

        {/* Track 1: Video / Ảnh nền */}
        <Row label="🎬 Video nền" h={48}>
          {videoClips.map(c => (
            <div
              key={c.id}
              onPointerDown={e => drag(e, c.id, 'move')}
              onClick={e => e.stopPropagation()}
              className={`absolute top-1 flex h-9 cursor-grab items-center overflow-hidden rounded-md px-2 text-[11px] font-medium active:cursor-grabbing ${
                selected === c.id ? 'bg-violet-500 ring-2 ring-violet-300' : 'bg-violet-600/70 hover:bg-violet-600'
              }`}
              style={{ left: c.start * PX, width: c.dur * PX }}
              title={c.src}
            >
              <span className="truncate">{c.effect !== 'none' ? `✨ ${c.src.replace('media/', '')}` : c.src.replace('media/', '')}</span>
              <div onPointerDown={e => drag(e, c.id, 'resize')} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize bg-white/30" />
            </div>
          ))}
        </Row>

        {/* Track 2: Lớp phủ / Icon / Sticker */}
        <Row label="🎨 Icon/Lớp phủ" h={42}>
          {overlayClips.map(c => (
            <div
              key={c.id}
              onPointerDown={e => drag(e, c.id, 'move')}
              onClick={e => e.stopPropagation()}
              className={`absolute top-1 flex h-8 cursor-grab items-center overflow-hidden rounded-md px-2 text-[11px] font-medium active:cursor-grabbing ${
                selected === c.id ? 'bg-amber-400 text-black ring-2 ring-amber-200' : 'bg-amber-600/80 text-white hover:bg-amber-500'
              }`}
              style={{ left: c.start * PX, width: c.dur * PX }}
              title={`[Icon] ${c.src}`}
            >
              <span className="truncate font-semibold">★ {c.src.replace('media/', '')}</span>
              <div onPointerDown={e => drag(e, c.id, 'resize')} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize bg-white/40" />
            </div>
          ))}
          {!overlayClips.length && (
            <span className="absolute top-2 left-3 text-[10px] text-zinc-600 italic">Thêm Icon/Sticker từ cột Media</span>
          )}
        </Row>

        {/* Track 3: Chữ */}
        <Row label="💬 Chữ" h={38}>
          {p.words.map((w, i) => (
            <button
              key={i}
              onClick={e => { e.stopPropagation(); update(prj => { prj.words[i].emph = !prj.words[i].emph; return prj }) }}
              className={`absolute top-1 h-7 overflow-hidden rounded px-1 text-left text-[11px] ${
                w.emph ? 'bg-cyan-500/80 font-bold text-black' : 'bg-zinc-700 text-zinc-200 hover:bg-zinc-600'
              }`}
              style={{ left: w.start * PX, width: Math.max((w.end - w.start) * PX - 1, 6) }}
              title="Click để đổi màu từ khóa nổi bật"
            >{w.text}</button>
          ))}
        </Row>

        {/* Track 4: Giọng */}
        <Row label="🎙️ Giọng" h={34}>
          {voiceEnd > 0 && (
            <div className="absolute top-1 h-6 rounded-md bg-emerald-600/60" style={{ left: 0, width: voiceEnd * PX }}>
              <div className="h-full w-full opacity-40" style={{ backgroundImage: 'repeating-linear-gradient(90deg,#fff 0 2px,transparent 2px 6px)', maskImage: 'linear-gradient(transparent 25%,#000 25%,#000 75%,transparent 75%)' }} />
            </div>
          )}
        </Row>

        <div className="pointer-events-none absolute top-0 z-40 h-full w-px bg-rose-500" style={{ left: LABEL_W + time * PX }}>
          <div className="-ml-1.5 h-3 w-3 rounded-sm bg-rose-500" />
        </div>
      </div>
    </div>
  )
}
