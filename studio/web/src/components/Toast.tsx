import { useEffect, useState } from 'react'

export interface ToastAction {
  label: string
  onClick?: () => void
  href?: string
  download?: string
  primary?: boolean
}

export interface ToastItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  elapsed_s?: number
  duration?: number // ms (mặc định 4500ms cho success/info, 0 cho không tự tắt)
  actions?: ToastAction[]
}

interface Props {
  toasts: ToastItem[]
  onDismiss: (id: string) => void
}

export default function ToastContainer({ toasts, onDismiss }: Props) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none select-none">
      {toasts.map(toast => (
        <ToastCard key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
      ))}
    </div>
  )
}

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const [progress, setProgress] = useState(100)
  const duration = toast.duration ?? (toast.type === 'error' ? 0 : 5000)

  useEffect(() => {
    if (duration <= 0) return
    const step = 50
    const totalSteps = duration / step
    const interval = setInterval(() => {
      setProgress(p => {
        const next = p - 100 / totalSteps
        if (next <= 0) {
          clearInterval(interval)
          onDismiss()
          return 0
        }
        return next
      })
    }, step)

    return () => clearInterval(interval)
  }, [duration, onDismiss])

  const typeConfig = {
    success: {
      icon: '✅',
      border: 'border-emerald-500/40',
      bgGlow: 'shadow-[0_8px_30px_rgba(16,185,129,0.15)]',
      titleColor: 'text-emerald-400',
      barColor: 'bg-emerald-500',
    },
    error: {
      icon: '❌',
      border: 'border-rose-500/50',
      bgGlow: 'shadow-[0_8px_30px_rgba(244,63,94,0.2)]',
      titleColor: 'text-rose-400',
      barColor: 'bg-rose-500',
    },
    warning: {
      icon: '⚠️',
      border: 'border-amber-500/40',
      bgGlow: 'shadow-[0_8px_30px_rgba(245,158,11,0.15)]',
      titleColor: 'text-amber-400',
      barColor: 'bg-amber-500',
    },
    info: {
      icon: 'ℹ️',
      border: 'border-violet-500/40',
      bgGlow: 'shadow-[0_8px_30px_rgba(139,92,246,0.15)]',
      titleColor: 'text-violet-400',
      barColor: 'bg-violet-500',
    },
  }[toast.type]

  return (
    <div
      className={`pointer-events-auto relative overflow-hidden rounded-2xl border ${typeConfig.border} bg-zinc-900/95 p-3.5 backdrop-blur-xl ${typeConfig.bgGlow} transition-all duration-300 animate-in slide-in-from-bottom-5 fade-in ring-1 ring-white/10`}
    >
      <div className="flex items-start gap-2.5">
        <span className="text-base shrink-0 leading-none mt-0.5">{typeConfig.icon}</span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className={`text-xs font-bold leading-tight ${typeConfig.titleColor}`}>
              {toast.title}
            </span>
            {toast.elapsed_s !== undefined && (
              <span className="rounded bg-white/10 px-1.5 py-0.2 text-[10px] font-mono text-zinc-300">
                ⏱️ {toast.elapsed_s.toFixed(1)}s
              </span>
            )}
          </div>

          {toast.message && (
            <p className="mt-1 text-xs text-zinc-300 leading-snug break-words">
              {toast.message}
            </p>
          )}

          {/* Action buttons (Mở Finder, Tải về, Xem video...) */}
          {toast.actions && toast.actions.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5 pt-1 border-t border-white/5">
              {toast.actions.map((act, i) =>
                act.href ? (
                  <a
                    key={i}
                    href={act.href}
                    download={act.download}
                    target={act.download ? undefined : '_blank'}
                    rel="noreferrer"
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
                      act.primary
                        ? 'bg-violet-600 text-white hover:bg-violet-500 shadow-sm'
                        : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-white'
                    }`}
                  >
                    {act.label}
                  </a>
                ) : (
                  <button
                    key={i}
                    type="button"
                    onClick={act.onClick}
                    className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
                      act.primary
                        ? 'bg-violet-600 text-white hover:bg-violet-500 shadow-sm'
                        : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-white'
                    }`}
                  >
                    {act.label}
                  </button>
                )
              )}
            </div>
          )}
        </div>

        {/* Nút tắt dấu X */}
        <button
          type="button"
          onClick={onDismiss}
          className="-mr-1 -mt-1 rounded-md p-1 text-zinc-400 hover:bg-white/10 hover:text-white transition"
          title="Đóng thông báo"
        >
          <span className="text-xs font-bold leading-none block">✕</span>
        </button>
      </div>

      {/* Thanh chạy thời gian tự động đóng */}
      {duration > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/5 overflow-hidden">
          <div
            className={`h-full ${typeConfig.barColor} transition-all duration-75 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  )
}
