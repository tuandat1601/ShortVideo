import { useEffect, useRef } from 'react'
import { fileUrl } from '../api'
import { groupWords, isImage, type Project } from '../types'

const FONT_CSS: Record<string, string> = {
  Impact: 'Impact, "Arial Narrow Bold", sans-serif',
  'Arial Black': '"Arial Black", sans-serif',
  'DIN Condensed': '"DIN Condensed", "Arial Narrow", sans-serif',
  'Courier Bold': '"Courier New", monospace',
}

interface Props {
  project: Project
  time: number
  playing: boolean
  onSeekAudio: (el: HTMLAudioElement | null) => void
  voiceVersion?: number
}

export default function Preview({ project: p, time, playing, onSeekAudio, voiceVersion = 0 }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const voiceAudio = useRef<HTMLAudioElement>(null)
  const bgmAudio = useRef<HTMLAudioElement>(null)
  const vids = useRef<Record<string, HTMLVideoElement | null>>({})

  useEffect(() => onSeekAudio(voiceAudio.current), [onSeekAudio])

  // Đồng bộ âm lượng BGM
  useEffect(() => {
    if (bgmAudio.current) {
      bgmAudio.current.volume = Math.min(Math.max(p.bgm_volume ?? 0.25, 0), 1)
    }
  }, [p.bgm_volume])

  // Đồng bộ phát BGM (chỉ seek khi play/pause, không seek liên tục khi đang phát)
  useEffect(() => {
    const bgm = bgmAudio.current
    if (!bgm) return
    const bgmOffset = p.bgm_offset ?? 0
    if (playing) {
      if (time >= bgmOffset) {
        bgm.currentTime = Math.max(0, time - bgmOffset)
        bgm.play().catch(() => {})
      } else {
        bgm.pause()
        bgm.currentTime = 0
      }
    } else {
      bgm.pause()
    }
  }, [playing])

  // Đồng bộ video clip với thời gian timeline (tua kéo bám sát chuột khi !playing)
  useEffect(() => {
    for (const c of p.clips) {
      const v = vids.current[c.id]
      if (!v) continue
      const active = time >= c.start && time < c.start + c.dur
      if (active) {
        const want = c.in_point + (time - c.start)
        const diff = Math.abs(v.currentTime - want)
        if ((!playing && diff > 0.02) || (playing && diff > 0.25)) {
          v.currentTime = want
        }
        if (playing && v.paused) v.play().catch(() => {})
        if (!playing && !v.paused) v.pause()
      } else if (!v.paused) v.pause()
    }
  }, [time, playing, p.clips])

  const scale = (box.current?.clientWidth ?? 360) / p.width
  const baseClips = p.clips.filter(c => (c.track || 'video') === 'video')
  const overlayClips = p.clips.filter(c => c.track === 'overlay')
  const activeBase = baseClips.filter(c => time >= c.start && time < c.start + c.dur)
  const activeOverlays = overlayClips.filter(c => time >= c.start && time < c.start + c.dur)
  const hasSpotlight = activeOverlays.some(c => c.dim_bg || c.effect === 'spotlight')
  const group = groupWords(p.words, p.caption.max_words).find(g => time >= g.start - 0.02 && time < g.showUntil)
  const st = p.caption

  return (
    <div className="flex h-full items-center justify-center">
      <div
        ref={box}
        className="relative overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/10"
        style={{ aspectRatio: `${p.width}/${p.height}`, height: '100%', maxHeight: '100%', background: p.bg_color }}
      >
        {/* 1. Track Video nền */}
        {baseClips.map(c => {
          const url = fileUrl(p.id, c.src)
          const on = activeBase.includes(c)
          const style = { display: on ? 'block' : 'none' } as const
          const fxClass = c.effect === 'zoom_in' ? 'scale-105 transition-transform duration-1000' :
                          c.effect === 'zoom_out' ? 'scale-95 transition-transform duration-1000' :
                          c.effect === 'dim_blur' ? 'blur-sm brightness-50 contrast-105 transition-all duration-300' : ''
          const cropX = c.crop_x ?? 50
          const cropY = c.crop_y ?? 50
          const cropScale = (c.crop_scale ?? 100) / 100
          const mediaStyle: React.CSSProperties = {
            objectPosition: `${cropX}% ${cropY}%`,
            transform: cropScale > 1.0 ? `scale(${cropScale})` : undefined,
            transformOrigin: `${cropX}% ${cropY}%`,
          }

          if (isImage(c.src)) {
            return (
              <div key={c.id} style={style} className={`absolute inset-0 ${fxClass}`}>
                {c.fit === 'contain_blur' && <img src={url} className="absolute inset-0 h-full w-full scale-110 object-cover blur-2xl opacity-60" />}
                <img
                  src={url}
                  style={c.fit === 'cover' ? mediaStyle : undefined}
                  className={`absolute inset-0 h-full w-full ${c.fit === 'cover' ? 'object-cover' : 'object-contain'}`}
                />
              </div>
            )
          }
          return (
            <div key={c.id} style={style} className={`absolute inset-0 ${fxClass}`}>
              {c.fit === 'contain_blur' && <div className="absolute inset-0 bg-black/40" />}
              <video
                ref={el => { vids.current[c.id] = el }} src={url} muted playsInline preload="auto"
                style={c.fit === 'cover' ? mediaStyle : undefined}
                className={`absolute inset-0 h-full w-full ${c.fit === 'cover' ? 'object-cover' : 'object-contain'}`}
              />
            </div>
          )
        })}

        {/* 2. Lớp tối mờ nền khi bật Spotlight / Focus comment */}
        {hasSpotlight && (
          <div className="pointer-events-none absolute inset-0 z-10 bg-black/75 transition-opacity duration-200" />
        )}

        {/* 3. Track Lớp phủ / Icon / Sticker (Sắp xếp theo thứ tự lớp z_order) */}
        {overlayClips
          .slice()
          .sort((a, b) => (a.z_order ?? 0) - (b.z_order ?? 0))
          .map((c, idx) => {
          const url = fileUrl(p.id, c.src)
          const on = time >= c.start && time < c.start + c.dur
          if (!on) return null
          const widthPct = c.scale_pct || 35
          const leftPct = c.x_pct || 50
          const topPct = c.y_pct || 30
          const isSpot = c.dim_bg || c.effect === 'spotlight'
          const zIndex = 20 + (c.z_order ?? idx)
          return (
            <div
              key={c.id}
              className={`pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 transition-all ${
                isSpot ? 'drop-shadow-[0_15px_35px_rgba(0,0,0,0.9)] scale-105 duration-300' : 'drop-shadow-2xl'
              }`}
              style={{
                left: `${leftPct}%`,
                top: `${topPct}%`,
                width: `${widthPct}%`,
                zIndex,
              }}
            >
              {isImage(c.src) ? (
                <img src={url} className="h-auto w-full object-contain" />
              ) : (
                <video src={url} muted playsInline autoPlay className="h-auto w-full object-contain" />
              )}
            </div>
          )
        })}

        {/* 4. Phụ đề từng từ */}
        {group && (
          <div
            className="pointer-events-none absolute left-0 right-0 z-30 flex -translate-y-1/2 flex-wrap justify-center px-[5%] text-center leading-[1.1] animate-in fade-in zoom-in-95 duration-100"
            style={{
              top: `${st.y_pct}%`, fontFamily: FONT_CSS[st.font] ?? FONT_CSS.Impact,
              fontSize: st.size * scale, gap: `0 ${st.size * scale * 0.25}px`,
              WebkitTextStroke: `${st.stroke_width * scale}px ${st.stroke_color}`, paintOrder: 'stroke fill',
              textTransform: st.uppercase ? 'uppercase' : 'none',
            }}
          >
            {group.words.map((w, i) => (
              <span key={i} style={{ color: w.emph ? st.emph_color : st.color }} className={w.emph ? 'scale-105 inline-block' : 'inline-block'}>
                {w.text}
              </span>
            ))}
          </div>
        )}

        {!p.words.length && !p.clips.length && (
          <div className="absolute inset-0 flex items-center justify-center p-8 text-center text-sm text-zinc-500">
            Viết script rồi chọn giọng và bấm <b className="mx-1 text-zinc-300">Tạo giọng</b> để bắt đầu
          </div>
        )}

        {/* Audio giọng đọc với cache buster đảm bảo cập nhật khi đổi giọng */}
        {p.voice_file && (
          <audio
            ref={voiceAudio}
            src={`${fileUrl(p.id, p.voice_file)}?v=${voiceVersion}_${p.words.length}`}
            preload="auto"
          />
        )}

        {/* Audio nhạc nền (BGM) */}
        {p.bgm_file && (
          <audio
            ref={bgmAudio}
            src={`${fileUrl(p.id, p.bgm_file)}`}
            loop
            preload="auto"
          />
        )}
      </div>
    </div>
  )
}
