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
  voice: (id: string, segment_id?: string) => fetch(`/api/projects/${id}/voice`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ segment_id }),
  }).then(r => j<Project>(r)),
  assembleVoice: (id: string) => fetch(`/api/projects/${id}/assemble-voice`, {
    method: 'POST',
  }).then(r => j<Project>(r)),
  autoBroll: (id: string) => fetch(`/api/projects/${id}/auto-broll`, { method: 'POST' }).then(r => j<Project>(r)),
  render: (id: string, export_dir?: string | null, quality = '1080p', eco_mode = true) => fetch(`/api/projects/${id}/render`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ export_dir, quality, eco_mode }),
  }).then(r => j<{ url: string; saved_path: string; filename: string }>(r)),
  cropSource: (pid: string, src: string, crop_x: number, crop_y: number, crop_scale: number, name?: string) => fetch(`/api/projects/${pid}/crop-source`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src, crop_x, crop_y, crop_scale, name }),
  }).then(r => j<{ src: string; url: string }>(r)),
  revealFile: (path: string) => fetch('/api/reveal-file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }),
  }).then(r => j<{ status: string }>(r)),
  upload: (id: string, file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(`/api/projects/${id}/media`, { method: 'POST', body: fd }).then(r => j<{ src: string }>(r))
  },
  media: (id: string) => fetch(`/api/media/${id}`).then(r => j<string[]>(r)),
  stickers: () => fetch('/api/stickers').then(r => j<string[]>(r)),
  addSticker: (pid: string, name: string) => fetch(`/api/projects/${pid}/add-sticker/${name}`, { method: 'POST' }).then(r => j<{ src: string }>(r)),
  meta: () => fetch('/api/meta').then(r => j<Meta>(r)),
  previewVoice: (voice: string, speed: number) => fetch('/api/preview-voice', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ voice, speed }),
  }).then(r => j<{ url: string }>(r)),
  extractVoiceUrl: (url: string, name: string) => fetch('/api/extract-voice-url', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, name }),
  }).then(r => j<{ status: string; voice: string }>(r)),
  uploadVoice: (file: File, name: string) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(`/api/upload-voice?name=${encodeURIComponent(name)}`, { method: 'POST', body: fd }).then(r => j<{ status: string; voice: string }>(r))
  },
  uploadBgm: (pid: string, file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(`/api/projects/${pid}/bgm`, { method: 'POST', body: fd }).then(r => j<Project>(r))
  },
  deleteBgm: (pid: string) => fetch(`/api/projects/${pid}/bgm`, { method: 'DELETE' }).then(r => j<Project>(r)),
}

export const fileUrl = (pid: string, src: string) => `/files/${pid}/${src}`
