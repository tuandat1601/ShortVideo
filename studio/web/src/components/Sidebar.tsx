import { useEffect, useRef, useState } from 'react'
import { api, fileUrl } from '../api'
import { isImage, isVideo, type Meta, type Project } from '../types'

interface Props {
  project: Project
  meta: Meta | null
  media: string[]
  refreshMedia: () => void
  update: (fn: (p: Project) => Project, record?: boolean) => void
  onVoice: () => void
  onAutoBroll: () => void
  busy: string | null
  time: number
}

const input = 'w-full rounded-md border border-white/10 bg-zinc-800 px-2 py-1.5 text-sm outline-none focus:border-violet-500'

export default function Sidebar({ project: p, meta, media, refreshMedia, update, onVoice, onAutoBroll, busy, time }: Props) {
  const [tab, setTab] = useState<'script' | 'media' | 'stickers'>('script')
  const [stickers, setStickers] = useState<string[]>([])
  const file = useRef<HTMLInputElement>(null)
  const voices = meta?.voices[p.voice.engine] ?? []

  useEffect(() => {
    api.stickers().then(setStickers).catch(() => {})
  }, [])

  const upload = async (files: FileList | null) => {
    if (!files) return
    for (const f of Array.from(files)) await api.upload(p.id, f)
    refreshMedia()
  }

  const addClip = (src: string, track: 'video' | 'overlay' = 'video') =>
    update(prj => {
      const end = prj.clips.filter(c => c.track === track).reduce((m, c) => Math.max(m, c.start + c.dur), 0)
      const start = track === 'overlay' ? Math.max(0, time) : (prj.clips.length ? Math.max(end, 0) : Math.max(0, time))
      prj.clips.push({
        id: crypto.randomUUID().slice(0, 8),
        track,
        src,
        start,
        dur: track === 'overlay' ? 2.0 : 2.5,
        in_point: 0,
        fit: 'cover',
        effect: 'none',
        x_pct: 50,
        y_pct: track === 'overlay' ? 30 : 50,
        scale_pct: track === 'overlay' ? 35 : 100,
      })
      return prj
    })

  const addStickerToProject = async (name: string) => {
    const res = await api.addSticker(p.id, name)
    refreshMedia()
    addClip(res.src, 'overlay')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex border-b border-white/10 text-xs">
        {(['script', 'media', 'stickers'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2.5 font-medium ${tab === t ? 'border-b-2 border-violet-500 text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'}`}>
            {t === 'script' ? 'Script & giọng' : t === 'media' ? 'Media' : '🎨 Icon/Lớp phủ'}
          </button>
        ))}
      </div>

      {tab === 'script' ? (
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          <textarea
            className={`${input} h-48 resize-none leading-relaxed`}
            placeholder="Viết kịch bản tiếng Anh ở đây. Mỗi câu sẽ được đọc riêng rồi nối lại."
            value={p.script} onChange={e => update(prj => { prj.script = e.target.value; return prj }, false)}
          />
          <div>
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Giọng</span>
            <select className={input} value={p.voice.voice} onChange={e => update(prj => { prj.voice.voice = e.target.value; return prj })}>
              {voices.map(v => <option key={v}>{v}</option>)}
              {!voices.includes(p.voice.voice) && <option>{p.voice.voice}</option>}
            </select>
          </div>
          <div>
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Phong cách</span>
            <select className={input} value={p.voice.style} onChange={e => update(prj => { prj.voice.style = e.target.value; return prj })}>
              {(meta?.styles ?? [p.voice.style]).map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Tốc độ {p.voice.speed.toFixed(2)}×</span>
            <input type="range" min={0.7} max={1.3} step={0.05} className="w-full accent-violet-500" value={p.voice.speed}
              onChange={e => update(prj => { prj.voice.speed = +e.target.value; return prj })} />
          </div>
          <button onClick={onVoice} disabled={!!busy || !p.script.trim()}
            className="w-full rounded-lg bg-violet-600 py-2.5 text-sm font-semibold hover:bg-violet-500 disabled:opacity-40">
            {busy === 'voice' ? 'Đang đọc…' : p.words.length ? 'Tạo lại giọng' : 'Tạo giọng'}
          </button>
          <p className="text-xs text-zinc-500">Tạo giọng sẽ đọc script, rồi Whisper căn mốc từng từ để chữ chạy khớp tiếng.</p>
        </div>
      ) : tab === 'media' ? (
        <div className="flex-1 overflow-y-auto p-4">
          <input ref={file} type="file" multiple hidden accept="image/*,video/*" onChange={e => upload(e.target.files)} />
          <div className="mb-3 flex gap-2">
            <button onClick={() => file.current?.click()}
              className="flex-1 rounded-lg border border-dashed border-white/20 py-2.5 text-xs text-zinc-300 hover:border-violet-500 hover:text-white">
              + Thêm ảnh / video
            </button>
            <button onClick={onAutoBroll} disabled={!media.length}
              className="flex-1 rounded-lg bg-violet-600/80 py-2.5 text-xs font-medium text-white hover:bg-violet-600 disabled:opacity-30"
              title="Tự động rải các ảnh/video vào khớp từng câu thoại">
              ⚡ Tự xếp theo câu
            </button>
          </div>

          <div className="space-y-2">
            {media.filter(m => isImage(m) || isVideo(m)).map(m => (
              <div key={m} className="flex items-center gap-2 rounded-lg bg-zinc-800/80 p-2 ring-1 ring-white/5">
                <div className="h-12 w-16 shrink-0 overflow-hidden rounded bg-black">
                  {isImage(m)
                    ? <img src={fileUrl(p.id, m)} className="h-full w-full object-cover" />
                    : <video src={fileUrl(p.id, m)} className="h-full w-full object-cover" muted preload="metadata" />}
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block truncate text-xs text-zinc-200">{m.replace('media/', '')}</span>
                  <div className="mt-1 flex gap-1">
                    <button onClick={() => addClip(m, 'video')} className="rounded bg-violet-600/60 px-2 py-0.5 text-[10px] text-violet-200 hover:bg-violet-600">
                      + Nền
                    </button>
                    <button onClick={() => addClip(m, 'overlay')} className="rounded bg-amber-600/60 px-2 py-0.5 text-[10px] text-amber-200 hover:bg-amber-600">
                      + Lớp phủ
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Tab Stickers / Icon có sẵn */
        <div className="flex-1 overflow-y-auto p-4">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-amber-400">Icon & Lớp phủ mẫu</span>
          <p className="mb-3 text-[11px] text-zinc-400">Bấm vào icon bên dưới để chèn đè lên video tại vị trí con trỏ thời gian:</p>
          <div className="grid grid-cols-2 gap-2">
            {stickers.map(stk => (
              <button
                key={stk}
                onClick={() => addStickerToProject(stk)}
                className="group flex flex-col items-center justify-center rounded-lg border border-white/10 bg-zinc-800/60 p-3 hover:border-amber-400 hover:bg-zinc-800"
              >
                <img src={`/files/${p.id}/media/${stk}`} onError={e => { (e.target as any).src = `/api/stickers` }} className="h-14 w-auto object-contain group-hover:scale-105 transition" />
                <span className="mt-1.5 truncate text-[10px] text-zinc-300">{stk.replace('.png', '')}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-lg bg-zinc-800/40 p-3 text-xs text-zinc-400">
            💡 Bạn có thể vào tab <b>Media</b> upload thêm bất kỳ file ảnh PNG trong suốt (logo, meme, ảnh comment) rồi bấm <b>+ Lớp phủ</b> để chèn vào video!
          </div>
        </div>
      )}
    </div>
  )
}
