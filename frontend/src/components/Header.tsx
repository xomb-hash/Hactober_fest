import { FileText } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface Props {
  title: string;
  description: string;
  onLoadSample?: () => void;
}

export function Header({ title, description, onLoadSample }: Props) {
  return (
    <header className="border-b border-slate-200 bg-white px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-base font-semibold text-slate-900">{title}</h1>
          <StatusBadge status="demo" showIcon={false} />
        </div>
        <p className="text-xs text-slate-500 mt-0.5 truncate">{description}</p>
      </div>

      {onLoadSample && (
        <button
          id="load-sample-report-btn"
          onClick={onLoadSample}
          className="btn-secondary flex-shrink-0"
          title="Load the synthetic sample report into the document input"
        >
          <FileText size={14} />
          Load sample report
        </button>
      )}
    </header>
  );
}
