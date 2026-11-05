import type { Meta, Project } from './types'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail ?? msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  projects: () => fetch('/api/projects').then(r => j<{ id: string; name: string }[]>(r)),
  create: (name: string) => fetch('/api/projects', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  }).then(r => j<Project>(r)),
  get: (id: string) => fetch(`/api/projects/${id}`).then(r => j<Project>(r)),
  save: (p: Project) => fetch(`/api/projects/${p.id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p),
  }).then(r => j<Project>(r)),
  voice: (id: string) => fetch(`/api/projects/${id}/voice`, { method: 'POST' }).then(r => j<Project>(r)),
  autoBroll: (id: string) => fetch(`/api/projects/${id}/auto-broll`, { method: 'POST' }).then(r => j<Project>(r)),
  render: (id: string) => fetch(`/api/projects/${id}/render`, { method: 'POST' }).then(r => j<{ url: string }>(r)),
  upload: (id: string, file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(`/api/projects/${id}/media`, { method: 'POST', body: fd }).then(r => j<{ src: string }>(r))
  },
  media: (id: string) => fetch(`/api/media/${id}`).then(r => j<string[]>(r)),
  stickers: () => fetch('/api/stickers').then(r => j<string[]>(r)),
  addSticker: (pid: string, name: string) => fetch(`/api/projects/${pid}/add-sticker/${name}`, { method: 'POST' }).then(r => j<{ src: string }>(r)),
  meta: () => fetch('/api/meta').then(r => j<Meta>(r)),
}

export const fileUrl = (pid: string, src: string) => `/files/${pid}/${src}`
