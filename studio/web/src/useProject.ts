import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Project } from './types'

/** Project + undo/redo + autosave (debounce). Mọi thay đổi đi qua `update`. */
export function useProject(id: string | null) {
  const [project, setProject] = useState<Project | null>(null)
  const past = useRef<Project[]>([])
  const future = useRef<Project[]>([])
  const [dirty, setDirty] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    past.current = []; future.current = []
    if (!id) { setProject(null); return }
    api.get(id).then(setProject)
  }, [id])

  const scheduleSave = useCallback((p: Project) => {
    setDirty(true)
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => api.save(p).then(() => setDirty(false)), 600)
  }, [])

  const update = useCallback((fn: (p: Project) => Project, record = true) => {
    setProject(prev => {
      if (!prev) return prev
      const next = fn(structuredClone(prev))
      if (record) { past.current.push(prev); if (past.current.length > 100) past.current.shift(); future.current = [] }
      scheduleSave(next)
      return next
    })
  }, [scheduleSave])

  const replace = useCallback((p: Project) => { setProject(p); setDirty(false) }, [])

  const undo = useCallback(() => {
    setProject(cur => {
      const prev = past.current.pop()
      if (!prev || !cur) return cur
      future.current.push(cur); scheduleSave(prev); return prev
    })
  }, [scheduleSave])

  const redo = useCallback(() => {
    setProject(cur => {
      const nxt = future.current.pop()
      if (!nxt || !cur) return cur
      past.current.push(cur); scheduleSave(nxt); return nxt
    })
  }, [scheduleSave])

  return { project, update, replace, undo, redo, dirty }
}
