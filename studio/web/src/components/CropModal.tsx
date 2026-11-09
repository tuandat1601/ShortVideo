import { useRef, useState } from 'react'
import { api, fileUrl } from '../api'
import { isImage, type Clip, type Project } from '../types'

interface Props {
  project: Project
  clip: Clip
  onClose: () => void
  onApply: (cropX: number, cropY: number, cropScale: number) => void
  onSourceCreated?: (newSrc: string) => void
}

export default function CropModal({ project: p, clip, onClose, onApply, onSourceCreated }: Props) {
  const [cropX, setCropX] = useState<number>(clip.crop_x ?? 50)
  const [cropY, setCropY] = useState<number>(clip.crop_y ?? 50)
  const [cropScale, setCropScale] = useState<number>(clip.crop_scale ?? 100)
  const [isExporting, setIsExporting] = useState(false)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)

  const url = fileUrl(p.id, clip.src)
  const isImg = isImage(clip.src)

  // Tỷ lệ khung đích Shorts (mặc định 9:16)
  const targetRatio = p.width / p.height // ~0.5625

  // Xử lý kéo thả khung 9:16 trên video ngang
  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startY = e.clientY
    const origCropX = cropX
    const origCropY = cropY

    const onMove = (ev: PointerEvent) => {
      ev.preventDefault()
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      // Tỉ lệ % di chuyển chuột so với độ rộng container
      const dxPct = ((ev.clientX - startX) / rect.width) * 100
      const dyPct = ((ev.clientY - startY) / rect.height) * 100

      setCropX(Math.max(0, Math.min(100, Number((origCropX + dxPct).toFixed(1)))))
      setCropY(Math.max(0, Math.min(100, Number((origCropY + dyPct).toFixed(1)))))
    }

    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  // Cắt và xuất thành file mới độc lập
  const handleExportSource = async () => {
    setIsExporting(true)
    try {
      const stem = clip.src.split('/').pop()?.replace(/\.[^.]+$/, '') || 'clip'
      const res = await api.cropSource(p.id, clip.src, cropX, cropY, cropScale, `reframe_${stem}`)
      if (onSourceCreated) onSourceCreated(res.src)
      onApply(50, 50, 100) // Reset crop về giữa vì file mới đã là 9:16 chuẩn
      onClose()
    } catch (err) {
      alert('Lỗi xuất video cắt: ' + (err as Error).message)
    } finally {
      setIsExporting(false)
    }
  }

  // Kích thước của hộp crop 9:16 trên preview toàn cảnh
  // Hộp crop có chiều cao = 100% / (cropScale/100), chiều rộng = chiều cao * targetRatio
  const currentScale = cropScale / 100
  const cropBoxHeightPct = Math.min(100, 100 / currentScale)
  // Tùy theo tỷ lệ video gốc
  const mediaRatio = naturalSize ? naturalSize.w / naturalSize.h : 16 / 9
  const cropBoxWidthPct = Math.min(100, (cropBoxHeightPct * targetRatio) / mediaRatio * 100)

  // Vị trí của hộp crop: từ 0% đến (100% - cropBoxWidthPct)
  const leftPct = (cropX / 100) * (100 - cropBoxWidthPct)
  const topPct = (cropY / 100) * (100 - cropBoxHeightPct)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 select-none animate-in fade-in duration-200">
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col rounded-2xl border border-white/10 bg-zinc-900 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3.5 bg-zinc-950/50">
          <div className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-violet-600/30 text-sm">📐</span>
            <div>
              <h3 className="text-sm font-bold text-white">Căn góc & Cắt tỷ lệ 9:16 (Reframe)</h3>
              <p className="text-[11px] text-zinc-400">Kéo thả khung chữ nhật để chọn chính xác góc màn hình muốn lấy</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white transition"
          >
            ✕
          </button>
        </div>

        {/* Nội dung chính: Bên trái là toàn cảnh kéo chọn, bên phải là xem trước kết quả */}
        <div className="grid flex-1 grid-cols-1 md:grid-cols-[1fr_260px] gap-4 p-5 overflow-y-auto">
          {/* Cột trái: Khung hình video gốc + Khung 9:16 kéo thả */}
          <div className="flex flex-col gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              🖥️ Video màn hình gốc (Kéo khung màu tím để chọn vùng):
            </span>

            <div
              ref={containerRef}
              className="relative flex items-center justify-center rounded-xl overflow-hidden bg-black ring-1 ring-white/10 aspect-video shadow-inner cursor-crosshair"
            >
              {isImg ? (
                <img
                  ref={imgRef}
                  src={url}
                  alt="Original"
                  onLoad={e => setNaturalSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
                  className="h-full w-full object-contain pointer-events-none select-none"
                />
              ) : (
                <video
                  ref={videoRef}
                  src={url}
                  muted
                  playsInline
                  onLoadedMetadata={e => setNaturalSize({ w: e.currentTarget.videoWidth, h: e.currentTarget.videoHeight })}
                  className="h-full w-full object-contain pointer-events-none select-none"
                />
              )}

              {/* Lớp phủ làm tối các vùng bị cắt bỏ (Mask letterbox) */}
              <div className="pointer-events-none absolute inset-0 bg-black/45" />

              {/* Khung cắt 9:16 di động có thể kéo thả */}
              <div
                onPointerDown={handlePointerDown}
                className="group absolute cursor-grab active:cursor-grabbing rounded-lg border-2 border-violet-400 bg-transparent shadow-[0_0_25px_rgba(168,85,247,0.35)] transition-shadow ring-1 ring-white/40"
                style={{
                  width: `${cropBoxWidthPct}%`,
                  height: `${cropBoxHeightPct}%`,
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.55)',
                }}
              >
                {/* Lưới căn chỉnh 3x3 */}
                <div className="pointer-events-none grid h-full w-full grid-cols-3 grid-rows-3 opacity-40">
                  <div className="border-b border-r border-white/50" />
                  <div className="border-b border-r border-white/50" />
                  <div className="border-b border-white/50" />
                  <div className="border-b border-r border-white/50" />
                  <div className="border-b border-r border-white/50" />
                  <div className="border-b border-white/50" />
                  <div className="border-r border-white/50" />
                  <div className="border-r border-white/50" />
                  <div />
                </div>

                {/* Huy hiệu nhãn giữa khung */}
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <span className="rounded bg-violet-950/85 px-2 py-0.5 text-[10px] font-bold text-violet-200 border border-violet-500/40 shadow">
                    📱 9:16 Shorts
                  </span>
                </div>
              </div>
            </div>

            {/* Các nút bấm căn nhanh vị trí 1-click */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-medium text-zinc-400">Vị trí lấy mẫu nhanh (1-Click):</span>
              <div className="grid grid-cols-4 gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => { setCropX(0); setCropY(50) }}
                  className={`rounded-lg py-1.5 px-2 border transition font-medium ${cropX <= 5 ? 'border-violet-500 bg-violet-600/30 text-white' : 'border-white/5 bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ⬅️ Góc Trái (Code)
                </button>
                <button
                  type="button"
                  onClick={() => { setCropX(50); setCropY(50) }}
                  className={`rounded-lg py-1.5 px-2 border transition font-medium ${cropX > 40 && cropX < 60 ? 'border-violet-500 bg-violet-600/30 text-white' : 'border-white/5 bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ⏺️ Chính Giữa
                </button>
                <button
                  type="button"
                  onClick={() => { setCropX(100); setCropY(50) }}
                  className={`rounded-lg py-1.5 px-2 border transition font-medium ${cropX >= 95 ? 'border-violet-500 bg-violet-600/30 text-white' : 'border-white/5 bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}
                >
                  ➡️ Góc Phải (Browser)
                </button>
                <button
                  type="button"
                  onClick={() => { setCropX(50); setCropY(50); setCropScale(100) }}
                  className="rounded-lg py-1.5 px-2 border border-white/5 bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white"
                >
                  🎯 Đặt lại
                </button>
              </div>
            </div>

            {/* Thanh trượt tinh chỉnh thủ công */}
            <div className="grid grid-cols-3 gap-3 rounded-xl bg-zinc-950/40 p-3 border border-white/5">
              <label className="block">
                <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                  <span>Trục ngang (X)</span>
                  <span className="font-mono text-violet-300">{cropX}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={cropX}
                  onChange={e => setCropX(+e.target.value)}
                  className="w-full accent-violet-500"
                />
              </label>

              <label className="block">
                <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                  <span>Trục dọc (Y)</span>
                  <span className="font-mono text-violet-300">{cropY}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={cropY}
                  onChange={e => setCropY(+e.target.value)}
                  className="w-full accent-violet-500"
                />
              </label>

              <label className="block">
                <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
                  <span>Thu phóng (Zoom)</span>
                  <span className="font-mono text-violet-300">{cropScale}%</span>
                </div>
                <input
                  type="range"
                  min={100}
                  max={250}
                  value={cropScale}
                  onChange={e => setCropScale(+e.target.value)}
                  className="w-full accent-violet-500"
                />
              </label>
            </div>
          </div>

          {/* Cột phải: Xem trước chuẩn 9:16 trên điện thoại */}
          <div className="flex flex-col items-center gap-3 border-l border-white/10 pl-4">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              📱 Xem trước khi lên Shorts:
            </span>

            <div
              className="relative overflow-hidden rounded-2xl bg-black shadow-2xl ring-2 ring-violet-500/40 w-[170px] aspect-[9/16]"
            >
              {isImg ? (
                <img
                  src={url}
                  alt="Result"
                  style={{
                    objectFit: 'cover',
                    objectPosition: `${cropX}% ${cropY}%`,
                    transform: cropScale > 100 ? `scale(${cropScale / 100})` : undefined,
                    transformOrigin: `${cropX}% ${cropY}%`,
                  }}
                  className="h-full w-full"
                />
              ) : (
                <video
                  src={url}
                  autoPlay
                  loop
                  muted
                  playsInline
                  style={{
                    objectFit: 'cover',
                    objectPosition: `${cropX}% ${cropY}%`,
                    transform: cropScale > 100 ? `scale(${cropScale / 100})` : undefined,
                    transformOrigin: `${cropX}% ${cropY}%`,
                  }}
                  className="h-full w-full"
                />
              )}

              {/* Viền camera mô phỏng màn hình điện thoại */}
              <div className="pointer-events-none absolute top-2 left-1/2 -translate-x-1/2 h-1.5 w-10 rounded-full bg-white/20" />
            </div>

            <p className="text-[10px] text-zinc-500 text-center leading-relaxed">
              Vùng hiển thị đúng chuẩn màn hình dọc 9:16, không bị đen viền 2 bên.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/10 px-5 py-3.5 bg-zinc-950/70">
          <button
            type="button"
            onClick={handleExportSource}
            disabled={isExporting}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/30 px-3.5 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-900/40 transition disabled:opacity-40"
            title="Dùng FFmpeg cắt trực tiếp video này thành 1 file MP4 9:16 mới lưu vào thư mục Media"
          >
            {isExporting ? '⏳ Đang cắt...' : '✂️ Xuất thành Source video 9:16 mới'}
          </button>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-xs font-medium text-zinc-400 hover:bg-zinc-800 hover:text-white"
            >
              Hủy
            </button>
            <button
              type="button"
              onClick={() => { onApply(cropX, cropY, cropScale); onClose() }}
              className="rounded-lg bg-violet-600 px-5 py-2 text-xs font-bold text-white hover:bg-violet-500 shadow-lg shadow-violet-900/30 transition active:scale-95"
            >
              ✅ Áp dụng cho Clip này
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
