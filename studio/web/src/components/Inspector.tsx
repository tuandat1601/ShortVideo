import type { ReactNode } from 'react'
import type { Meta, Project } from '../types'

interface Props {
  project: Project
  meta: Meta | null
  selectedClip: string | null
  update: (fn: (p: Project) => Project, record?: boolean) => void
  onOpenCrop?: (clipId: string) => void
}

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <label className="mb-3 block">
    <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">{label}</span>
    {children}
  </label>
)
const input = 'w-full rounded-md border border-white/10 bg-zinc-800 px-2 py-1.5 text-sm outline-none focus:border-violet-500'

export default function Inspector({ project: p, meta, selectedClip, update, onOpenCrop }: Props) {
  const c = p.clips.find(x => x.id === selectedClip)
  const cap = p.caption
  const setCap = <K extends keyof Project['caption']>(k: K, v: Project['caption'][K]) =>
    update(prj => { prj.caption[k] = v; return prj })

  const setPos = (x: number, y: number) => {
    if (!c) return
    update(prj => {
      const target = prj.clips.find(clip => clip.id === c.id)
      if (target) { target.x_pct = x; target.y_pct = y }
      return prj
    })
  }

  return (
    <div className="h-full overflow-y-auto p-4 text-sm">
      {c ? (
        <>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-violet-400">
              {c.track === 'overlay' ? '🎨 Lớp phủ / Icon' : '🎬 Clip đang chọn'}
            </h3>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${c.track === 'overlay' ? 'bg-amber-500/20 text-amber-300' : 'bg-violet-500/20 text-violet-300'}`}>
              {c.track === 'overlay' ? 'Lớp phủ' : 'Video nền'}
            </span>
          </div>

          <div className="mb-3 truncate rounded bg-zinc-800 px-2 py-1.5 text-xs text-zinc-300">{c.src}</div>

          {/* Chọn loại track */}
          <Field label="Loại Track">
            <select
              className={input}
              value={c.track || 'video'}
              onChange={e => update(prj => {
                const target = prj.clips.find(x => x.id === c.id)!
                target.track = e.target.value as 'video' | 'overlay'
                if (target.track === 'overlay') {
                  target.x_pct = target.x_pct ?? 50
                  target.y_pct = target.y_pct ?? 30
                  target.scale_pct = target.scale_pct ?? 35
                }
                return prj
              })}
            >
              <option value="video">Video nền (Track Video)</option>
              <option value="overlay">Lớp phủ / Icon / Sticker (Track Overlay)</option>
            </select>
          </Field>

          {/* Hiệu ứng chuyển động / animation */}
          <Field label="✨ Hiệu ứng (Effects / Animation)">
            <select
              className={input}
              value={c.effect || 'none'}
              onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.effect = e.target.value as any; return prj })}
            >
              <option value="none">Không có hiệu ứng</option>
              <option value="spotlight">🎯 Tiêu điểm cmt / Spotlight (Tối mờ nền)</option>
              <option value="dim_blur">🌫️ Mờ & Tối nền (Dim & Blur background)</option>
              <option value="zoom_in">🔍 Zoom vào chậm (Ken Burns)</option>
              <option value="zoom_out">🔎 Zoom ra chậm</option>
              <option value="flash">⚡ Chớp sáng trắng (Flash)</option>
              <option value="fade">🌫️ Mờ dần vào (Fade in)</option>
            </select>
          </Field>

          {/* Nếu là Icon / Lớp phủ -> Hiện chỉnh vị trí & kích thước & thứ tự lớp đè */}
          {c.track === 'overlay' && (
            <div className="my-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
              <span className="mb-2 block text-xs font-semibold text-amber-300">Vị trí & Kích thước Icon</span>
              <label className="mb-3 flex items-center gap-2 text-xs font-medium text-amber-200 cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-amber-500 rounded"
                  checked={c.dim_bg || c.effect === 'spotlight'}
                  onChange={e => update(prj => {
                    const target = prj.clips.find(x => x.id === c.id)!
                    target.dim_bg = e.target.checked
                    return prj
                  })}
                />
                🎯 Làm tối mờ nền phía sau (Spotlight Focus)
              </label>

              {/* Thứ tự lớp đè (Z-Index) */}
              <div className="mb-3 rounded-md bg-zinc-900/80 p-2 border border-white/5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] font-semibold text-zinc-300">Thứ tự lớp đè:</span>
                  <span className="rounded bg-amber-400/20 px-1.5 py-0.5 text-[10px] font-mono text-amber-300">
                    Lớp #{c.z_order ?? 0}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    type="button"
                    onClick={() => update(prj => {
                      const target = prj.clips.find(x => x.id === c.id)!
                      target.z_order = (target.z_order ?? 0) + 1
                      return prj
                    })}
                    className="flex items-center justify-center gap-1 rounded bg-zinc-800 py-1 text-xs text-zinc-200 hover:bg-amber-600 hover:text-white transition"
                    title="Đưa icon này đè lên trên các icon khác"
                  >
                    ⬆️ Đè lên trên
                  </button>
                  <button
                    type="button"
                    onClick={() => update(prj => {
                      const target = prj.clips.find(x => x.id === c.id)!
                      target.z_order = Math.max(0, (target.z_order ?? 0) - 1)
                      return prj
                    })}
                    className="flex items-center justify-center gap-1 rounded bg-zinc-800 py-1 text-xs text-zinc-200 hover:bg-zinc-700 transition"
                    title="Hạ icon này nằm dưới các icon khác"
                  >
                    ⬇️ Nằm bên dưới
                  </button>
                </div>
              </div>

              <Field label={`Kích thước icon (${c.scale_pct || 35}%)`}>
                <input
                  type="range" min={15} max={90} className="w-full accent-amber-500"
                  value={c.scale_pct || 35}
                  onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.scale_pct = +e.target.value; return prj })}
                />
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label={`Vị trí X (${c.x_pct || 50}%)`}>
                  <input
                    type="range" min={10} max={90} className="w-full accent-amber-500"
                    value={c.x_pct || 50}
                    onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.x_pct = +e.target.value; return prj })}
                  />
                </Field>
                <Field label={`Vị trí Y (${c.y_pct || 30}%)`}>
                  <input
                    type="range" min={10} max={90} className="w-full accent-amber-500"
                    value={c.y_pct || 30}
                    onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.y_pct = +e.target.value; return prj })}
                  />
                </Field>
              </div>
              <span className="mb-1 block text-[10px] text-zinc-400">Vị trí nhanh:</span>
              <div className="grid grid-cols-3 gap-1 text-[10px]">
                <button type="button" onClick={() => setPos(25, 20)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Góc trên T</button>
                <button type="button" onClick={() => setPos(50, 25)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Trên giữa</button>
                <button type="button" onClick={() => setPos(75, 20)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Góc trên P</button>
                <button type="button" onClick={() => setPos(25, 75)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Góc dưới T</button>
                <button type="button" onClick={() => setPos(50, 50)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Chính giữa</button>
                <button type="button" onClick={() => setPos(75, 75)} className="rounded bg-zinc-800 py-1 hover:bg-zinc-700">Góc dưới P</button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Field label={`Bắt đầu (${c.start.toFixed(2)}s)`}>
              <input type="number" step="0.1" className={input} value={c.start}
                onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.start = Math.max(0, +e.target.value); return prj })} />
            </Field>
            <Field label={`Độ dài (${c.dur.toFixed(2)}s)`}>
              <input type="number" step="0.1" className={input} value={c.dur}
                onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.dur = Math.max(0.2, +e.target.value); return prj })} />
            </Field>
          </div>

          <Field label="Cắt từ giây (video)">
            <input type="number" step="0.1" className={input} value={c.in_point}
              onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.in_point = Math.max(0, +e.target.value); return prj })} />
          </Field>

          {c.track !== 'overlay' && (
            <Field label="Khung hình (Fit)">
              <select className={input} value={c.fit}
                onChange={e => update(prj => { prj.clips.find(x => x.id === c.id)!.fit = e.target.value as 'cover'; return prj })}>
                <option value="cover">Phủ kín (Cắt góc 9:16)</option>
                <option value="contain_blur">Giữ nguyên + nền mờ (Contain blur)</option>
              </select>
            </Field>
          )}

          {/* Căn góc quay màn hình / Reframe 9:16 */}
          {c.track !== 'overlay' && c.fit === 'cover' && (
            <div className="mb-4 rounded-xl border border-violet-500/30 bg-violet-950/20 p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-violet-300 flex items-center gap-1.5">
                  <span>📐</span> Căn góc 9:16 (Quay màn hình)
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">
                  {c.crop_x ?? 50}% X
                </span>
              </div>

              <button
                type="button"
                onClick={() => onOpenCrop?.(c.id)}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-600 py-2 text-xs font-bold text-white hover:from-violet-500 hover:to-fuchsia-500 shadow-md shadow-violet-950/40 transition active:scale-95"
              >
                <span>🔍 Mở bảng Cắt góc trực quan</span>
              </button>

              <div className="grid grid-cols-3 gap-1 pt-1 text-[10px]">
                <button
                  type="button"
                  onClick={() => update(prj => {
                    const target = prj.clips.find(x => x.id === c.id)!
                    target.crop_x = 0; target.crop_y = 50
                    return prj
                  })}
                  className={`rounded py-1 font-medium transition ${(c.crop_x ?? 50) <= 5 ? 'bg-violet-600 text-white' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ⬅️ Trái (Code)
                </button>
                <button
                  type="button"
                  onClick={() => update(prj => {
                    const target = prj.clips.find(x => x.id === c.id)!
                    target.crop_x = 50; target.crop_y = 50
                    return prj
                  })}
                  className={`rounded py-1 font-medium transition ${(c.crop_x ?? 50) > 40 && (c.crop_x ?? 50) < 60 ? 'bg-violet-600 text-white' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ⏺️ Ở Giữa
                </button>
                <button
                  type="button"
                  onClick={() => update(prj => {
                    const target = prj.clips.find(x => x.id === c.id)!
                    target.crop_x = 100; target.crop_y = 50
                    return prj
                  })}
                  className={`rounded py-1 font-medium transition ${(c.crop_x ?? 50) >= 95 ? 'bg-violet-600 text-white' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ➡️ Phải (Web)
                </button>
              </div>

              <div className="space-y-1 pt-1">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>Trục ngang (X): {c.crop_x ?? 50}%</span>
                  <span>Zoom: {c.crop_scale ?? 100}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={c.crop_x ?? 50}
                  onChange={e => update(prj => {
                    prj.clips.find(x => x.id === c.id)!.crop_x = +e.target.value
                    return prj
                  })}
                  className="w-full accent-violet-500"
                />
              </div>
            </div>
          )}

          <button className="w-full rounded-md bg-rose-600/80 py-1.5 text-xs font-medium hover:bg-rose-600"
            onClick={() => update(prj => { prj.clips = prj.clips.filter(x => x.id !== c.id); return prj })}>
            Xóa {c.track === 'overlay' ? 'Icon' : 'Clip'}
          </button>
          <hr className="my-5 border-white/10" />
        </>
      ) : null}

      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-violet-400">Chữ (caption)</h3>
      <Field label="Font">
        <select className={input} value={cap.font} onChange={e => setCap('font', e.target.value)}>
          {(meta?.fonts ?? [cap.font]).map(f => <option key={f}>{f}</option>)}
        </select>
      </Field>
      <Field label={`Cỡ chữ ${cap.size}px`}>
        <input type="range" min={40} max={220} className="w-full accent-violet-500" value={cap.size} onChange={e => setCap('size', +e.target.value)} />
      </Field>
      <Field label={`Viền ${cap.stroke_width}px`}>
        <input type="range" min={0} max={24} className="w-full accent-violet-500" value={cap.stroke_width} onChange={e => setCap('stroke_width', +e.target.value)} />
      </Field>
      <Field label={`Vị trí dọc ${cap.y_pct}%`}>
        <input type="range" min={10} max={90} className="w-full accent-violet-500" value={cap.y_pct} onChange={e => setCap('y_pct', +e.target.value)} />
      </Field>
      <Field label="Số từ hiện cùng lúc">
        <div className="flex gap-1">
          {[1, 2, 3, 4].map(n => (
            <button key={n} onClick={() => setCap('max_words', n)}
              className={`flex-1 rounded-md py-1.5 text-sm ${cap.max_words === n ? 'bg-violet-600' : 'bg-zinc-800 hover:bg-zinc-700'}`}>{n}</button>
          ))}
        </div>
      </Field>
      <div className="mb-3 flex gap-3">
        <Field label="Màu chữ"><input type="color" className="h-8 w-full cursor-pointer rounded bg-transparent" value={cap.color} onChange={e => setCap('color', e.target.value)} /></Field>
        <Field label="Từ khóa"><input type="color" className="h-8 w-full cursor-pointer rounded bg-transparent" value={cap.emph_color} onChange={e => setCap('emph_color', e.target.value)} /></Field>
        <Field label="Viền"><input type="color" className="h-8 w-full cursor-pointer rounded bg-transparent" value={cap.stroke_color} onChange={e => setCap('stroke_color', e.target.value)} /></Field>
      </div>
      <label className="mb-3 flex items-center gap-2 text-sm text-zinc-300">
        <input type="checkbox" className="accent-violet-500" checked={cap.uppercase} onChange={e => setCap('uppercase', e.target.checked)} /> VIẾT HOA
      </label>
      <Field label="Màu nền video">
        <input type="color" className="h-8 w-full cursor-pointer rounded bg-transparent" value={p.bg_color}
          onChange={e => update(prj => { prj.bg_color = e.target.value; return prj })} />
      </Field>
    </div>
  )
}
