import type { ReactNode } from 'react'
import { isVideo, type Meta, type Project } from '../types'

interface Props {
  project: Project
  meta: Meta | null
  selectedClip: string | null
  update: (fn: (p: Project) => Project, record?: boolean) => void
  onOpenCrop?: (clipId: string) => void
  onSplit?: (clipId?: string) => void
}

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <label className="mb-3 block">
    <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">{label}</span>
    {children}
  </label>
)
const input = 'w-full rounded-md border border-white/10 bg-zinc-800 px-2 py-1.5 text-sm outline-none focus:border-violet-500'

export default function Inspector({ project: p, meta, selectedClip, update, onOpenCrop, onSplit }: Props) {
  const c = p.clips.find(x => x.id === selectedClip)
  const sfx = (p.sfx_clips ?? []).find(x => x.id === selectedClip)
  const cap = p.caption
  const setCap = <K extends keyof Project['caption']>(k: K, v: Project['caption'][K]) =>
    update(prj => { prj.caption[k] = v; return prj })

  const applyPreset = (preset: string) => {
    update(prj => {
      if (preset === 'tiktok') {
        prj.caption.font = 'TheBoldFont'
        prj.caption.color = '#ffffff'
        prj.caption.emph_color = '#facc15'
        prj.caption.stroke_color = '#000000'
        prj.caption.stroke_width = 12
        prj.caption.uppercase = true
        prj.caption.box_style = 'none'
      } else if (preset === 'pill') {
        prj.caption.font = 'Montserrat'
        prj.caption.color = '#ffffff'
        prj.caption.emph_color = '#22d3ee'
        prj.caption.stroke_color = '#000000'
        prj.caption.stroke_width = 0
        prj.caption.uppercase = false
        prj.caption.box_style = 'pill'
        prj.caption.box_color = '#000000aa'
        prj.caption.box_padding = 12
      } else if (preset === 'cyber') {
        prj.caption.font = 'Impact'
        prj.caption.color = '#00ffff'
        prj.caption.emph_color = '#ff007f'
        prj.caption.stroke_color = '#000000'
        prj.caption.stroke_width = 8
        prj.caption.uppercase = true
        prj.caption.box_style = 'card'
        prj.caption.box_color = '#0f172acc'
        prj.caption.box_padding = 14
      } else if (preset === 'highlight') {
        prj.caption.font = 'Montserrat'
        prj.caption.color = '#000000'
        prj.caption.emph_color = '#ef4444'
        prj.caption.stroke_color = '#ffffff'
        prj.caption.stroke_width = 0
        prj.caption.uppercase = true
        prj.caption.box_style = 'highlight'
        prj.caption.box_color = '#facc15ee'
        prj.caption.box_padding = 8
      }
      return prj
    }, true)
  }

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
      {sfx ? (
        <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-950/20 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-rose-400">
              🔊 Hiệu ứng SFX
            </h3>
            <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-bold text-rose-300">
              {sfx.dur.toFixed(1)}s
            </span>
          </div>

          <div className="truncate rounded bg-zinc-800 px-2 py-1.5 text-xs font-semibold text-zinc-200">
            🔔 {sfx.name}
          </div>

          <div>
            <div className="flex justify-between text-xs text-zinc-400 mb-1">
              <span>Âm lượng SFX</span>
              <span>{Math.round((sfx.volume ?? 0.8) * 100)}%</span>
            </div>
            <input
              type="range" min={0.0} max={1.0} step={0.05}
              value={sfx.volume ?? 0.8}
              onChange={e => update(prj => {
                const item = (prj.sfx_clips ?? []).find(s => s.id === sfx.id)
                if (item) item.volume = +e.target.value
                return prj
              })}
              className="w-full accent-rose-500"
            />
          </div>

          <button
            className="w-full rounded-md bg-rose-600/80 py-1.5 text-xs font-medium hover:bg-rose-600 text-white"
            onClick={() => update(prj => {
              prj.sfx_clips = (prj.sfx_clips ?? []).filter(s => s.id !== sfx.id)
              return prj
            }, true)}
          >
            Xóa âm thanh này
          </button>
          <hr className="my-2 border-white/10" />
        </div>
      ) : null}

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

          {/* Tăng tốc độ phát (Speed / Timelapse) cho video */}
          {isVideo(c.src) && (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-950/20 p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                  <span>⚡</span> Tốc độ phát (Speed / Timelapse)
                </span>
                <span className="text-xs font-mono font-bold text-amber-400">
                  {(c.speed ?? 1.0).toFixed(1)}x
                </span>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.5"
                  min="0.2"
                  max="50"
                  className={input}
                  value={c.speed ?? 1.0}
                  onChange={e => {
                    const newSpeed = Math.max(0.1, +e.target.value)
                    update(prj => {
                      const target = prj.clips.find(x => x.id === c.id)!
                      const oldSpeed = target.speed ?? 1.0
                      target.speed = newSpeed
                      if (oldSpeed > 0 && newSpeed > 0) {
                        target.dur = Math.max(0.2, Number((target.dur * (oldSpeed / newSpeed)).toFixed(2)))
                      }
                      return prj
                    })
                  }}
                />
                <span className="text-xs text-zinc-400">lần (x)</span>
              </div>

              <div className="flex flex-wrap gap-1 text-[10px]">
                {[1, 1.5, 2, 3, 5, 10, 15, 20].map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      update(prj => {
                        const target = prj.clips.find(x => x.id === c.id)!
                        const oldSpeed = target.speed ?? 1.0
                        target.speed = s
                        if (oldSpeed > 0 && s > 0) {
                          target.dur = Math.max(0.2, Number((target.dur * (oldSpeed / s)).toFixed(2)))
                        }
                        return prj
                      })
                    }}
                    className={`rounded px-2 py-1 font-medium transition ${
                      Math.abs((c.speed ?? 1.0) - s) < 0.05
                        ? 'bg-amber-500 text-black font-bold'
                        : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => {
                  update(prj => {
                    const curr = prj.clips.find(x => x.id === c.id)!
                    const track = curr.track || 'video'
                    const afterClips = prj.clips
                      .filter(x => (x.track || 'video') === track && x.start >= curr.start && x.id !== curr.id)
                      .sort((a, b) => a.start - b.start)
                    let nextStart = curr.start + curr.dur
                    for (const ac of afterClips) {
                      ac.start = Number(nextStart.toFixed(2))
                      nextStart += ac.dur
                    }
                    return prj
                  })
                }}
                className="w-full rounded bg-zinc-800/80 hover:bg-zinc-700 py-1.5 text-[11px] text-amber-200 transition text-center"
                title="Dồn các clip phía sau tự động hít sát vào đuôi clip này để không bị khoảng trống"
              >
                🧲 Dồn các clip phía sau liền kề
              </button>
            </div>
          )}

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

          <div className="flex gap-2">
            {onSplit && (
              <button
                type="button"
                className="flex-1 rounded-md bg-amber-600/80 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 transition shadow"
                onClick={() => onSplit(c.id)}
                title="Cắt đôi clip này tại vị trí kim thời gian đỏ (Phím S)"
              >
                ✂️ Cắt clip đôi (S)
              </button>
            )}
            <button
              className="flex-1 rounded-md bg-rose-600/80 py-1.5 text-xs font-medium hover:bg-rose-600 text-white transition"
              onClick={() => update(prj => { prj.clips = prj.clips.filter(x => x.id !== c.id); return prj }, true)}
            >
              Xóa {c.track === 'overlay' ? 'Icon' : 'Clip'}
            </button>
          </div>
          <hr className="my-5 border-white/10" />
        </>
      ) : null}

      {/* MẪU CHỮ PRESET 1-CLICK */}
      <div className="mb-4">
        <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-violet-400">
          🎨 Mẫu chữ 1-Click (Presets)
        </span>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={() => applyPreset('tiktok')}
            className="rounded-lg border border-yellow-500/30 bg-yellow-950/20 px-2 py-1.5 text-xs font-bold text-yellow-300 hover:bg-yellow-900/40 text-left transition"
          >
            🔥 TikTok Pop
          </button>
          <button
            type="button"
            onClick={() => applyPreset('pill')}
            className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 px-2 py-1.5 text-xs font-bold text-cyan-300 hover:bg-cyan-900/40 text-left transition"
          >
            💊 Viên thuốc Pill
          </button>
          <button
            type="button"
            onClick={() => applyPreset('cyber')}
            className="rounded-lg border border-fuchsia-500/30 bg-fuchsia-950/20 px-2 py-1.5 text-xs font-bold text-fuchsia-300 hover:bg-fuchsia-900/40 text-left transition"
          >
            💎 Cyber Card
          </button>
          <button
            type="button"
            onClick={() => applyPreset('highlight')}
            className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-2 py-1.5 text-xs font-bold text-amber-300 hover:bg-amber-900/40 text-left transition"
          >
            ✨ Dạ quang Box
          </button>
        </div>
      </div>

      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-violet-400">Chữ (caption)</h3>
      <Field label="Font">
        <select className={input} value={cap.font} onChange={e => setCap('font', e.target.value)}>
          {(meta?.fonts ?? [cap.font]).map(f => <option key={f}>{f}</option>)}
        </select>
      </Field>

      {/* NỀN VIỀN CHỮ (BOX / BADGE STYLE) */}
      <Field label="🏷️ Nền viền chữ (Badge / Box)">
        <select
          className={input}
          value={cap.box_style || 'none'}
          onChange={e => setCap('box_style', e.target.value as any)}
        >
          <option value="none">Không có nền (Chữ trơn)</option>
          <option value="pill">💊 Viên thuốc bo tròn (Pill Badge)</option>
          <option value="card">🗂️ Hộp thẻ bo góc (Card Box)</option>
          <option value="highlight">🖍️ Dạ quang nổi bật (Highlight)</option>
        </select>
      </Field>

      {cap.box_style && cap.box_style !== 'none' && (
        <div className="mb-3 space-y-2 rounded-lg border border-white/5 bg-zinc-800/40 p-2.5">
          <Field label={`Độ rộng lề hộp ${cap.box_padding ?? 12}px`}>
            <input
              type="range" min={4} max={28} className="w-full accent-violet-500"
              value={cap.box_padding ?? 12}
              onChange={e => setCap('box_padding', +e.target.value)}
            />
          </Field>
          <Field label="Màu nền hộp (Hex / RGBA)">
            <input
              type="text"
              placeholder="#000000b0"
              className={input}
              value={cap.box_color || '#000000b0'}
              onChange={e => setCap('box_color', e.target.value)}
            />
          </Field>
        </div>
      )}

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

      {/* CHỮ KHỔNG LỒ SAU LƯNG (CINEMATIC DEPTH TEXT) */}
      <hr className="my-5 border-white/10" />

      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-violet-400">
        🎬 Chữ khổng lồ sau lưng (Depth Text)
      </h3>
      <p className="mb-3 text-[11px] text-zinc-400">
        Hiển thị chữ to mờ chạy ngầm sau lưng nhân vật / sticker:
      </p>

      <Field label="Nội dung chữ sau lưng">
        <input
          type="text"
          className={input}
          placeholder="vd: DEVLOG, STORY, DESIGN..."
          value={p.bg_text || ''}
          onChange={e => update(prj => { prj.bg_text = e.target.value; return prj })}
        />
      </Field>

      {p.bg_text && (
        <div className="space-y-3 rounded-lg border border-white/5 bg-zinc-800/40 p-2.5">
          <Field label={`Cỡ chữ sau lưng ${p.bg_text_size ?? 160}px`}>
            <input
              type="range" min={60} max={320} step={5} className="w-full accent-violet-500"
              value={p.bg_text_size ?? 160}
              onChange={e => update(prj => { prj.bg_text_size = +e.target.value; return prj })}
            />
          </Field>
          <Field label={`Vị trí dọc ${p.bg_text_y_pct ?? 35}%`}>
            <input
              type="range" min={10} max={90} className="w-full accent-violet-500"
              value={p.bg_text_y_pct ?? 35}
              onChange={e => update(prj => { prj.bg_text_y_pct = +e.target.value; return prj })}
            />
          </Field>
          <Field label="Màu chữ sau lưng (RGBA / Hex)">
            <input
              type="text"
              className={input}
              placeholder="#ffffff1e"
              value={p.bg_text_color || '#ffffff1e'}
              onChange={e => update(prj => { prj.bg_text_color = e.target.value; return prj })}
            />
          </Field>
        </div>
      )}
    </div>
  )
}
