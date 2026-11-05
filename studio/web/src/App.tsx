import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import Inspector from './components/Inspector'
import Preview from './components/Preview'
import Sidebar from './components/Sidebar'
import Timeline from './components/Timeline'
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
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string; url?: string } | null>(null)
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

  // đồng hồ phát
  useEffect(() => {
    if (!playing) { audio.current?.pause(); return }
    const a = audio.current
    if (a) { a.currentTime = time; a.play().catch(() => {}) }
    let last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000; last = now
      setTime(t => {
        const nt = a && !a.paused ? a.currentTime : t + dt
        if (nt >= total) { setPlaying(false); return total }
        return nt
      })
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, total])

  const seek = (t: number) => {
    const nt = Math.min(Math.max(0, t), total || t)
    setTime(nt)
    if (audio.current) audio.current.currentTime = nt
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

  const run = async (kind: 'voice' | 'render' | 'broll') => {
    if (!project) return
    setBusy(kind); setMsg(null)
    try {
      await api.save(project)
      if (kind === 'voice') { replace(await api.voice(project.id)); setMsg({ kind: 'ok', text: 'Đã tạo giọng + căn từng từ.' }) }
      else if (kind === 'broll') { replace(await api.autoBroll(project.id)); setMsg({ kind: 'ok', text: 'Đã tự xếp B-Roll theo câu.' }) }
      else { const r = await api.render(project.id); setMsg({ kind: 'ok', text: 'Xuất xong.', url: r.url }) }
    } catch (e) { setMsg({ kind: 'err', text: (e as Error).message }) }
    finally { setBusy(null) }
  }

  const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`
  const btn = 'rounded-md px-2.5 py-1.5 text-sm text-zinc-300 hover:bg-white/10 disabled:opacity-30'

  return (
    <div className="grid h-screen grid-rows-[48px_1fr_260px] bg-zinc-950 text-zinc-100">
      <header className="flex items-center gap-3 border-b border-white/10 px-4">
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
          {msg && (
            <span className={`max-w-md truncate text-xs ${msg.kind === 'ok' ? 'text-emerald-400' : 'text-rose-400'}`} title={msg.text}>
              {msg.text} {msg.url && <a className="underline" href={msg.url} target="_blank">Mở video</a>}
            </span>
          )}
          <button onClick={() => run('render')} disabled={!project || !!busy || !total}
            className="rounded-lg bg-fuchsia-600 px-4 py-1.5 text-sm font-semibold hover:bg-fuchsia-500 disabled:opacity-40">
            {busy === 'render' ? 'Đang xuất…' : 'Xuất MP4'}
          </button>
        </div>
      </header>

      {project ? (
        <>
          <main className="grid min-h-0 grid-cols-[300px_1fr_280px]">
            <aside className="min-h-0 border-r border-white/10 bg-zinc-900/40">
              <Sidebar project={project} meta={meta} media={media} refreshMedia={refreshMedia}
                update={update} onVoice={() => run('voice')} onAutoBroll={() => run('broll')} busy={busy} time={time} />
            </aside>
            <section className="flex min-h-0 flex-col bg-zinc-950">
              <div className="min-h-0 flex-1 p-5"><Preview project={project} time={time} playing={playing} onSeekAudio={el => { audio.current = el }} /></div>
              <div className="flex items-center justify-center gap-4 pb-3">
                <button onClick={() => seek(0)} className={btn}>⏮</button>
                <button onClick={toggle} disabled={!total} className="grid h-10 w-10 place-items-center rounded-full bg-white text-black disabled:opacity-30">{playing ? '❚❚' : '▶'}</button>
                <span className="w-28 font-mono text-xs text-zinc-400">{fmt(time)} / {fmt(total)}</span>
              </div>
            </section>
            <aside className="min-h-0 border-l border-white/10 bg-zinc-900/40">
              <Inspector project={project} meta={meta} selectedClip={selected} update={update} />
            </aside>
          </main>
          <footer className="min-h-0 border-t border-white/10">
            <Timeline project={project} time={time} selected={selected} onSelect={setSelected} onSeek={seek} update={update} />
          </footer>
        </>
      ) : (
        <div className="row-span-2 grid place-items-center text-zinc-500">
          <button onClick={newProject} className="rounded-xl bg-violet-600 px-6 py-3 font-semibold text-white hover:bg-violet-500">Tạo project đầu tiên</button>
        </div>
      )}
    </div>
  )
}
