import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import CropModal from './components/CropModal'
import Inspector from './components/Inspector'
import Preview from './components/Preview'
import Sidebar from './components/Sidebar'
import Timeline from './components/Timeline'
import ToastContainer, { type ToastItem } from './components/Toast'
import { duration, type Meta } from './types'
import { useProject } from './useProject'

export default function App() {
  const [list, setList] = useState<{ id: string; name: string }[]>([])
  const [pid, setPid] = useState<string | null>(localStorage.getItem('pid'))
  const { project, update, replace, undo, redo, dirty } = useProject(pid)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [media, setMedia] = useState<string[]>([])
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [voiceVersion, setVoiceVersion] = useState(0)
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [showExportModal, setShowExportModal] = useState(false)
  const [selectedExportDir, setSelectedExportDir] = useState<string>('project')
  const [customExportDir, setCustomExportDir] = useState<string>('')
  const [exportQuality, setExportQuality] = useState<'480p' | '720p' | '1080p'>('720p')
  const [ecoMode, setEcoMode] = useState(true)
  const [lastRender, setLastRender] = useState<{ url: string; saved_path: string; filename: string } | null>(null)
  const [cropClipId, setCropClipId] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const raf = useRef(0)

  const refreshList = useCallback(() => api.projects().then(setList), [])
  const refreshMedia = useCallback(() => { if (pid) api.media(pid).then(setMedia) }, [pid])

  useEffect(() => { refreshList(); api.meta().then(setMeta) }, [refreshList])
  useEffect(() => {
    if (pid) localStorage.setItem('pid', pid)
    setTime(0); setPlaying(false); setSelected(null); refreshMedia()
  }, [pid, refreshMedia])
  // chưa chọn project -> lấy cái đầu tiên
  useEffect(() => {
    if (!pid && list.length) setPid(list[0].id)
  }, [list, pid])

  const total = project ? duration(project) : 0

  // đồng hồ phát (Audio là master clock khi phát, tuyệt đối không seek liên tục trong loop)
  useEffect(() => {
    if (!playing) { audio.current?.pause(); return }
    const a = audio.current
    const vOffset = project?.voice?.offset ?? 0
    if (a) {
      if (time >= vOffset) {
        a.currentTime = Math.max(0, time - vOffset)
        a.play().catch(() => {})
      } else {
        a.pause()
        a.currentTime = 0
      }
    }
    let last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000; last = now
      setTime(cur => {
        let nt: number
        if (a && !a.paused && a.duration > 0) {
          nt = a.currentTime + vOffset
        } else {
          nt = cur + dt
          if (a && cur < vOffset && nt >= vOffset) {
            a.currentTime = 0
            a.play().catch(() => {})
          }
        }
        if (nt >= total) {
          setPlaying(false)
          audio.current?.pause()
          return total
        }
        return nt
      })
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, total, project?.voice?.offset])

  const seek = (t: number) => {
    const nt = Math.min(Math.max(0, t), total || t)
    setTime(nt)
    const vOffset = project?.voice?.offset ?? 0
    if (audio.current) {
      if (nt >= vOffset) {
        audio.current.currentTime = nt - vOffset
      } else {
        audio.current.currentTime = 0
      }
    }
  }
  const toggle = useCallback(() => {
    if (!total) return
    if (time >= total - 0.05) seek(0)
    setPlaying(p => !p)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [total, time])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return
      if (e.code === 'Space') { e.preventDefault(); toggle() }
      else if ((e.metaKey || e.ctrlKey) && e.key === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo() }
      else if ((e.key === 'Delete' || e.key === 'Backspace') && selected) {
        update(p => { p.clips = p.clips.filter(c => c.id !== selected); return p }); setSelected(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle, undo, redo, selected, update])

  const newProject = async () => {
    const name = prompt('Tên project mới?', 'Short mới')
    if (!name) return
    const p = await api.create(name); await refreshList(); setPid(p.id)
  }

  const addToast = (t: Omit<ToastItem, 'id'>) => {
    const id = crypto.randomUUID().slice(0, 8)
    setToasts(prev => [...prev.slice(-3), { ...t, id }])
    return id
  }

  const dismissToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  const run = async (kind: 'voice' | 'render' | 'broll', segmentId?: string) => {
    if (!project) return
    if (kind === 'render') {
      setShowExportModal(true)
      return
    }
    const busyKey = segmentId ? `voice_${segmentId}` : kind
    setBusy(busyKey)
    const t0 = performance.now()
    try {
      await api.save(project)
      if (kind === 'voice') {
        replace(await api.voice(project.id, segmentId))
        setVoiceVersion(v => v + 1)
        const elapsed = (performance.now() - t0) / 1000
        addToast({
          type: 'success',
          title: 'Tạo giọng đọc thành công!',
          message: segmentId ? 'Đã tạo và căn mốc từng từ đoạn thoại này.' : 'Đã tạo và đồng bộ toàn bộ các đoạn thoại.',
          elapsed_s: elapsed,
          duration: 4500,
        })
      }
      else if (kind === 'broll') {
        replace(await api.autoBroll(project.id))
        addToast({
          type: 'success',
          title: 'Tự xếp B-Roll hoàn tất!',
          message: 'Các ảnh và video nền đã được phân bổ khớp theo từng câu thoại.',
          duration: 4000,
        })
      }
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Thao tác thất bại!',
        message: (e as Error).message,
      })
    } finally {
      setBusy(null)
    }
  }

  const doRender = async () => {
    if (!project) return
    let targetDir = 'project'
    if (selectedExportDir === 'custom') {
      targetDir = customExportDir.trim() || 'project'
    } else {
      const preset = meta?.export_presets?.find(p => p.id === selectedExportDir)
      targetDir = preset ? preset.path : 'project'
    }
    setBusy('render')
    const t0 = performance.now()
    addToast({
      type: 'info',
      title: 'Đang xuất video MP4...',
      message: 'Hệ thống đang render video, phụ đề và hòa âm nhạc nền...',
      duration: 3500,
    })

    try {
      update(p => { p.export_dir = targetDir; return p }, false)
      await api.save({ ...project, export_dir: targetDir })
      const res = await api.render(project.id, targetDir, exportQuality, ecoMode)
      setLastRender(res)
      const elapsed = (performance.now() - t0) / 1000

      addToast({
        type: 'success',
        title: 'Xuất video MP4 thành công!',
        message: `Đã lưu video: ${res.filename}`,
        elapsed_s: elapsed,
        duration: 8000,
        actions: [
          {
            label: '📂 Mở Finder',
            onClick: () => api.revealFile(res.saved_path).catch(err => alert(err.message)),
          },
          {
            label: '📥 Tải về máy',
            href: res.url,
            download: res.filename,
          },
          {
            label: '▶️ Xem video',
            href: res.url,
            primary: true,
          },
        ],
      })
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Xuất video thất bại!',
        message: (e as Error).message,
      })
    } finally {
      setBusy(null)
    }
  }

  const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`
  const btn = 'rounded-md px-2.5 py-1.5 text-sm text-zinc-300 hover:bg-white/10 disabled:opacity-30'

  return (
    <div className="grid h-screen w-screen max-w-full overflow-hidden grid-rows-[48px_1fr_260px] bg-zinc-950 text-zinc-100">
      <header className="flex h-12 w-full shrink-0 items-center gap-3 border-b border-white/10 px-4">
        <div className="mr-2 flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid h-6 w-6 place-items-center rounded-md bg-gradient-to-br from-violet-500 to-fuchsia-500 text-xs">S</span>
          Shorts Studio
        </div>
        <select className="rounded-md border border-white/10 bg-zinc-900 px-2 py-1 text-sm" value={pid ?? ''} onChange={e => setPid(e.target.value)}>
          {list.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <button className={btn} onClick={newProject}>+ Mới</button>
        <div className="mx-1 h-5 w-px bg-white/10" />
        <button className={btn} onClick={undo} title="⌘Z">↶</button>
        <button className={btn} onClick={redo} title="⇧⌘Z">↷</button>
        <span className="text-xs text-zinc-500">{dirty ? 'Đang lưu…' : 'Đã lưu'}</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setShowExportModal(true)}
            disabled={!project || !!busy || !total}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-fuchsia-600 to-pink-600 px-4 py-1.5 text-sm font-bold text-white hover:from-fuchsia-500 hover:to-pink-500 disabled:opacity-40 shadow-lg shadow-fuchsia-950/50 transition ring-1 ring-white/20 active:scale-95"
            title={!total ? 'Cần có giọng nói hoặc clip trước khi xuất' : 'Mở bảng xuất video MP4'}
          >
            {busy === 'render' ? '⏳ Đang xuất…' : '🎬 Xuất MP4'}
          </button>
        </div>
      </header>

      {project ? (
        <>
          <main className="grid min-h-0 min-w-0 w-full overflow-hidden grid-cols-[300px_1fr_280px]">
            <aside className="min-h-0 border-r border-white/10 bg-zinc-900/40">
              <Sidebar
                project={project}
                meta={meta}
                media={media}
                refreshMedia={refreshMedia}
                refreshMeta={() => api.meta().then(setMeta)}
                update={update}
                onVoice={(segId) => run('voice', segId)}
                onAutoBroll={() => run('broll')}
                busy={busy}
                time={time}
              />
            </aside>
            <section className="flex min-h-0 flex-col bg-zinc-950">
              <div className="min-h-0 flex-1 p-5">
                <Preview
                  project={project}
                  time={time}
                  playing={playing}
                  onSeekAudio={el => { audio.current = el }}
                  voiceVersion={voiceVersion}
                />
              </div>
              <div className="flex items-center justify-center gap-4 pb-3">
                <button onClick={() => seek(0)} className={btn}>⏮</button>
                <button onClick={toggle} disabled={!total} className="grid h-10 w-10 place-items-center rounded-full bg-white text-black disabled:opacity-30">{playing ? '❚❚' : '▶'}</button>
                <span className="w-28 font-mono text-xs text-zinc-400">{fmt(time)} / {fmt(total)}</span>
              </div>
            </section>
            <aside className="min-h-0 border-l border-white/10 bg-zinc-900/40">
              <Inspector project={project} meta={meta} selectedClip={selected} update={update} onOpenCrop={id => setCropClipId(id)} />
            </aside>
          </main>
          <footer className="min-h-0 min-w-0 w-full overflow-hidden border-t border-white/10">
            <Timeline project={project} time={time} selected={selected} onSelect={setSelected} onSeek={seek} update={update} />
          </footer>
        </>
      ) : (
        <div className="row-span-2 grid place-items-center text-zinc-500">
          <button onClick={newProject} className="rounded-xl bg-violet-600 px-6 py-3 font-semibold text-white hover:bg-violet-500">Tạo project đầu tiên</button>
        </div>
      )}

      {/* Modal Tùy chọn Thư mục Xuất MP4 */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-zinc-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>🎬</span> Xuất video MP4 & Chọn nơi lưu
              </h3>
              <button
                onClick={() => setShowExportModal(false)}
                className="text-zinc-400 hover:text-zinc-200 text-lg px-1.5"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Thư mục lưu video trên máy tính:
              </span>

              <div className="space-y-2">
                {(meta?.export_presets ?? [
                  { id: 'project', label: '📁 Thư mục dự án (Mặc định)', path: 'project' },
                  { id: 'downloads', label: '📥 Thư mục Downloads', path: '~/Downloads' },
                  { id: 'desktop', label: '🖥️ Desktop (Màn hình chính)', path: '~/Desktop' },
                  { id: 'movies', label: '🎬 Thư mục Phim (Movies)', path: '~/Movies' },
                ]).map(opt => (
                  <label
                    key={opt.id}
                    className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 text-xs transition ${
                      selectedExportDir === opt.id
                        ? 'border-fuchsia-500 bg-fuchsia-950/30 text-white font-medium'
                        : 'border-white/5 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-800'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        type="radio"
                        name="exportDir"
                        checked={selectedExportDir === opt.id}
                        onChange={() => setSelectedExportDir(opt.id)}
                        className="accent-fuchsia-500"
                      />
                      <span>{opt.label}</span>
                    </div>
                    <span className="text-[11px] text-zinc-500 font-mono truncate max-w-[200px]">
                      {opt.path === 'project' ? `projects/${project?.id}/out/` : opt.path}
                    </span>
                  </label>
                ))}

                {/* Tùy chọn nhập đường dẫn thư mục bất kỳ */}
                <label
                  className={`flex flex-col gap-2 rounded-lg border p-3 text-xs transition ${
                    selectedExportDir === 'custom'
                      ? 'border-fuchsia-500 bg-fuchsia-950/30 text-white'
                      : 'border-white/5 bg-zinc-800/60 text-zinc-300 hover:bg-zinc-800'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="exportDir"
                      checked={selectedExportDir === 'custom'}
                      onChange={() => setSelectedExportDir('custom')}
                      className="accent-fuchsia-500"
                    />
                    <span className="font-medium">✏️ Đường dẫn thư mục tùy ý trên máy...</span>
                  </div>
                  {selectedExportDir === 'custom' && (
                    <input
                      type="text"
                      className="w-full rounded-md border border-white/10 bg-zinc-950 px-3 py-1.5 text-xs text-white placeholder-zinc-500 outline-none focus:border-fuchsia-500 font-mono"
                      placeholder="vd: /Users/tuandat/Documents/my_videos"
                      value={customExportDir}
                      onChange={e => setCustomExportDir(e.target.value)}
                    />
                  )}
                </label>
              </div>
            </div>

            {/* Tùy chọn Mức đồ họa & Độ phân giải */}
            <div className="space-y-2 border-t border-white/10 pt-3">
              <span className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Mức đồ họa & Độ phân giải:
              </span>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: '480p', label: '⚡ 480p', desc: 'Siêu nhanh, mát lạnh máy' },
                  { id: '720p', label: '🚀 720p', desc: 'Chuẩn TikTok (Khuyên dùng)' },
                  { id: '1080p', label: '✨ 1080p', desc: 'Full HD sắc nét nhất' },
                ].map(q => (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => setExportQuality(q.id as any)}
                    className={`flex flex-col items-center justify-center rounded-lg border p-2 text-center transition ${
                      exportQuality === q.id
                        ? 'border-fuchsia-500 bg-fuchsia-950/40 text-white ring-1 ring-fuchsia-400/40'
                        : 'border-white/5 bg-zinc-800/60 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                    }`}
                  >
                    <span className="text-xs font-bold">{q.label}</span>
                    <span className="text-[10px] text-zinc-400 mt-0.5">{q.desc}</span>
                  </button>
                ))}
              </div>

              {/* Chế độ làm mát máy Eco Mode */}
              <label className="flex items-center gap-2 pt-1 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={ecoMode}
                  onChange={e => setEcoMode(e.target.checked)}
                  className="rounded border-white/20 bg-zinc-800 text-emerald-500 accent-emerald-500"
                />
                <span className="text-xs text-zinc-300">
                  🌿 <strong className="text-emerald-400">Chế độ máy mát</strong> (Giới hạn luồng CPU, dùng chip Apple VideoToolbox không lo nóng máy)
                </span>
              </label>
            </div>

            {/* Kết quả video vừa xuất */}
            {lastRender && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-emerald-400 font-medium">
                  <span>✅</span>
                  <span className="truncate">Đã lưu: {lastRender.saved_path}</span>
                </div>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => api.revealFile(lastRender.saved_path).catch(err => alert(err.message))}
                    className="flex-1 rounded-lg bg-zinc-800 py-1.5 font-medium text-zinc-200 hover:bg-zinc-700 transition"
                  >
                    📂 Mở trong Finder
                  </button>
                  <a
                    href={lastRender.url}
                    download={lastRender.filename}
                    className="flex-1 rounded-lg bg-violet-600 py-1.5 text-center font-medium text-white hover:bg-violet-500 transition"
                  >
                    📥 Tải về máy
                  </a>
                  <a
                    href={lastRender.url}
                    target="_blank"
                    className="flex-1 rounded-lg border border-white/20 py-1.5 text-center font-medium text-zinc-300 hover:text-white transition"
                  >
                    ▶️ Xem video
                  </a>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 border-t border-white/10 pt-3">
              <button
                onClick={() => setShowExportModal(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium text-zinc-400 hover:text-white"
              >
                Đóng
              </button>
              <button
                onClick={doRender}
                disabled={busy === 'render'}
                className="rounded-lg bg-fuchsia-600 px-5 py-2 text-xs font-semibold text-white hover:bg-fuchsia-500 disabled:opacity-40 shadow transition"
              >
                {busy === 'render' ? '⏳ Đang render...' : '🚀 Bắt đầu xuất video'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Căn góc & Cắt tỷ lệ 9:16 trực quan (YouTube Shorts Reframe) */}
      {cropClipId && project && (() => {
        const clipToCrop = project.clips.find(c => c.id === cropClipId)
        if (!clipToCrop) return null
        return (
          <CropModal
            project={project}
            clip={clipToCrop}
            onClose={() => setCropClipId(null)}
            onApply={(cx, cy, cs) => {
              update(prj => {
                const target = prj.clips.find(c => c.id === cropClipId)
                if (target) {
                  target.crop_x = cx
                  target.crop_y = cy
                  target.crop_scale = cs
                }
                return prj
              })
              addToast({
                type: 'success',
                title: 'Đã cập nhật góc cắt 9:16!',
                duration: 3000,
              })
            }}
            onSourceCreated={(newSrc) => {
              refreshMedia()
              update(prj => {
                const target = prj.clips.find(c => c.id === cropClipId)
                if (target) {
                  target.src = newSrc
                  target.crop_x = 50
                  target.crop_y = 50
                  target.crop_scale = 100
                }
                return prj
              })
              addToast({
                type: 'success',
                title: 'Đã xuất thành Source 9:16 mới!',
                message: `Tệp đã lưu: ${newSrc}`,
                duration: 4500,
              })
            }}
          />
        )
      })()}

      {/* Thông báo bảng tin Toast (Góc phải dưới trượt lên) */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
