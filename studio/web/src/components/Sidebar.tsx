import { useEffect, useRef, useState } from 'react'
import { api, fileUrl } from '../api'
import { isImage, isVideo, type Meta, type Project, type VoiceSegment } from '../types'

interface Props {
  project: Project
  meta: Meta | null
  media: string[]
  refreshMedia: () => void
  refreshMeta: () => void
  update: (fn: (p: Project) => Project, record?: boolean) => void
  onVoice: (segmentId?: string) => void
  onAutoBroll: () => void
  busy: string | null
  time: number
}

const input = 'w-full rounded-md border border-white/10 bg-zinc-800 px-2 py-1.5 text-sm outline-none focus:border-violet-500'

export default function Sidebar({
  project: p, meta, media, refreshMedia, refreshMeta, update, onVoice, onAutoBroll, busy, time,
}: Props) {
  const [tab, setTab] = useState<'script' | 'media' | 'stickers' | 'bgm'>('script')
  const [stickers, setStickers] = useState<string[]>([])
  const file = useRef<HTMLInputElement>(null)
  const bgmFile = useRef<HTMLInputElement>(null)
  const voiceFile = useRef<HTMLInputElement>(null)

  // Nghe thử giọng
  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null)
  const previewAudio = useRef<HTMLAudioElement | null>(null)

  // Trích xuất giọng từ link video
  const [extractOpen, setExtractOpen] = useState(false)
  const [extractUrl, setExtractUrl] = useState('')
  const [extractName, setExtractName] = useState('')
  const [extracting, setExtracting] = useState(false)

  // Phân loại danh mục giọng
  const categories = meta?.categories ?? {
    '🇻🇳 Tiếng Việt & Clone': meta?.voices?.vieneu ?? [],
    '🇺🇸 Tiếng Anh (Mỹ)': (meta?.voices?.kokoro ?? []).filter(v => v.includes('am_') || v.includes('af_') || v.includes('blend_')),
    '🇬🇧 Tiếng Anh (Anh)': (meta?.voices?.kokoro ?? []).filter(v => v.includes('bm_') || v.includes('bf_')),
  }

  // Khởi tạo segments nếu chưa có
  const segments: VoiceSegment[] = (p.voice_segments && p.voice_segments.length > 0)
    ? p.voice_segments
    : [
        {
          id: 'seg_1',
          text: p.script || '',
          voice: p.voice.voice,
          engine: p.voice.engine,
          style: p.voice.style,
          speed: p.voice.speed,
          start: p.voice.offset ?? 0,
          dur: p.words.length ? (p.words[p.words.length - 1].end - (p.voice.offset ?? 0)) : 0,
          words: p.words || [],
        },
      ]

  useEffect(() => {
    api.stickers().then(setStickers).catch(() => {})
  }, [])

  const upload = async (files: FileList | null) => {
    if (!files) return
    for (const f of Array.from(files)) await api.upload(p.id, f)
    refreshMedia()
  }

  const uploadBgm = async (files: FileList | null) => {
    if (!files || !files[0]) return
    try {
      const updated = await api.uploadBgm(p.id, files[0])
      update(prj => {
        prj.bgm_file = updated.bgm_file
        prj.bgm_volume = updated.bgm_volume ?? 0.25
        return prj
      })
      refreshMedia()
    } catch (e) {
      alert('Lỗi tải BGM: ' + (e as Error).message)
    }
  }

  const removeBgm = async () => {
    try {
      await api.deleteBgm(p.id)
      update(prj => {
        prj.bgm_file = null
        return prj
      })
    } catch (e) {
      alert('Lỗi xóa BGM: ' + (e as Error).message)
    }
  }

  const addClip = (src: string, track: 'video' | 'overlay' = 'video') =>
    update(prj => {
      const existingOverlays = prj.clips.filter(c => c.track === 'overlay')
      const maxZ = existingOverlays.reduce((m, c) => Math.max(m, c.z_order ?? 0), 0)
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
        z_order: track === 'overlay' ? maxZ + 1 : 0,
      })
      return prj
    })

  const addStickerToProject = async (name: string) => {
    const res = await api.addSticker(p.id, name)
    refreshMedia()
    addClip(res.src, 'overlay')
  }

  const handlePreviewVoice = async (voiceName: string, speed: number = 1.0) => {
    if (previewingVoice === voiceName) {
      previewAudio.current?.pause()
      setPreviewingVoice(null)
      return
    }
    setPreviewingVoice(voiceName)
    try {
      const res = await api.previewVoice(voiceName, speed)
      if (previewAudio.current) {
        previewAudio.current.pause()
      }
      const audio = new Audio(res.url)
      previewAudio.current = audio
      audio.onended = () => setPreviewingVoice(null)
      audio.onerror = () => setPreviewingVoice(null)
      await audio.play()
    } catch (e) {
      alert('Không nghe thử được: ' + (e as Error).message)
      setPreviewingVoice(null)
    }
  }

  const handleExtractVoice = async () => {
    if (!extractUrl.trim() || !extractName.trim()) {
      alert('Vui lòng nhập link video (YouTube/Shorts) và tên giọng!')
      return
    }
    setExtracting(true)
    try {
      const res = await api.extractVoiceUrl(extractUrl.trim(), extractName.trim())
      refreshMeta()
      setExtractUrl('')
      setExtractName('')
      setExtractOpen(false)
      alert(`Đã trích xuất thành công giọng '${res.voice}'! Có thể chọn và nghe thử ngay trong danh sách giọng.`)
    } catch (e) {
      alert('Lỗi: ' + (e as Error).message)
    } finally {
      setExtracting(false)
    }
  }

  const handleUploadVoice = async (files: FileList | null) => {
    if (!files || !files[0]) return
    const customName = prompt('Đặt tên cho giọng này:', files[0].name.replace(/\.[^/.]+$/, ''))
    if (!customName) return
    try {
      const res = await api.uploadVoice(files[0], customName)
      refreshMeta()
      alert(`Đã tải lên và tối ưu giọng '${res.voice}' thành công!`)
    } catch (e) {
      alert('Lỗi tải file giọng: ' + (e as Error).message)
    }
  }

  // Thêm đoạn thoại mới với giọng riêng
  const addSegment = () => {
    update(prj => {
      const curSegs = (prj.voice_segments && prj.voice_segments.length > 0) ? prj.voice_segments : [...segments]
      const last = curSegs[curSegs.length - 1]
      const nextStart = last ? Number((last.start + Math.max(last.dur, 1.5) + 0.5).toFixed(2)) : 0
      curSegs.push({
        id: crypto.randomUUID().slice(0, 8),
        text: '',
        voice: last?.voice ?? '【EN Devlog Trẻ / Độc quyền】blend_young_devlog',
        engine: last?.engine ?? 'kokoro',
        style: last?.style ?? 'Devlog / Chill',
        speed: 1.0,
        start: nextStart,
        dur: 0,
        words: [],
      })
      prj.voice_segments = curSegs
      prj.script = curSegs.map(s => s.text).join('\n\n')
      return prj
    })
  }

  // Xóa 1 đoạn thoại
  const removeSegment = (segId: string) => {
    update(prj => {
      if (!prj.voice_segments || prj.voice_segments.length <= 1) return prj
      prj.voice_segments = prj.voice_segments.filter(s => s.id !== segId)
      prj.script = prj.voice_segments.map(s => s.text).join('\n\n')
      const allW: typeof prj.words = []
      prj.voice_segments.forEach(s => allW.push(...s.words))
      prj.words = allW.sort((a, b) => a.start - b.start)
      return prj
    })
  }

  // Cập nhật 1 segment
  const updateSegment = (segId: string, fn: (seg: VoiceSegment) => void, record: boolean = false) => {
    update(prj => {
      if (!prj.voice_segments) prj.voice_segments = [...segments]
      const target = prj.voice_segments.find(s => s.id === segId)
      if (target) {
        fn(target)
        prj.script = prj.voice_segments.map(s => s.text).join('\n\n')
      }
      return prj
    }, record)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex border-b border-white/10 text-xs">
        {(['script', 'media', 'stickers', 'bgm'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 font-medium transition ${
              tab === t ? 'border-b-2 border-violet-500 text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {t === 'script' ? `🎙️ Thoại (${segments.length})` : t === 'media' ? 'Media' : t === 'stickers' ? '🎨 Icon' : '🎵 Nhạc BGM'}
          </button>
        ))}
      </div>

      {tab === 'script' ? (
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {/* Công cụ trích xuất giọng & Tải giọng mới */}
          <div className="rounded-lg border border-violet-500/20 bg-violet-950/20 p-2.5">
            <button
              onClick={() => setExtractOpen(!extractOpen)}
              className="flex w-full items-center justify-between text-xs font-medium text-violet-300 hover:text-violet-200"
            >
              <span>✨ Trích xuất giọng từ link video (YouTube/Shorts)</span>
              <span>{extractOpen ? '▲' : '▼'}</span>
            </button>

            {extractOpen && (
              <div className="mt-3 space-y-2 border-t border-violet-500/20 pt-2 text-xs">
                <div>
                  <span className="mb-1 block text-[10px] text-zinc-400">Dán URL YouTube / Shorts:</span>
                  <input
                    type="text"
                    className={input}
                    placeholder="https://www.youtube.com/shorts/..."
                    value={extractUrl}
                    onChange={e => setExtractUrl(e.target.value)}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-[10px] text-zinc-400">Tên giọng clone:</span>
                  <input
                    type="text"
                    className={input}
                    placeholder="vd: kimbo_giong_hay"
                    value={extractName}
                    onChange={e => setExtractName(e.target.value)}
                  />
                </div>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={handleExtractVoice}
                    disabled={extracting}
                    className="flex-1 rounded bg-violet-600 py-1.5 font-medium text-white hover:bg-violet-500 disabled:opacity-50"
                  >
                    {extracting ? 'Đang trích xuất…' : '🚀 Lấy giọng'}
                  </button>
                  <button
                    onClick={() => voiceFile.current?.click()}
                    className="rounded border border-white/20 px-2 py-1.5 text-zinc-300 hover:border-violet-400"
                    title="Hoặc upload file âm thanh/thu âm để tạo giọng"
                  >
                    📁 Tải file wav/mp3
                  </button>
                </div>
              </div>
            )}
            <input ref={voiceFile} type="file" hidden accept="audio/*" onChange={e => handleUploadVoice(e.target.files)} />
          </div>

          {/* DANH SÁCH CÁC ĐOẠN THOẠI (MULTI-VOICE SEGMENTS) */}
          <div className="space-y-3">
            {segments.map((seg, idx) => {
              const curCat = Object.keys(categories).find(c => categories[c]?.includes(seg.voice)) || '🇻🇳 Tiếng Việt & Clone'
              const voiceList = categories[curCat] ?? []

              return (
                <div
                  key={seg.id}
                  className="rounded-xl border border-white/10 bg-zinc-900/80 p-3 space-y-2.5 shadow-sm ring-1 ring-white/5"
                >
                  {/* Header đoạn thoại */}
                  <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="grid h-5 w-5 place-items-center rounded bg-violet-600/30 text-[10px] font-bold text-violet-300">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-semibold text-zinc-200">
                        Đoạn thoại #{idx + 1}
                      </span>
                      <span className="text-[10px] text-zinc-500 font-mono">
                        ({seg.start.toFixed(1)}s {seg.dur > 0 ? `→ ${(seg.start + seg.dur).toFixed(1)}s` : ''})
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      {segments.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeSegment(seg.id)}
                          className="rounded px-1.5 py-0.5 text-[10px] text-rose-400 hover:bg-rose-500/20"
                          title="Xóa đoạn này"
                        >
                          ✕ Xóa
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Textarea kịch bản của đoạn */}
                  <textarea
                    className={`${input} h-24 resize-none leading-relaxed text-xs`}
                    placeholder={`Viết câu nói cho đoạn ${idx + 1} ở đây...`}
                    value={seg.text}
                    onChange={e => updateSegment(seg.id, s => { s.text = e.target.value }, false)}
                  />

                  {/* Chọn quốc gia / ngôn ngữ cho đoạn này */}
                  <div>
                    <span className="mb-1 block text-[10px] font-medium text-zinc-400">
                      Ngôn ngữ / Quốc gia:
                    </span>
                    <div className="grid grid-cols-3 gap-1 rounded bg-zinc-800 p-0.5">
                      {Object.keys(categories).map(cat => (
                        <button
                          key={cat}
                          type="button"
                          onClick={() => {
                            const first = categories[cat]?.[0]
                            if (first) {
                              updateSegment(seg.id, s => {
                                s.voice = first
                                s.engine = first.startsWith('【EN') ? 'kokoro' : 'vieneu'
                              }, true)
                            }
                          }}
                          className={`truncate rounded px-1 py-0.5 text-[10px] font-medium transition ${
                            curCat === cat ? 'bg-violet-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                          }`}
                        >
                          {cat.split(' ')[0]} {cat.split(' ')[1]}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Chọn giọng riêng của đoạn này */}
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-[10px] font-medium text-zinc-400">Giọng đọc riêng:</span>
                      <button
                        type="button"
                        onClick={() => handlePreviewVoice(seg.voice, seg.speed)}
                        className="flex items-center gap-1 text-[10px] font-medium text-emerald-400 hover:underline"
                        title="Nghe thử giọng này"
                      >
                        {previewingVoice === seg.voice ? '⏹ Đang phát…' : '🔊 Nghe thử'}
                      </button>
                    </div>
                    <select
                      className={input}
                      value={seg.voice}
                      onChange={e => updateSegment(seg.id, s => {
                        s.voice = e.target.value
                        s.engine = e.target.value.startsWith('【EN') ? 'kokoro' : 'vieneu'
                      }, true)}
                    >
                      {voiceList.map(v => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                      {!voiceList.includes(seg.voice) && (
                        <option value={seg.voice}>{seg.voice}</option>
                      )}
                    </select>
                  </div>

                  {/* Mốc bắt đầu & Tốc độ của đoạn */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="block text-[10px] text-zinc-500 mb-1">Bắt đầu ({seg.start}s)</span>
                      <input
                        type="number" step="0.1" min="0"
                        className={input}
                        value={seg.start}
                        onChange={e => updateSegment(seg.id, s => {
                          const diff = Math.max(0, +e.target.value) - s.start
                          s.start = Math.max(0, +e.target.value)
                          s.words.forEach(w => { w.start += diff; w.end += diff })
                        }, true)}
                      />
                    </div>
                    <div>
                      <span className="block text-[10px] text-zinc-500 mb-1">Tốc độ ({seg.speed}×)</span>
                      <input
                        type="range" min={0.7} max={1.3} step={0.05} className="mt-2 w-full accent-violet-500"
                        value={seg.speed}
                        onChange={e => updateSegment(seg.id, s => { s.speed = +e.target.value }, false)}
                      />
                    </div>
                  </div>

                  {/* Nút đọc riêng đoạn này */}
                  <button
                    type="button"
                    onClick={() => onVoice(seg.id)}
                    disabled={!!busy || !seg.text.trim()}
                    className="w-full rounded bg-zinc-800 py-1.5 text-xs font-medium text-violet-300 hover:bg-zinc-700 disabled:opacity-40 transition"
                  >
                    {busy === `voice_${seg.id}` ? 'Đang đọc đoạn này…' : seg.words.length ? '🔄 Đọc lại đoạn này' : '▶️ Tạo giọng đoạn này'}
                  </button>
                </div>
              )
            })}
          </div>

          {/* Nút Thêm đoạn thoại mới */}
          <button
            type="button"
            onClick={addSegment}
            className="w-full rounded-xl border border-dashed border-violet-500/40 bg-violet-950/20 py-2.5 text-xs font-semibold text-violet-300 hover:border-violet-400 hover:bg-violet-950/40 transition flex items-center justify-center gap-1.5"
          >
            <span>+</span>
            <span>Thêm đoạn thoại mới (Đổi giọng/nhân vật khác)</span>
          </button>

          {/* Nút Đọc toàn bộ các đoạn */}
          <button
            onClick={() => onVoice()}
            disabled={!!busy || segments.every(s => !s.text.trim())}
            className="w-full rounded-lg bg-violet-600 py-3 text-sm font-semibold hover:bg-violet-500 disabled:opacity-40 transition shadow-lg shadow-violet-600/20"
          >
            {busy === 'voice' ? 'Đang đọc toàn bộ…' : '⚡ Tạo toàn bộ giọng các đoạn'}
          </button>
          <p className="text-[11px] text-zinc-500">
            💡 Mỗi đoạn thoại có thể đặt 1 giọng khác nhau (đối thoại nhiều nhân vật). Bạn có thể kéo thả trực tiếp từng đoạn trên timeline.
          </p>
        </div>
      ) : tab === 'media' ? (
        <div className="flex-1 overflow-y-auto p-4">
          <input ref={file} type="file" multiple hidden accept="image/*,video/*" onChange={e => upload(e.target.files)} />
          <div className="mb-3 flex gap-2">
            <button
              onClick={() => file.current?.click()}
              className="flex-1 rounded-lg border border-dashed border-white/20 py-2.5 text-xs text-zinc-300 hover:border-violet-500 hover:text-white"
            >
              + Thêm ảnh / video
            </button>
            <button
              onClick={onAutoBroll}
              disabled={!media.length}
              className="flex-1 rounded-lg bg-violet-600/80 py-2.5 text-xs font-medium text-white hover:bg-violet-600 disabled:opacity-30"
              title="Tự động rải các ảnh/video vào khớp từng câu thoại"
            >
              ⚡ Tự xếp theo câu
            </button>
          </div>

          <div className="space-y-2">
            {media.filter(m => isImage(m) || isVideo(m)).map(m => (
              <div key={m} className="flex items-center gap-2 rounded-lg bg-zinc-800/80 p-2 ring-1 ring-white/5">
                <div className="h-12 w-16 shrink-0 overflow-hidden rounded bg-black">
                  {isImage(m) ? (
                    <img src={fileUrl(p.id, m)} className="h-full w-full object-cover" />
                  ) : (
                    <video src={fileUrl(p.id, m)} className="h-full w-full object-cover" muted preload="metadata" />
                  )}
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
      ) : tab === 'stickers' ? (
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
      ) : (
        /* Tab Nhạc nền BGM */
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <input ref={bgmFile} type="file" hidden accept="audio/*" onChange={e => uploadBgm(e.target.files)} />
          <span className="block text-xs font-semibold uppercase tracking-wider text-violet-400">🎵 Nhạc nền (BGM)</span>

          {p.bgm_file ? (
            <div className="rounded-lg border border-violet-500/30 bg-violet-950/20 p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="truncate text-xs font-medium text-zinc-200">
                  {p.bgm_file.replace('media/', '')}
                </span>
                <button onClick={removeBgm} className="rounded bg-rose-600/40 px-2 py-0.5 text-[11px] text-rose-200 hover:bg-rose-600">
                  Xóa nhạc
                </button>
              </div>

              <div>
                <div className="flex justify-between text-xs text-zinc-400 mb-1">
                  <span>Âm lượng BGM</span>
                  <span>{Math.round((p.bgm_volume ?? 0.25) * 100)}%</span>
                </div>
                <input
                  type="range" min={0.0} max={1.0} step={0.05}
                  value={p.bgm_volume ?? 0.25}
                  onChange={e => update(prj => { prj.bgm_volume = +e.target.value; return prj })}
                  className="w-full accent-violet-500"
                />
              </div>

              <button
                onClick={() => bgmFile.current?.click()}
                className="w-full rounded border border-white/10 py-1.5 text-xs text-zinc-300 hover:border-violet-500"
              >
                Đổi bài nhạc khác
              </button>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-white/20 p-6 text-center">
              <p className="text-xs text-zinc-400 mb-3">Chưa có nhạc nền trong video này</p>
              <button
                onClick={() => bgmFile.current?.click()}
                className="rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white hover:bg-violet-500 shadow"
              >
                + Tải nhạc nền (.mp3 / .wav)
              </button>
            </div>
          )}

          <div className="rounded-lg bg-zinc-800/40 p-3 text-xs text-zinc-400 space-y-1">
            <p>💡 <b>Tự động hạ nhạc (Auto Ducking):</b></p>
            <p>Khi xuất video, nhạc nền sẽ được tự động hòa âm dịu dàng dưới giọng đọc để không lấn át tiếng nói.</p>
          </div>
        </div>
      )}
    </div>
  )
}
