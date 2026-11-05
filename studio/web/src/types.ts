export interface Word { text: string; start: number; end: number; emph: boolean }
export interface CaptionStyle {
  font: string; size: number; color: string; emph_color: string; stroke_color: string;
  stroke_width: number; y_pct: number; max_words: number; uppercase: boolean;
  effect: 'none' | 'pop_in';
}
export interface VoiceSettings { engine: string; voice: string; speed: number; style: string }
export interface Clip {
  id: string; track: 'video' | 'overlay'; src: string; start: number; dur: number; in_point: number;
  fit: 'cover' | 'contain_blur' | 'contain';
  effect: 'none' | 'zoom_in' | 'zoom_out' | 'fade' | 'flash' | 'dim_blur' | 'spotlight';
  dim_bg?: boolean;
  x_pct: number;
  y_pct: number;
  scale_pct: number;
}
export interface Project {
  id: string; name: string; width: number; height: number; fps: number; bg_color: string;
  script: string; voice: VoiceSettings; caption: CaptionStyle; words: Word[];
  voice_file: string | null; clips: Clip[];
}
export interface Meta { voices: Record<string, string[]>; styles: string[]; fonts: string[] }

export const isImage = (src: string) => /\.(png|jpe?g|webp|gif)$/i.test(src)
export const isVideo = (src: string) => /\.(mp4|mov|webm|mkv|m4v)$/i.test(src)

export function duration(p: Project): number {
  const ends = [...p.words.map(w => w.end), ...p.clips.map(c => c.start + c.dur)]
  return ends.length ? Math.max(...ends) + 0.3 : 0
}

/** Giống render/captions.py: gom từ thành nhóm, ngắt sau dấu câu. */
export interface Group { words: Word[]; start: number; end: number; showUntil: number }
export function groupWords(words: Word[], maxWords: number): Group[] {
  const groups: Word[][] = []
  let cur: Word[] = []
  for (const w of words) {
    cur.push(w)
    if (cur.length >= maxWords || /[.!?,;:]$/.test(w.text.trim())) { groups.push(cur); cur = [] }
  }
  if (cur.length) groups.push(cur)
  return groups.map((ws, i) => {
    const start = ws[0].start, end = ws[ws.length - 1].end
    const nxt = i + 1 < groups.length ? groups[i + 1][0].start : end + 0.25
    return { words: ws, start, end, showUntil: Math.max(Math.min(nxt, end + 0.6), start + 0.05) }
  })
}
