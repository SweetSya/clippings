import React, { useEffect, useRef, useState } from 'react';
import {
  Plus,
  Trash2,
  Pencil,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
  Bookmark,
  Crop,
  Type,
  Music,
  Mic,
  RefreshCw,
  Copy,
  Download,
  Upload,
} from 'lucide-react';
import { presetsApi } from '../services/api';
import { SubtitleFrame } from '../components/SubtitleFrame';
import { TextPreset } from '../types';
import { PresetEditorPage } from './PresetEditorPage';

export const PresetPage: React.FC = () => {
  const [viewMode, setViewMode] = useState<'list' | 'editor'>('list');
  const [selectedPreset, setSelectedPreset] = useState<TextPreset | null>(null);
  const [presets, setPresets] = useState<TextPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshingBuiltins, setRefreshingBuiltins] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchPresets = async () => {
    setLoading(true);
    try {
      const data = await presetsApi.list();
      setPresets(data);
    } catch (err) {
      console.error('Gagal memuat preset', err);
    } finally {
      setLoading(false);
    }
  };

  const handleResetBuiltins = async () => {
    setRefreshingBuiltins(true);
    try {
      const data = await presetsApi.resetBuiltins();
      setPresets(data);
      showNotification('success', 'Preset bawaan berhasil diperbarui ke versi terlengkap!');
    } catch (err: any) {
      showNotification('error', 'Gagal memperbarui preset bawaan.');
    } finally {
      setRefreshingBuiltins(false);
    }
  };

  useEffect(() => {
    fetchPresets();
  }, []);

  const openCreatePage = () => {
    setSelectedPreset(null);
    setViewMode('editor');
  };

  const openEditPage = (preset: TextPreset) => {
    setSelectedPreset(preset);
    setViewMode('editor');
  };

  const handleDelete = async (preset: TextPreset) => {
    if (preset.is_builtin) return;
    if (!window.confirm(`Hapus preset "${preset.name}"?`)) return;

    try {
      await presetsApi.remove(preset.id);
      showNotification('success', `Preset "${preset.name}" dihapus.`);
      await fetchPresets();
    } catch (err: any) {
      showNotification(
        'error',
        err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal menghapus preset.'
      );
    }
  };

  const handleExport = async (preset: TextPreset) => {
    try {
      const data = await presetsApi.exportPreset(preset.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `preset-${preset.name.replace(/[\\/*?:"<>|]/g, '').trim().replace(/\s+/g, '-').toLowerCase() || preset.id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showNotification('success', `Preset "${preset.name}" diekspor.`);
    } catch (err: any) {
      showNotification('error', err.response?.data?.detail || 'Gagal mengekspor preset.');
    }
  };

  const handleDuplicate = async (preset: TextPreset) => {
    try {
      const copy = await presetsApi.duplicate(preset.id);
      showNotification('success', `Preset "${copy.name}" berhasil diduplikat.`);
      await fetchPresets();
    } catch (err: any) {
      showNotification('error', err.response?.data?.detail || 'Gagal menduplikat preset.');
    }
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const imported = await presetsApi.importPreset(parsed);
      showNotification('success', `Preset "${imported.name}" berhasil diimpor.`);
      await fetchPresets();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      showNotification('error', typeof detail === 'string' ? detail : 'File JSON preset tidak valid.');
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // If user is editing or creating, render the dedicated PresetEditorPage!
  if (viewMode === 'editor') {
    return (
      <PresetEditorPage
        preset={selectedPreset}
        onBack={() => {
          setViewMode('list');
          setSelectedPreset(null);
        }}
        onSaved={(savedPreset) => {
          fetchPresets();
          setViewMode('list');
          setSelectedPreset(null);
          showNotification('success', `Preset "${savedPreset.name}" berhasil disimpan.`);
        }}
      />
    );
  }

  const builtins = presets.filter((p) => p.is_builtin);
  const customs = presets.filter((p) => !p.is_builtin);
  const [categoryFilter, setCategoryFilter] = useState('semua');

  const CATEGORY_LABELS: Record<string, string> = {
    semua: 'Semua',
    text: 'Teks',
    full: 'Full',
    streamer: 'Streamer',
    podcast: 'Podcast',
    educational: 'Edukasi',
    motivational: 'Motivasi',
    gaming: 'Gaming',
  };

  const filteredBuiltins = categoryFilter === 'semua'
    ? builtins
    : builtins.filter((p) => (p.category || 'text') === categoryFilter);

  const builtinsByCategory = filteredBuiltins.reduce<Record<string, TextPreset[]>>((acc, p) => {
    const cat = p.category || 'text';
    (acc[cat] = acc[cat] || []).push(p);
    return acc;
  }, {});

  const renderPresetCard = (preset: TextPreset) => (
    <div
      key={preset.id}
      className="bg-white border border-[#D6D3D1] rounded-2xl p-4 flex items-start space-x-4 shadow-xs hover:shadow-md transition-all group"
    >
      {/* 9:16 Real Scaled Thumbnail */}
      <div className="w-[100px] shrink-0">
        <SubtitleFrame
          font={preset.font}
          fontSize={preset.font_size}
          primaryColor={preset.primary_color}
          activeColor={preset.active_color}
          outlineWidth={preset.outline_width}
          shadowDepth={preset.shadow_depth}
          isUppercase={preset.is_uppercase}
          position={preset.subtitle_position}
          marginV={preset.margin_v}
          motionType={preset.motion_type}
          highlightBgColor={preset.highlight_bg_color}
          enableKeywordColor={preset.enable_keyword_color}
          keywordColor={preset.keyword_color}
          enableDynamicScaling={preset.enable_dynamic_scaling}
          enableEmojiInjection={preset.enable_emoji_injection}
          glowEffect={preset.glow_effect}
          framingLayout={preset.framing_layout}
          screenMode={preset.screen_mode}
          personShape={preset.person_shape}
          personScale={preset.person_scale}
          personOffsetX={preset.person_offset_x}
          personOffsetY={preset.person_offset_y}
          screenOffsetX={preset.screen_offset_x}
          screenOffsetY={preset.screen_offset_y}
          screenScale={preset.screen_scale}
          screenAspect={preset.screen_aspect}
          enableVocalDynamics={preset.enable_vocal_dynamics}
          videoFilter={preset.video_filter}
          overlayIntro={preset.enable_intro_title ? preset.name : null}
          overlayOutro={preset.enable_outro_cta ? preset.outro_cta_text || "Follow untuk lebih banyak!" : null}
          overlayLowerThird={preset.enable_lower_third ? preset.lower_third_text || "Nama" : null}
          className="rounded-xl shadow-xs"
        />
      </div>

      <div className="min-w-0 flex-1 space-y-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <h4 className="font-bold text-sm text-[#1C1917] truncate">{preset.name}</h4>
              {preset.is_builtin ? (
                <span className="px-1.5 py-0.5 bg-[#E7E5E4] text-[#57534E] text-[10px] font-semibold rounded-md uppercase tracking-wide shrink-0">
                  Bawaan
                </span>
              ) : (
                <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-semibold rounded-md uppercase tracking-wide shrink-0">
                  Kustom
                </span>
              )}
              {preset.category && preset.category !== 'text' && (
                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-[10px] font-semibold rounded-md uppercase tracking-wide shrink-0">
                  {preset.category}
                </span>
              )}
            </div>
            {preset.description && (
              <p className="text-xs text-[#78716C] line-clamp-2 mt-0.5">{preset.description}</p>
            )}
          </div>

          <div className="flex items-center space-x-1 shrink-0">
            <button
              type="button"
              onClick={() => openEditPage(preset)}
              className="p-1.5 text-[#78716C] hover:text-[#C2410C] hover:bg-[#F5F5F4] rounded-lg transition-colors"
              title={preset.is_builtin ? 'Duplikasi & Sesuaikan' : 'Ubah Preset di Halaman Editor'}
            >
              <Pencil className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => handleDuplicate(preset)}
              className="p-1.5 text-[#78716C] hover:text-[#C2410C] hover:bg-[#F5F5F4] rounded-lg transition-colors"
              title="Duplikat preset"
            >
              <Copy className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => handleExport(preset)}
              className="p-1.5 text-[#78716C] hover:text-[#C2410C] hover:bg-[#F5F5F4] rounded-lg transition-colors"
              title="Export preset ke JSON"
            >
              <Download className="w-4 h-4" />
            </button>
            {!preset.is_builtin && (
              <button
                type="button"
                onClick={() => handleDelete(preset)}
                className="p-1.5 text-[#78716C] hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Hapus Preset"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Feature Badges */}
        <div className="flex flex-wrap gap-1.5 text-[10px]">
          <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md border border-[#E7E5E4] flex items-center space-x-1">
            <Crop className="w-3 h-3 text-[#C2410C]" />
            <span>{preset.crop_mode === 'smart' ? 'Smart Crop' : 'Center Crop'}</span>
          </span>

          <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md border border-[#E7E5E4] flex items-center space-x-1">
            <Type className="w-3 h-3 text-[#C2410C]" />
            <span>
              {preset.font} • {preset.font_size}px
            </span>
          </span>

          <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-mono rounded-md border border-[#E7E5E4]">
            Pos Y: {preset.margin_v ?? 340}px
          </span>

          <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md border border-[#E7E5E4] flex items-center space-x-1">
            <Music className="w-3 h-3 text-[#C2410C]" />
            <span>BGM {Math.round((preset.bgm_volume ?? 0.2) * 100)}%</span>
          </span>

          {(preset.video_filter ?? 'none') !== 'none' && (
            <span className="px-2 py-0.5 bg-violet-50 text-violet-700 font-medium rounded-md border border-violet-200">
              🎬 {preset.video_filter}
            </span>
          )}

          {preset.use_voiceover && (
            <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 font-medium rounded-md border border-emerald-200 flex items-center space-x-1">
              <Mic className="w-3 h-3" />
              <span>Voiceover</span>
            </span>
          )}
        </div>

        {/* Color preview dots */}
        <div className="flex items-center space-x-2 pt-0.5">
          <div className="flex items-center space-x-1">
            <div
              className="w-3.5 h-3.5 rounded-full border border-black/20"
              style={{ backgroundColor: preset.active_color }}
              title={`Aktif: ${preset.active_color}`}
            />
            <div
              className="w-3.5 h-3.5 rounded-full border border-black/20"
              style={{ backgroundColor: preset.primary_color }}
              title={`Dasar: ${preset.primary_color}`}
            />
          </div>
          <span className="text-[10px] text-[#A8A29E]">Palet Teks</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Floating Top Notification */}
      {notification && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 pointer-events-auto max-w-xl w-auto animate-in fade-in slide-in-from-top-4 duration-200">
          <div
            className={`flex items-center space-x-3 px-5 py-3 rounded-2xl shadow-2xl border backdrop-blur-md ${
              notification.type === 'success'
                ? 'bg-[#1C1917]/95 text-white border-emerald-500/40 ring-1 ring-emerald-500/20'
                : 'bg-[#1C1917]/95 text-white border-rose-500/40 ring-1 ring-rose-500/20'
            }`}
          >
            {notification.type === 'success' ? (
              <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
            ) : (
              <div className="w-6 h-6 rounded-full bg-rose-500/20 flex items-center justify-center shrink-0">
                <AlertCircle className="w-4 h-4 text-rose-400" />
              </div>
            )}
            <span className="text-sm font-medium tracking-tight text-white/95">{notification.message}</span>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="text-stone-400 hover:text-white p-1 rounded-lg hover:bg-stone-800 transition-colors ml-2 shrink-0"
              title="Tutup"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-2xl text-[#1C1917] flex items-center space-x-2">
            <Bookmark className="w-6 h-6 text-[#C2410C]" />
            <span>Preset Template Studio</span>
          </h2>
          <p className="text-sm text-[#57534E] mt-1">
            Pusat konfigurasi template utuh (Framing Visual 9:16, Subtitle Karaoke, dan Musik/Voiceover).
          </p>
        </div>

        <div className="flex items-center space-x-2.5 self-start sm:self-auto">
          <input ref={fileInputRef} type="file" accept=".json,application/json" className="hidden" onChange={handleImportFile} />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="px-3.5 py-2.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#57534E] hover:text-[#1C1917] text-xs font-bold rounded-xl transition-all border border-[#D6D3D1] flex items-center space-x-1.5 disabled:opacity-50"
            title="Impor preset dari file JSON"
          >
            {importing ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C2410C]" /> : <Upload className="w-3.5 h-3.5 text-[#C2410C]" />}
            <span>Import</span>
          </button>
          <button
            type="button"
            onClick={handleResetBuiltins}
            disabled={refreshingBuiltins}
            className="px-3.5 py-2.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#57534E] hover:text-[#1C1917] text-xs font-bold rounded-xl transition-all border border-[#D6D3D1] flex items-center space-x-1.5 disabled:opacity-50"
            title="Sinkronkan dan muat ulang semua preset bawaan sistem ke versi terlengkap"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#C2410C] ${refreshingBuiltins ? 'animate-spin' : ''}`} />
            <span>Refresh Preset Bawaan</span>
          </button>

          <button
            type="button"
            onClick={openCreatePage}
            className="px-4 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-[#C2410C]/20 flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Tambah Preset Baru</span>
          </button>
        </div>
      </div>

      {/* Preset List Grid */}
      {loading ? (
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-12 text-center">
          <Loader2 className="w-6 h-6 animate-spin text-[#C2410C] mx-auto" />
        </div>
      ) : presets.length === 0 ? (
        <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-12 text-center space-y-2">
          <Bookmark className="w-8 h-8 text-[#D6D3D1] mx-auto" />
          <p className="text-sm text-[#78716C]">Belum ada preset.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {customs.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-bold text-sm text-[#1C1917] flex items-center space-x-2">
                <span>Preset Kustom Saya</span>
                <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full text-xs font-mono">
                  {customs.length}
                </span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {customs.map(renderPresetCard)}
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="font-bold text-sm text-[#1C1917] flex items-center space-x-2">
                <span>Preset Bawaan Sistem</span>
                <span className="px-2 py-0.5 bg-[#E7E5E4] text-[#57534E] rounded-full text-xs font-mono">
                  {builtins.length}
                </span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(CATEGORY_LABELS).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setCategoryFilter(id)}
                    className={`px-2.5 py-1 text-[11px] font-bold rounded-full transition-all ${
                      categoryFilter === id
                        ? 'bg-[#C2410C] text-white'
                        : 'bg-[#F5F5F4] text-[#57534E] hover:bg-[#E7E5E4]'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {Object.entries(builtinsByCategory).map(([cat, list]) => (
              <div key={cat} className="space-y-2">
                <h4 className="font-semibold text-xs text-[#78716C] uppercase tracking-wider">
                  {CATEGORY_LABELS[cat] || cat} ({list.length})
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {list.map(renderPresetCard)}
                </div>
              </div>
            ))}
            {filteredBuiltins.length === 0 && (
              <p className="text-xs text-[#78716C]">Tidak ada preset bawaan di kategori ini.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PresetPage;
