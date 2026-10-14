import type { ExtractionStatus, AnchorMatchStatus, StageStatus } from '../types/helixguard';
import { CheckCircle, AlertTriangle, XCircle, Clock, Minus, SkipForward } from 'lucide-react';

interface Props {
  status: ExtractionStatus | AnchorMatchStatus | StageStatus | 'demo' | string;
  label?: string;
  showIcon?: boolean;
}

const CONFIG: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
  verified:          { cls: 'badge-verified',  icon: <CheckCircle size={11} />, label: 'Verified' },
  matched:           { cls: 'badge-verified',  icon: <CheckCircle size={11} />, label: 'Matched' },
  success:           { cls: 'badge-verified',  icon: <CheckCircle size={11} />, label: 'Success' },
  candidate:         { cls: 'badge-candidate', icon: <Clock size={11} />,       label: 'Candidate' },
  running:           { cls: 'badge-candidate', icon: <Clock size={11} />,       label: 'Running' },
  recovery_required: { cls: 'badge-warning',   icon: <AlertTriangle size={11} />, label: 'Recovery Required' },
  warning:           { cls: 'badge-warning',   icon: <AlertTriangle size={11} />, label: 'Warning' },
  unverified:        { cls: 'badge-warning',   icon: <AlertTriangle size={11} />, label: 'Unverified' },
  failed:            { cls: 'badge-error',     icon: <XCircle size={11} />,     label: 'Failed' },
  error:             { cls: 'badge-error',     icon: <XCircle size={11} />,     label: 'Error' },
  rejected:          { cls: 'badge-error',     icon: <XCircle size={11} />,     label: 'Rejected' },
  not_checked:       { cls: 'badge-skipped',   icon: <Minus size={11} />,       label: 'Not Checked' },
  abstained:         { cls: 'badge-abstained', icon: <Minus size={11} />,       label: 'Abstained' },
  skipped:           { cls: 'badge-skipped',   icon: <SkipForward size={11} />, label: 'Skipped' },
  pending:           { cls: 'badge-skipped',   icon: <Clock size={11} />,       label: 'Pending' },
  demo:              { cls: 'badge-demo',      icon: null,                      label: 'DEMO MODE' },
  ambiguous:         { cls: 'badge-warning',   icon: <AlertTriangle size={11} />, label: 'Ambiguous' },
};

export function StatusBadge({ status, label, showIcon = true }: Props) {
  const cfg = CONFIG[status] ?? { cls: 'badge-skipped', icon: null, label: status };
  const displayLabel = label ?? cfg.label;
  return (
    <span className={cfg.cls} aria-label={`Status: ${displayLabel}`}>
      {showIcon && cfg.icon}
      {displayLabel}
    </span>
  );
}
