import React from 'react';
import {
  Film,
  UploadCloud,
  Sparkles,
  Smartphone,
  Mic,
  Music,
  Bookmark,
  Settings,
  LogOut,
  Flame,
  Activity,
  ListOrdered,
  Workflow
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  onLogout: () => void;
  healthOk: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  onLogout,
  healthOk,
}) => {
  const navItems = [
    { id: 'upload', label: 'Upload Video', icon: UploadCloud },
    { id: 'studio', label: 'Clip Studio', icon: Sparkles },
    { id: 'shorts', label: 'Hasil Shorts & Drive', icon: Smartphone },
    { id: 'queue', label: 'Antrean Worker', icon: ListOrdered },
    { id: 'pipeline', label: 'Pipeline Otomatis', icon: Workflow },
    { id: 'preset', label: 'Preset', icon: Bookmark },
    { id: 'audio', label: 'Audio Library', icon: Music },
    { id: 'tts', label: 'Text-to-Speech', icon: Mic },
    { id: 'dashboard', label: 'Daftar Video', icon: Film },
    { id: 'settings', label: 'Pengaturan', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-ember-surface border-r border-ember-border flex flex-col h-screen fixed left-0 top-0 select-none z-20">
      {/* Brand Header */}
      <div className="p-6 border-b border-ember-border flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-[#C2410C] flex items-center justify-center text-white shadow-md shadow-[#C2410C]/20">
          <Flame className="w-6 h-6 fill-current" />
        </div>
        <div>
          <h1 className="font-display font-bold text-xl text-ember-text-primary tracking-tight leading-none">
            Ember Shorts
          </h1>
          <p className="text-xs text-ember-neutral font-mono mt-1">Local AI Clipper</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-150 text-left ${
                isActive
                  ? 'bg-ember-surface-raised text-[#C2410C] shadow-sm border-l-4 border-[#C2410C]'
                  : 'text-ember-text-secondary hover:bg-ember-surface-raised/60 hover:text-ember-text-primary'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-[#C2410C]' : 'text-ember-neutral'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Footer Info & Logout */}
      <div className="p-4 border-t border-ember-border space-y-3 bg-ember-surface/80">
        {/* System Health Status */}
        <div className="flex items-center justify-between px-2 py-1.5 bg-ember-surface-raised rounded-md text-xs font-mono">
          <span className="flex items-center space-x-1.5 text-ember-text-secondary">
            <Activity className="w-3.5 h-3.5 text-ember-neutral" />
            <span>Local Engine</span>
          </span>
          <span className="flex items-center space-x-1">
            <span
              className={`w-2 h-2 rounded-full ${healthOk ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}
            />
            <span className={healthOk ? 'text-emerald-700 font-semibold' : 'text-red-700 font-semibold'}>
              {healthOk ? 'Aktif' : 'Offline'}
            </span>
          </span>
        </div>

        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center space-x-2 px-3 py-2 text-sm text-ember-text-secondary hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Keluar Sesi (PIN)</span>
        </button>
      </div>
    </aside>
  );
};
