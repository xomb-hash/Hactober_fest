import { Dna, LayoutDashboard, Scissors, AlignCenter, FlaskConical, Info, Activity } from 'lucide-react';

export type NavPage = 'dashboard' | 'extraction' | 'alignment' | 'test-cases' | 'about';

interface Props {
  currentPage: NavPage;
  onNavigate: (page: NavPage) => void;
}

const NAV_ITEMS: { id: NavPage; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard',  label: 'Dashboard',           icon: <LayoutDashboard size={16} /> },
  { id: 'extraction', label: 'Sequence Extraction',  icon: <Scissors size={16} /> },
  { id: 'alignment',  label: 'Alignment',            icon: <AlignCenter size={16} /> },
  { id: 'test-cases', label: 'Test Cases',           icon: <FlaskConical size={16} /> },
  { id: 'about',      label: 'About / Limitations',  icon: <Info size={16} /> },
];

export function Sidebar({ currentPage, onNavigate }: Props) {
  return (
    <aside className="sidebar w-56 flex-shrink-0 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-100">
        <div className="w-7 h-7 rounded-md bg-accent-600 flex items-center justify-center flex-shrink-0">
          <Dna size={16} className="text-white" />
        </div>
        <div>
          <span className="text-sm font-bold text-slate-900 tracking-tight">HelixGuard</span>
          <p className="text-[10px] text-slate-400 leading-none mt-0.5">Genomic Verification</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5" aria-label="Main navigation">
        {NAV_ITEMS.map(({ id, label, icon }) => (
          <button
            key={id}
            id={`nav-${id}`}
            onClick={() => onNavigate(id)}
            className={`nav-item w-full text-left ${currentPage === id ? 'active' : ''}`}
            aria-current={currentPage === id ? 'page' : undefined}
          >
            <span className="flex-shrink-0">{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* System status */}
      <div className="px-3 py-3 border-t border-slate-100 space-y-2">
        <div className="flex items-center gap-1.5">
          <Activity size={11} className="text-amber-500" />
          <span className="text-[10px] font-semibold text-amber-700 uppercase tracking-wider">Demo Mode</span>
        </div>
        <p className="text-[10px] text-slate-400 leading-snug">
          Running predefined mock scenarios. No backend connected.
        </p>
      </div>
    </aside>
  );
}
