import { Server, Sparkles } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface Props {
  title: string;
  description: string;
  isLiveMode?: boolean;
  onToggleMode?: (live: boolean) => void;
  backendReachable?: boolean;
}

export function Header({
  title,
  description,
  isLiveMode = true,
  onToggleMode,
  backendReachable = false,
}: Props) {
  return (
    <header className="border-b border-slate-200 bg-white px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-base font-semibold text-slate-900">{title}</h1>
          {isLiveMode ? (
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border ${
                backendReachable
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  backendReachable ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                }`}
              />
              {backendReachable ? 'LIVE BACKEND (Engine + Middleware)' : 'BACKEND CONNECTING (Port 8000)'}
            </span>
          ) : (
            <StatusBadge status="demo" showIcon={false} />
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5 truncate">{description}</p>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {onToggleMode && (
          <button
            id="toggle-backend-mode-btn"
            onClick={() => onToggleMode(!isLiveMode)}
            className={`btn-secondary text-xs flex items-center gap-1.5 ${
              isLiveMode ? 'text-emerald-700 border-emerald-300' : 'text-slate-600'
            }`}
            title="Toggle between Live FastAPI/C++ backend and offline synthetic demo mode"
          >
            {isLiveMode ? <Server size={13} className="text-emerald-600" /> : <Sparkles size={13} />}
            {isLiveMode ? 'Switch to Demo Mock' : 'Switch to Live Backend'}
          </button>
        )}
      </div>
    </header>
  );
}
