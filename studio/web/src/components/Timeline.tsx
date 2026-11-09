import { useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { duration, groupWords, type Project } from '../types'

const LABEL_W = 104
const SNAP = 0.22

interface Props {
  project: Project
  time: number
  selected: string | null
  onSelect: (id: string | null) => void
  onSeek: (t: number) => void
  update: (fn: (p: Project) => Project, record?: boolean) => void
}

export default function Timeline({ project: p, time, selected, onSelect, onSeek, update }: Props) {
  const [pxPerSec, setPxPerSec] = useState<number>(() => {
    const saved = localStorage.getItem('studio_timeline_zoom')
    return saved ? Math.max(50, Math.min(300, Number(saved))) : 110
  })
  const [wordMode, setWordMode] = useState<'word' | 'phrase'>(() => {
    return (localStorage.getItem('studio_word_mode') as 'word' | 'phrase') || 'word'
  })

  const changeZoom = (newVal: number) => {
    const clamped = Math.min(300, Math.max(50, Math.round(newVal)))
    setPxPerSec(clamped)
    localStorage.setItem('studio_timeline_zoom', String(clamped))
  }

  const total = Math.max(duration(p), 8)
  const width = total * pxPerSec + 120
  const wrap = useRef<HTMLDivElement>(null)

  // Điểm bắt dính nam châm thông minh: mép các clip (đầu & đuôi), các đoạn thoại, câu, từ
  const snaps = useMemo(() => {
    const s = [0]
    for (const c of p.clips) {
      s.push(c.start)
      s.push(Number((c.start + c.dur).toFixed(3)))
    }
    for (const seg of (p.voice_segments ?? [])) {
      s.push(seg.start)
      s.push(Number((seg.start + seg.dur).toFixed(3)))
    }
    for (const w of p.words) if (/[.!?]$/.test(w.text.trim())) s.push(w.end)
    if (p.words.length) s.push(p.words[p.words.length - 1].end)
    return Array.from(new Set(s)).sort((a, b) => a - b)
  }, [p.clips, p.voice_segments, p.words])

  const snap = (t: number) => {
    let best = t, d = SNAP
    for (const s of snaps) if (Math.abs(s - t) < d) { d = Math.abs(s - t); best = s }
    return best
  }

  // Co dãn toàn bộ dự án vừa khít màn hình
  const fitToScreen = () => {
    if (!wrap.current || total <= 0) return
    const avail = wrap.current.clientWidth - LABEL_W - 40
    if (avail > 80) {
      const target = Math.max(25, Math.min(250, Math.floor(avail / total)))
      changeZoom(target)
    }
  }

  const getTimeFromClientX = (clientX: number) => {
    if (!wrap.current) return 0
    const r = wrap.current.getBoundingClientRect()
    const x = clientX - r.left + wrap.current.scrollLeft - LABEL_W
    const t = Math.max(0, x / pxPerSec)
    return Math.min(t, total)
  }

  // Tua kéo bám sát chuột tức thì (Live Scrubbing)
  const startScrub = (e: React.PointerEvent) => {
    e.stopPropagation()
    e.preventDefault()
    onSeek(getTimeFromClientX(e.clientX))

    const onMove = (ev: PointerEvent) => {
      ev.preventDefault()
      onSeek(getTimeFromClientX(ev.clientX))
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const dragClip = (e: React.PointerEvent, id: string, mode: 'move' | 'resize') => {
    e.stopPropagation(); e.preventDefault()
    onSelect(id)
    const c0 = p.clips.find(c => c.id === id)!
    const x0 = e.clientX
    const move = (ev: PointerEvent) => {
      const dt = (ev.clientX - x0) / pxPerSec
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

  // Kéo dời đoạn thoại (Hỗ trợ từng đoạn voice_segment độc lập)
  const dragVoiceSegment = (e: React.PointerEvent, segId: string) => {
    e.stopPropagation(); e.preventDefault()
    const x0 = e.clientX
    const isMulti = p.voice_segments && p.voice_segments.length > 0
    const seg0 = isMulti
      ? p.voice_segments!.find(s => s.id === segId)
      : { start: p.voice.offset ?? 0, words: p.words }
    if (!seg0) return
    const origStart = seg0.start
    const origWords = seg0.words.map(w => ({ start: w.start, end: w.end }))

    const move = (ev: PointerEvent) => {
      const dt = (ev.clientX - x0) / pxPerSec
      const newStart = Math.max(0, Number((origStart + dt).toFixed(3)))
      const diff = newStart - origStart
      update(prj => {
        if (isMulti) {
          const target = prj.voice_segments?.find(s => s.id === segId)
          if (target) {
            target.start = newStart
            target.words.forEach((w, i) => {
              if (origWords[i]) {
                w.start = Math.max(0, Number((origWords[i].start + diff).toFixed(3)))
                w.end = Math.max(w.start + 0.05, Number((origWords[i].end + diff).toFixed(3)))
              }
            })
            const allW: typeof prj.words = []
            prj.voice_segments?.forEach(s => allW.push(...s.words))
            prj.words = allW.sort((a, b) => a.start - b.start)
          }
        } else {
          prj.voice.offset = newStart
          prj.words.forEach((w, i) => {
            if (origWords[i]) {
              w.start = Math.max(0, Number((origWords[i].start + diff).toFixed(3)))
              w.end = Math.max(w.start + 0.05, Number((origWords[i].end + diff).toFixed(3)))
            }
          })
        }
        return prj
      }, false)
    }

    const up = async () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      update(prj => prj, true)
      if (isMulti) {
        try {
          await api.assembleVoice(p.id)
        } catch { /* ignore */ }
      }
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  // Kéo dời mốc phát BGM
  const dragBgm = (e: React.PointerEvent) => {
    e.stopPropagation(); e.preventDefault()
    const x0 = e.clientX
    const origOffset = p.bgm_offset ?? 0

    const move = (ev: PointerEvent) => {
      const dt = (ev.clientX - x0) / pxPerSec
      const newOffset = Math.max(0, Number((origOffset + dt).toFixed(3)))
      update(prj => {
        prj.bgm_offset = newOffset
        return prj
      }, false)
    }

    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
      update(prj => prj, true)
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }

  const phraseGroups = useMemo(() => {
    return groupWords(p.words, p.caption.max_words || 3)
  }, [p.words, p.caption.max_words])

  const step = pxPerSec >= 160 ? 0.5 : 1
  const ticks = Array.from({ length: Math.ceil(total / step) + 1 }, (_, i) => Number((i * step).toFixed(1)))
  const voiceEnd = p.words.length ? p.words[p.words.length - 1].end : (p.voice.offset ?? 0)

  const segments = (p.voice_segments && p.voice_segments.length > 0)
    ? p.voice_segments
    : (voiceEnd > 0 ? [{
        id: 'legacy_voice',
        text: p.script,
        voice: p.voice.voice,
        engine: p.voice.engine,
        style: p.voice.style,
        speed: p.voice.speed,
        start: p.voice.offset ?? 0,
        dur: voiceEnd - (p.voice.offset ?? 0),
        words: p.words,
      }] : [])

  const videoClips = p.clips.filter(c => (c.track || 'video') === 'video')
  const overlayClips = p.clips.filter(c => c.track === 'overlay')

  const Row = ({ label, children, h = 38 }: { label: React.ReactNode; children: React.ReactNode; h?: number }) => (
    <div className="flex border-b border-white/5" style={{ height: h }}>
      <div className="sticky left-0 z-20 flex shrink-0 items-center bg-zinc-900 px-2.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400 border-r border-white/5" style={{ width: LABEL_W }}>
        {label}
      </div>
      <div className="relative" style={{ width }}>{children}</div>
    </div>
  )

  return (
    <div
      ref={wrap}
      className="relative h-full w-full overflow-x-auto overflow-y-hidden bg-zinc-900/60"
      onClick={() => onSelect(null)}
      onWheel={e => {
        if (e.altKey || e.ctrlKey || e.metaKey) {
          // Ngăn trình duyệt kích hoạt Page Zoom (phóng to trang web)
          e.preventDefault()
          changeZoom(pxPerSec - Math.sign(e.deltaY) * 20)
        } else if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && wrap.current) {
          // Lăn chuột dọc -> tự động cuộn ngang timeline
          wrap.current.scrollLeft += e.deltaY
        }
      }}
    >
      <div style={{ width: width + LABEL_W }}>
        {/* Thước thời gian (Kéo tua chuột bám sát tức thì + Điều khiển Co dãn / Vừa màn hình) */}
        <div
          className="sticky top-0 z-30 flex h-6 cursor-ew-resize border-b border-white/10 bg-zinc-900 select-none"
          onPointerDown={startScrub}
        >
          <div className="sticky left-0 shrink-0 z-30 flex items-center justify-between bg-zinc-900 border-r border-white/10 px-1.5 select-none" style={{ width: LABEL_W }}>
            <button
              onClick={e => { e.stopPropagation(); fitToScreen() }}
              className="rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] font-semibold text-cyan-400 hover:bg-zinc-700 hover:text-cyan-200 border border-cyan-500/30"
              title="Co dãn toàn bộ video vừa khít màn hình (không cần cuộn)"
            >
              ↔ Vừa
            </button>
            <div className="flex items-center gap-0.5">
              <button
                onClick={e => { e.stopPropagation(); changeZoom(pxPerSec - 20) }}
                className="rounded p-0.5 text-[10px] font-bold text-zinc-400 hover:bg-zinc-800 hover:text-white"
                title="Thu nhỏ timeline"
              >
                －
              </button>
              <button
                onClick={e => { e.stopPropagation(); changeZoom(pxPerSec + 20) }}
                className="rounded p-0.5 text-[10px] font-bold text-zinc-400 hover:bg-zinc-800 hover:text-white"
                title="Phóng to timeline (xem rõ từng từ)"
              >
                ＋
              </button>
            </div>
          </div>
          <div className="relative pointer-events-none" style={{ width }}>
            {ticks.map(t => (
              <div key={t} className="absolute top-0 h-full border-l border-white/10 pl-1 text-[10px] text-zinc-500" style={{ left: t * pxPerSec }}>
                {Number.isInteger(t) ? `${t}s` : `${t}`}
              </div>
            ))}
          </div>
        </div>

        {/* Track 1: Video / Ảnh nền */}
        <Row label="🎬 Video nền" h={48}>
          {videoClips.map(c => (
            <div
              key={c.id}
              onPointerDown={e => dragClip(e, c.id, 'move')}
              onClick={e => e.stopPropagation()}
              className={`absolute top-1 flex h-9 cursor-grab items-center overflow-hidden rounded-md px-2 text-[11px] font-medium active:cursor-grabbing ${
                selected === c.id ? 'bg-violet-500 ring-2 ring-violet-300' : 'bg-violet-600/70 hover:bg-violet-600'
              }`}
              style={{ left: c.start * pxPerSec, width: c.dur * pxPerSec }}
              title={c.src}
            >
              <span className="truncate">{c.effect !== 'none' ? `✨ ${c.src.replace('media/', '')}` : c.src.replace('media/', '')}</span>
              <div onPointerDown={e => dragClip(e, c.id, 'resize')} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize bg-white/30" />
            </div>
          ))}
        </Row>

        {/* Track 2: Lớp phủ / Icon / Sticker */}
        <Row label="🎨 Icon/Phủ" h={42}>
          {overlayClips.map(c => (
            <div
              key={c.id}
              onPointerDown={e => dragClip(e, c.id, 'move')}
              onClick={e => e.stopPropagation()}
              className={`absolute top-1 flex h-8 cursor-grab items-center overflow-hidden rounded-md px-2 text-[11px] font-medium active:cursor-grabbing ${
                selected === c.id ? 'bg-amber-400 text-black ring-2 ring-amber-200' : 'bg-amber-600/80 text-white hover:bg-amber-500'
              }`}
              style={{ left: c.start * pxPerSec, width: c.dur * pxPerSec }}
              title={`[Icon] ${c.src}`}
            >
              <span className="truncate font-semibold">★ {c.src.replace('media/', '')}</span>
              <div onPointerDown={e => dragClip(e, c.id, 'resize')} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize bg-white/40" />
            </div>
          ))}
          {!overlayClips.length && (
            <span className="absolute top-2.5 left-3 text-[10px] text-zinc-600 italic">Thêm Icon/Sticker từ cột Media</span>
          )}
        </Row>

        {/* Track 3: Chữ phụ đề */}
        <Row
          label={
            <div className="flex w-full items-center justify-between pr-1">
              <span>💬 Chữ</span>
              <button
                onClick={e => {
                  e.stopPropagation()
                  const next = wordMode === 'word' ? 'phrase' : 'word'
                  setWordMode(next)
                  localStorage.setItem('studio_word_mode', next)
                }}
                className="rounded bg-zinc-800 px-1 py-0.5 text-[9px] font-normal text-cyan-400 hover:bg-zinc-700 hover:text-cyan-300 border border-cyan-500/30"
                title="Chuyển chế độ xem từng từ hoặc cụm câu phụ đề"
              >
                {wordMode === 'word' ? 'từ' : 'cụm'}
              </button>
            </div>
          }
          h={42}
        >
          {wordMode === 'word' ? (
            p.words.map((w, i) => {
              const chipW = Math.max((w.end - w.start) * pxPerSec - 1, 14)
              return (
                <button
                  key={i}
                  onClick={e => {
                    e.stopPropagation()
                    update(prj => { prj.words[i].emph = !prj.words[i].emph; return prj })
                  }}
                  onDoubleClick={e => {
                    e.stopPropagation()
                    const newText = prompt(`Sửa chữ phụ đề "${w.text}":`, w.text)
                    if (newText && newText.trim() && newText.trim() !== w.text) {
                      update(prj => { prj.words[i].text = newText.trim(); return prj }, true)
                    }
                  }}
                  className={`group absolute top-1 h-7 rounded px-1 text-left text-[11px] transition-all whitespace-nowrap z-10 hover:z-30 hover:w-auto hover:min-w-fit hover:px-2 hover:bg-zinc-700 hover:ring-2 hover:ring-cyan-300 hover:shadow-xl ${
                    w.emph ? 'bg-cyan-500/90 font-bold text-black shadow-sm ring-1 ring-cyan-300' : 'bg-zinc-700 text-zinc-200 hover:text-white'
                  }`}
                  style={{ left: w.start * pxPerSec, width: chipW }}
                  title={`"${w.text}" (${w.start.toFixed(2)}s - ${w.end.toFixed(2)}s)\n• Click: Đổi màu nổi bật\n• Nhấp đúp: Sửa lại chữ`}
                >
                  <span className="block truncate group-hover:overflow-visible font-sans leading-5">
                    {w.text}
                  </span>
                </button>
              )
            })
          ) : (
            phraseGroups.map((grp, gIdx) => (
              <div
                key={gIdx}
                className="absolute top-1 flex h-7 items-center gap-1 rounded-md bg-zinc-800/95 px-2 py-0.5 text-[11px] ring-1 ring-white/10 shadow-sm overflow-hidden"
                style={{ left: grp.start * pxPerSec, width: Math.max((grp.end - grp.start) * pxPerSec, 60) }}
                title={`Cụm #${gIdx + 1}: ${grp.words.map(w => w.text).join(' ')}`}
              >
                {grp.words.map((w, wIdx) => {
                  const globalIdx = p.words.indexOf(w)
                  return (
                    <button
                      key={wIdx}
                      onClick={e => {
                        e.stopPropagation()
                        if (globalIdx >= 0) {
                          update(prj => { prj.words[globalIdx].emph = !prj.words[globalIdx].emph; return prj })
                        }
                      }}
                      className={`rounded px-1 py-0.5 text-[11px] transition shrink-0 ${
                        w.emph ? 'bg-cyan-400 font-bold text-black' : 'text-zinc-200 hover:bg-zinc-700 hover:text-white'
                      }`}
                      title="Click để đổi màu nổi bật"
                    >
                      {w.text}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </Row>

        {/* Track 4: Giọng (Hỗ trợ Nhiều đoạn giọng độc lập, kéo dời từng đoạn) */}
        <Row label="🎙️ Giọng" h={38}>
          {segments.map((seg, idx) => {
            const segStart = seg.start
            const segDur = Math.max(seg.dur || (seg.words.length ? seg.words[seg.words.length - 1].end - seg.start : 2.0), 0.5)
            const segWidth = segDur * pxPerSec
            const speakerName = seg.voice.split('】')[1] || seg.voice
            return (
              <div
                key={seg.id}
                onPointerDown={e => dragVoiceSegment(e, seg.id)}
                className="group absolute top-1 flex h-7 cursor-grab items-center rounded-md bg-emerald-600/85 px-2 text-[11px] font-medium text-emerald-100 hover:bg-emerald-600 active:cursor-grabbing ring-1 ring-emerald-400/40 overflow-hidden shadow-sm"
                style={{ left: segStart * pxPerSec, width: Math.max(segWidth, 50) }}
                title={`Đoạn #${idx + 1} [${speakerName}]: ${seg.text}`}
              >
                <div className="flex items-center gap-1.5 min-w-0 pointer-events-none">
                  <span className="shrink-0 font-bold text-amber-200">🗣️ #{idx + 1} {speakerName}</span>
                  <span className="truncate opacity-75 text-[10px]">{seg.text}</span>
                </div>
                <div className="absolute inset-0 opacity-15 pointer-events-none border-y border-dashed border-white/50" />
              </div>
            )
          })}
        </Row>

        {/* Track 5: Nhạc nền BGM (KÉO DỜI ĐƯỢC) */}
        <Row label="🎵 Nhạc BGM" h={36}>
          {p.bgm_file ? (
            <div
              onPointerDown={dragBgm}
              className="absolute top-1 flex h-7 cursor-grab items-center rounded-md bg-indigo-600/80 px-2 text-[11px] font-medium text-indigo-100 hover:bg-indigo-600 active:cursor-grabbing ring-1 ring-indigo-400/30"
              style={{ left: (p.bgm_offset ?? 0) * pxPerSec, width: Math.max(total * pxPerSec * 0.8, 120) }}
              title={`Nhạc nền (Âm lượng: ${Math.round((p.bgm_volume ?? 0.25) * 100)}%). Kéo chuột để dời mốc phát.`}
            >
              <span className="truncate">🎶 {p.bgm_file.replace('media/', '')} ({Math.round((p.bgm_volume ?? 0.25) * 100)}%)</span>
              <div className="absolute inset-0 opacity-15 pointer-events-none border-y border-dashed border-white/50" />
            </div>
          ) : (
            <span className="absolute top-2 left-3 text-[10px] text-zinc-600 italic">Chưa có nhạc nền (Thêm ở tab Nhạc BGM)</span>
          )}
        </Row>

        {/* Con trỏ thời gian (Kéo trực tiếp đầu kim đỏ) */}
        <div className="pointer-events-none absolute top-0 z-40 h-full w-px bg-rose-500" style={{ left: LABEL_W + time * pxPerSec }}>
          <div
            onPointerDown={startScrub}
            className="pointer-events-auto -ml-2 -mt-0.5 flex h-6 w-4 cursor-ew-resize items-start justify-center group"
            title="Kéo để tua video bám sát chuột"
          >
            <div className="-ml-0.5 h-3.5 w-3.5 rounded-sm bg-rose-500 shadow-lg group-hover:scale-125 transition-transform" />
          </div>
        </div>
      </div>
    </div>
  )
}
