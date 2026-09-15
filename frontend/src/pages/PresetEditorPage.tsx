import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
  Bookmark,
  Crop,
  Type,
  Music,
  Mic,
  Sliders,
  Sparkles,
  Palette,
  Volume2,
} from 'lucide-react';
import { presetsApi, audioApi, ttsApi } from '../services/api';
import { SubtitleFrame } from '../components/SubtitleFrame';
import {
  TextPreset,
  TextPresetPayload,
  AudioTrack,
  VoiceItem,
  AudioMode,
  NarrationStyle,
  SubtitleMotionType,
} from '../types';

interface PresetEditorPageProps {
  preset: TextPreset | null;
  onBack: () => void;
  onSaved: (savedPreset: TextPreset) => void;
}

interface PresetFormState extends TextPresetPayload {
  name: string;
  description: string;
  crop_mode: 'smart' | 'center' | 'manual';
  crop_offset_x: number;
  smart_deadzone: number;
  smart_pan_seconds: number;
  font: string;
  font_size: number;
  primary_color: string;
  active_color: string;
  subtitle_position: 'bottom' | 'middle' | 'top' | 'custom' | string;
  margin_v: number;
  outline_width: number;
  shadow_depth: number;
  is_uppercase: boolean;
  motion_type: SubtitleMotionType;
  highlight_bg_color: string;
  enable_keyword_color: boolean;
  keyword_color: string;
  enable_dynamic_scaling: boolean;
  enable_emoji_injection: boolean;
  glow_effect: boolean;
  audio_track_id: string | null;
  bgm_volume: number;
  audio_mode: AudioMode;
  use_voiceover: boolean;
  narration_voice: string;
  narration_style: NarrationStyle;
}

const FONT_OPTIONS = ['Poppins', 'Inter', 'Playfair Display', 'Arial', 'Anton', 'Montserrat'];

const COLOR_SWATCHES = [
  { label: 'Gold / Amber', hex: '#FFCC00' },
  { label: 'Terracotta', hex: '#C2410C' },
  { label: 'Cyan Neon', hex: '#00F0FF' },
  { label: 'Emerald Neon', hex: '#10B981' },
  { label: 'Sky Blue', hex: '#38BDF8' },
  { label: 'Rose Pink', hex: '#F43F5E' },
  { label: 'Pure White', hex: '#FFFFFF' },
];

const DEFAULT_MARGIN_V: Record<string, number> = {
  bottom: 340,
  middle: 920,
  top: 1540,
};

export const PresetEditorPage: React.FC<PresetEditorPageProps> = ({
  preset,
  onBack,
  onSaved,
}) => {
  const isEditing = Boolean(preset);

  const [form, setForm] = useState<PresetFormState>(() => ({
    name: preset?.name ?? '',
    description: preset?.description ?? '',
    crop_mode: (preset?.crop_mode as any) ?? 'smart',
    crop_offset_x: preset?.crop_offset_x ?? 0,
    smart_deadzone: preset?.smart_deadzone ?? 0.4,
    smart_pan_seconds: preset?.smart_pan_seconds ?? 0.4,
    font: preset?.font || 'Poppins',
    font_size: preset?.font_size || 44,
    primary_color: preset?.primary_color || '#FFFFFF',
    active_color: preset?.active_color || '#FFCC00',
    subtitle_position: preset?.subtitle_position || 'bottom',
    margin_v: preset?.margin_v ?? (DEFAULT_MARGIN_V[preset?.subtitle_position || 'bottom'] || 340),
    outline_width: preset?.outline_width ?? 3,
    shadow_depth: preset?.shadow_depth ?? 2,
    is_uppercase: preset?.is_uppercase ?? true,
    motion_type: (preset?.motion_type as SubtitleMotionType) || 'karaoke',
    highlight_bg_color: preset?.highlight_bg_color || '#FFCC00',
    enable_keyword_color: preset?.enable_keyword_color ?? true,
    keyword_color: preset?.keyword_color || '#10B981',
    enable_dynamic_scaling: Boolean(preset?.enable_dynamic_scaling),
    enable_emoji_injection: Boolean(preset?.enable_emoji_injection),
    glow_effect: Boolean(preset?.glow_effect),
    audio_track_id: preset?.audio_track_id ?? null,
    bgm_volume: preset?.bgm_volume ?? 0.2,
    audio_mode: preset?.audio_mode || 'mix',
    use_voiceover: Boolean(preset?.use_voiceover),
    narration_voice: preset?.narration_voice || 'id-ID-ArdiNeural',
    narration_style: preset?.narration_style || 'hook_story',
  }));

  const [activeTab, setActiveTab] = useState<'info' | 'visual' | 'text' | 'audio'>('info');
  const [audioTracks, setAudioTracks] = useState<AudioTrack[]>([]);
  const [voices, setVoices] = useState<VoiceItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  useEffect(() => {
    Promise.all([
      audioApi.list().catch(() => []),
      ttsApi.getVoices().catch(() => []),
    ]).then(([tracks, voiceList]) => {
      setAudioTracks(tracks);
      setVoices(voiceList);
    });
  }, []);

  const handlePositionPresetClick = (pos: 'bottom' | 'middle' | 'top') => {
    setForm((prev) => ({
      ...prev,
      subtitle_position: pos,
      margin_v: DEFAULT_MARGIN_V[pos],
    }));
  };

  const handleCustomYChange = (val: number) => {
    setForm((prev) => ({
      ...prev,
      subtitle_position: 'custom',
      margin_v: val,
    }));
  };

  const handleSubmit = async () => {
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      showNotification('error', 'Nama preset wajib diisi.');
      return;
    }

    setSaving(true);
    try {
      const payload: TextPresetPayload = {
        name: trimmedName,
        description: form.description.trim() || null,
        crop_mode: form.crop_mode,
        crop_offset_x: form.crop_offset_x,
        smart_deadzone: form.smart_deadzone,
        smart_pan_seconds: form.smart_pan_seconds,
        font: form.font,
        font_size: form.font_size,
        primary_color: form.primary_color,
        active_color: form.active_color,
        subtitle_position: form.subtitle_position,
        margin_v: form.margin_v,
        outline_width: form.outline_width,
        shadow_depth: form.shadow_depth,
        is_uppercase: form.is_uppercase,
        motion_type: form.motion_type,
        highlight_bg_color: form.highlight_bg_color,
        enable_keyword_color: form.enable_keyword_color,
        keyword_color: form.keyword_color,
        enable_dynamic_scaling: form.enable_dynamic_scaling,
        enable_emoji_injection: form.enable_emoji_injection,
        glow_effect: form.glow_effect,
        audio_track_id: form.audio_track_id || null,
        bgm_volume: form.bgm_volume,
        audio_mode: form.audio_mode,
        use_voiceover: form.use_voiceover,
        narration_voice: form.narration_voice,
        narration_style: form.narration_style,
      };

      let result: TextPreset;
      if (preset && !preset.is_builtin) {
        result = await presetsApi.update(preset.id, payload);
        showNotification('success', `Preset "${trimmedName}" berhasil diperbarui.`);
      } else {
        result = await presetsApi.create(payload);
        showNotification('success', `Preset "${trimmedName}" berhasil dibuat.`);
      }

      onSaved(result);
    } catch (err: any) {
      showNotification(
        'error',
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          'Gagal menyimpan preset.'
      );
    } finally {
      setSaving(false);
    }
  };

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
            <span className="text-sm font-medium tracking-tight text-white/95">
              {notification.message}
            </span>
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

      {/* Page Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E7E5E4]">
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={onBack}
            className="p-2 bg-white border border-[#D6D3D1] hover:bg-[#F5F5F4] text-[#1C1917] rounded-xl transition-all shadow-xs"
            title="Kembali ke Daftar Preset"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          <div>
            <div className="flex items-center space-x-2">
              <h2 className="font-display font-bold text-2xl text-[#1C1917]">
                {isEditing ? `Ubah Preset: ${preset?.name}` : 'Buat Template Preset Baru'}
              </h2>
              {preset?.is_builtin && (
                <span className="px-2 py-0.5 bg-[#E7E5E4] text-[#57534E] text-xs font-semibold rounded-md uppercase">
                  Bawaan (Akan disimpan sebagai salinan baru)
                </span>
              )}
            </div>
            <p className="text-xs text-[#57534E] mt-0.5">
              Halaman khusus untuk mengonfigurasi framing vertikal 9:16, tipografi subtitle, dan audio template.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-end sm:self-auto">
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 text-xs font-bold text-[#57534E] hover:bg-[#F5F5F4] rounded-xl transition-colors"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !form.name.trim()}
            className="px-6 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#C2410C]/25 transition-all disabled:opacity-50 flex items-center space-x-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>{isEditing && !preset?.is_builtin ? 'Simpan Perubahan' : 'Simpan Sebagai Preset'}</span>
          </button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column (Sticky 9:16 Phone Preview) */}
        <div className="lg:col-span-4 flex flex-col items-center lg:sticky lg:top-6">
          <div className="w-full flex items-center justify-between mb-2 px-1">
            <span className="text-xs font-bold text-[#78716C] uppercase tracking-wider">
              Pratinjau Langsung 9:16
            </span>
            <span className="text-[11px] font-mono text-[#78716C] bg-white px-2 py-0.5 rounded border border-[#E7E5E4]">
              1080 × 1920
            </span>
          </div>

          {/* Scaled Phone Frame */}
          <div className="w-[230px] p-[6px] bg-[#1C1917] rounded-[36px] shadow-2xl">
            <SubtitleFrame
              font={form.font}
              fontSize={form.font_size}
              primaryColor={form.primary_color}
              activeColor={form.active_color}
              outlineWidth={form.outline_width}
              shadowDepth={form.shadow_depth}
              isUppercase={form.is_uppercase}
              position={form.subtitle_position}
              marginV={form.margin_v}
              motionType={form.motion_type}
              highlightBgColor={form.highlight_bg_color}
              enableKeywordColor={form.enable_keyword_color}
              keywordColor={form.keyword_color}
              enableDynamicScaling={form.enable_dynamic_scaling}
              enableEmojiInjection={form.enable_emoji_injection}
              glowEffect={form.glow_effect}
              className="rounded-[30px]"
            />
          </div>

          {/* Quick Summary Card */}
          <div className="mt-4 w-full bg-white p-4 rounded-2xl border border-[#E7E5E4] text-xs space-y-2 text-[#57534E] shadow-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Crop className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Framing Kamera:</span>
              </span>
              <span className="font-medium text-[#1C1917]">
                {form.crop_mode === 'smart' ? 'Smart (Ikuti Wajah)' : 'Center Crop'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Gaya Animasi:</span>
              </span>
              <span className="font-bold text-[#C2410C] capitalize">
                {form.motion_type === 'single_word_pop'
                  ? 'Hormozi Pop'
                  : form.motion_type === 'background_box'
                  ? 'Highlighter Box'
                  : form.motion_type === 'typewriter'
                  ? 'Typewriter'
                  : form.motion_type === 'slide_up'
                  ? 'Slide Up'
                  : 'Karaoke'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Type className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Tipografi Teks:</span>
              </span>
              <span className="font-medium text-[#1C1917]">
                {form.font} • {form.font_size}px
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Sliders className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Posisi Y Subtitle:</span>
              </span>
              <span className="font-mono font-bold text-[#C2410C]">
                {form.margin_v} px
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Music className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Musik Latar (BGM):</span>
              </span>
              <span className="font-medium text-[#1C1917]">
                {Math.round(form.bgm_volume * 100)}% ({form.audio_mode})
              </span>
            </div>

            {form.use_voiceover && (
              <div className="flex items-center justify-between text-emerald-700 pt-1 border-t border-[#F5F5F4] font-semibold">
                <span className="flex items-center space-x-1">
                  <Mic className="w-3.5 h-3.5" />
                  <span>Voiceover AI:</span>
                </span>
                <span>Aktif</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Column (Organized Settings & Tabs) */}
        <div className="lg:col-span-8 space-y-5">
          {/* Section Navigation Tabs */}
          <div className="grid grid-cols-4 gap-1 p-1 bg-[#F5F5F4] rounded-2xl border border-[#E7E5E4]">
            <button
              type="button"
              onClick={() => setActiveTab('info')}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === 'info'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
            >
              <Bookmark className="w-3.5 h-3.5" />
              <span>Informasi</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('visual')}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === 'visual'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
            >
              <Crop className="w-3.5 h-3.5" />
              <span>Framing Visual</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('text')}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === 'text'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
            >
              <Type className="w-3.5 h-3.5" />
              <span>Tipografi & Subtitle</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('audio')}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === 'audio'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>Audio & Narasi</span>
            </button>
          </div>

          {/* TAB 1: INFORMASI UMUM */}
          {activeTab === 'info' && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-4 shadow-xs">
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-1.5">
                  Nama Template Preset <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Contoh: TikTok Viral Bold, Cyberpunk Neon, Podcast Dark..."
                  className="w-full px-4 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] focus:bg-white outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-1.5">
                  Deskripsi Singkat (Opsional)
                </label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Jelaskan karakteristik preset ini (misal: Font tebal kuning aktif, smart follow face, cocok untuk video monolog)..."
                  rows={4}
                  className="w-full px-4 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] focus:bg-white outline-none resize-none transition-all"
                />
              </div>
            </div>
          )}

          {/* TAB 2: FRAMING VISUAL (9:16) */}
          {activeTab === 'visual' && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-5 shadow-xs">
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <Crop className="w-4 h-4 text-[#C2410C]" />
                  <span>Mode Pemotongan 9:16</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, crop_mode: 'smart' })}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      form.crop_mode === 'smart'
                        ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                        : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                    }`}
                  >
                    <div className="font-bold text-sm">👁️ Ikuti Wajah (Smart Crop)</div>
                    <div className="text-xs opacity-80 mt-1">
                      Kamera AI otomatis melacak posisi pembicara agar selalu berada di dalam frame 9:16.
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setForm({ ...form, crop_mode: 'center' })}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      form.crop_mode === 'center'
                        ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                        : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                    }`}
                  >
                    <div className="font-bold text-sm">📐 Tengah (Center Crop)</div>
                    <div className="text-xs opacity-80 mt-1">
                      Kamera statis tetap berada tepat di tengah frame video sumber secara konsisten.
                    </div>
                  </button>
                </div>
              </div>

              {form.crop_mode === 'smart' && (
                <div className="space-y-4 pt-4 border-t border-[#E7E5E4]">
                  <div>
                    <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                      <span className="font-bold">Batas Gerak Kepala (Deadzone)</span>
                      <span className="font-mono font-bold text-[#C2410C]">
                        {Math.round(form.smart_deadzone * 100)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="10"
                      max="90"
                      step="5"
                      value={Math.round(form.smart_deadzone * 100)}
                      onChange={(e) =>
                        setForm({ ...form, smart_deadzone: parseInt(e.target.value) / 100 })
                      }
                      className="w-full accent-[#C2410C] cursor-pointer"
                    />
                    <p className="text-[11px] text-[#78716C] mt-1">
                      Kepala bebas bergerak di pita tengah selebar {Math.round(form.smart_deadzone * 100)}% tanpa
                      menggeser kamera, sehingga hasil potongan video tidak goyang berlebihan.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TIPOGRAFI & SUBTITLE */}
          {activeTab === 'text' && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-6 shadow-xs">
              {/* 1. GAYA ANIMASI UTAMA (MOTION TYPES) */}
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2.5 flex items-center space-x-1.5">
                  <Sparkles className="w-4 h-4 text-[#C2410C]" />
                  <span>Gaya Animasi Subtitle (Motion Type)</span>
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {[
                    {
                      id: 'single_word_pop',
                      name: 'Hormozi Pop (1 Kata)',
                      badge: 'Retensi Tertinggi',
                      desc: 'Hanya menampilkan 1 kata per waktu dengan zoom bounce cepat. Sangat agresif menahan fokus penonton.',
                      icon: '🔥',
                    },
                    {
                      id: 'karaoke',
                      name: 'Karaoke Highlight',
                      badge: 'Paling Populer',
                      desc: '3-4 kata sekaligus dalam satu baris, kata yang sedang diucapkan menyala terang secara real-time.',
                      icon: '🎤',
                    },
                    {
                      id: 'background_box',
                      name: 'Highlighter Sticker',
                      badge: 'CapCut / Opus',
                      desc: 'Kata aktif dibungkus badge stiker berlatar kontras tinggi seperti distabilo agar mencolok.',
                      icon: '🏷️',
                    },
                    {
                      id: 'typewriter',
                      name: 'Typewriter Reveal',
                      badge: 'Storytelling',
                      desc: 'Kata muncul satu per satu berurutan dan menetap sampai akhir kalimat. Cocok untuk narasi edukatif.',
                      icon: '⌨️',
                    },
                    {
                      id: 'slide_up',
                      name: 'Slide Up & Fade',
                      badge: 'Sinematik',
                      desc: 'Kalimat meluncur halus dari bawah dengan transisi fade-in elegan. Tampilan bersih dan modern.',
                      icon: '⬆️',
                    },
                  ].map((m) => {
                    const isSelected = form.motion_type === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setForm({ ...form, motion_type: m.id as any })}
                        className={`p-4 rounded-xl border text-left transition-all relative ${
                          isSelected
                            ? 'bg-[#FFF7ED] border-[#C2410C] shadow-sm ring-1 ring-[#C2410C]'
                            : 'bg-white border-[#E7E5E4] hover:bg-[#F5F5F4]'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-xl">{m.icon}</span>
                            <span className="font-bold text-sm text-[#1C1917]">{m.name}</span>
                          </div>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            isSelected ? 'bg-[#C2410C] text-white' : 'bg-stone-100 text-[#78716C]'
                          }`}>
                            {m.badge}
                          </span>
                        </div>
                        <p className="text-xs text-[#78716C] mt-2 leading-relaxed">{m.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* JIKA BACKGROUND BOX DIPILIH: PILIH WARNA BACKGROUND STIKER */}
              {form.motion_type === 'background_box' && (
                <div className="p-4 bg-[#FFF7ED] border border-[#FDBA74] rounded-2xl space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[#9A3412] uppercase tracking-wider flex items-center space-x-1.5">
                      <Palette className="w-3.5 h-3.5" />
                      <span>Warna Background Stiker (Highlighter Box)</span>
                    </label>
                    <span className="font-mono text-xs font-bold text-[#C2410C]">
                      {form.highlight_bg_color.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2.5">
                    {COLOR_SWATCHES.map((s) => (
                      <button
                        key={s.hex}
                        type="button"
                        onClick={() => setForm({ ...form, highlight_bg_color: s.hex })}
                        className={`w-7 h-7 rounded-full border-2 transition-all ${
                          form.highlight_bg_color.toUpperCase() === s.hex
                            ? 'scale-110 border-[#1C1917] shadow-md'
                            : 'border-stone-200 hover:scale-105'
                        }`}
                        style={{ backgroundColor: s.hex }}
                        title={s.label}
                      />
                    ))}
                    <input
                      type="color"
                      value={form.highlight_bg_color}
                      onChange={(e) => setForm({ ...form, highlight_bg_color: e.target.value })}
                      className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0 ml-1"
                      title="Pilih warna stiker kustom"
                    />
                  </div>
                </div>
              )}

              {/* 2. PENGATURAN TIPOGRAFI & WARNA DASAR */}
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-[#E7E5E4]">
                <div>
                  <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-1.5">
                    Font Subtitle
                  </label>
                  <select
                    value={form.font}
                    onChange={(e) => setForm({ ...form, font: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                  >
                    {FONT_OPTIONS.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span className="font-bold">Ukuran Font</span>
                    <span className="font-mono font-bold text-[#C2410C]">{form.font_size} px</span>
                  </div>
                  <input
                    type="range"
                    min="20"
                    max="80"
                    step="2"
                    value={form.font_size}
                    onChange={(e) => setForm({ ...form, font_size: parseInt(e.target.value) })}
                    className="w-full accent-[#C2410C] cursor-pointer mt-2"
                  />
                </div>
              </div>

              {/* Swatches Warna Kata Aktif */}
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2">
                  Warna Kata Aktif (Karaoke Highlight)
                </label>
                <div className="flex items-center space-x-2.5">
                  {COLOR_SWATCHES.map((s) => (
                    <button
                      key={s.hex}
                      type="button"
                      onClick={() => setForm({ ...form, active_color: s.hex })}
                      className={`w-8 h-8 rounded-full border-2 transition-all ${
                        form.active_color.toUpperCase() === s.hex
                          ? 'scale-110 border-[#1C1917] shadow-md'
                          : 'border-stone-200 hover:scale-105'
                      }`}
                      style={{ backgroundColor: s.hex }}
                      title={s.label}
                    />
                  ))}
                  <input
                    type="color"
                    value={form.active_color}
                    onChange={(e) => setForm({ ...form, active_color: e.target.value })}
                    className="w-9 h-9 rounded-xl cursor-pointer bg-transparent border-0 ml-1"
                    title="Pilih warna kustom"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-1.5">
                    Warna Dasar Teks
                  </label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={form.primary_color}
                      onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                      className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                    />
                    <span className="font-mono text-xs text-[#57534E] font-semibold">{form.primary_color.toUpperCase()}</span>
                  </div>
                </div>

                <label className="flex items-center justify-between p-3 bg-[#F5F5F4] rounded-xl cursor-pointer">
                  <span className="text-xs font-bold text-[#57534E]">HURUF BESAR SEMUA</span>
                  <input
                    type="checkbox"
                    checked={form.is_uppercase}
                    onChange={(e) => setForm({ ...form, is_uppercase: e.target.checked })}
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span>Ketebalan Outline</span>
                    <span className="font-mono font-bold text-[#C2410C]">{form.outline_width}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={form.outline_width}
                    onChange={(e) => setForm({ ...form, outline_width: parseInt(e.target.value) })}
                    className="w-full accent-[#C2410C] cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span>Kedalaman Shadow</span>
                    <span className="font-mono font-bold text-[#C2410C]">{form.shadow_depth}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={form.shadow_depth}
                    onChange={(e) => setForm({ ...form, shadow_depth: parseInt(e.target.value) })}
                    className="w-full accent-[#C2410C] cursor-pointer"
                  />
                </div>
              </div>

              {/* 3. EFEK VISUAL & PENEKANAN KATA (VISUAL EMPHASIS) */}
              <div className="pt-3 border-t border-[#E7E5E4] space-y-3">
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                  <Sparkles className="w-4 h-4 text-[#C2410C]" />
                  <span>Efek Penekanan Visual & Atensi</span>
                </label>

                {/* Auto-Keyword Color Shift */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-base">🎯</span>
                      <div>
                        <span className="text-xs font-bold text-[#1C1917] block">Pewarnaan Kata Kunci Otomatis (Auto-Keyword Color Shift)</span>
                        <span className="text-[11px] text-[#78716C]">Deteksi otomatis angka, nominal uang, & kata emosi tinggi dengan warna kontras</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={form.enable_keyword_color}
                      onChange={(e) => setForm({ ...form, enable_keyword_color: e.target.checked })}
                      className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                    />
                  </div>
                  {form.enable_keyword_color && (
                    <div className="flex items-center justify-between pt-2 border-t border-[#E7E5E4] mt-2">
                      <span className="text-xs text-[#57534E] font-medium">Warna Kata Kunci Khusus:</span>
                      <div className="flex items-center space-x-2">
                        <input
                          type="color"
                          value={form.keyword_color}
                          onChange={(e) => setForm({ ...form, keyword_color: e.target.value })}
                          className="w-7 h-7 rounded-lg cursor-pointer bg-transparent border-0"
                        />
                        <span className="font-mono text-xs font-semibold text-[#1C1917]">{form.keyword_color.toUpperCase()}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Dynamic Font Scaling */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🔍</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">Skala Font Dinamis (Dynamic Scaling 125%)</span>
                      <span className="text-[11px] text-[#78716C]">Membuat kata-kata kunci 25% lebih besar untuk memancing fokus mata penonton</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.enable_dynamic_scaling}
                    onChange={(e) => setForm({ ...form, enable_dynamic_scaling: e.target.checked })}
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>

                {/* Smart Emoji Injection */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🚀</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">Injeksi Emoji Pintar (Smart Emoji)</span>
                      <span className="text-[11px] text-[#78716C]">Menyematkan emoji visual secara cerdas (misal: 💰 cuan, 🔥 viral, 🚀 roket)</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.enable_emoji_injection}
                    onChange={(e) => setForm({ ...form, enable_emoji_injection: e.target.checked })}
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>

                {/* Neon Glow Outline */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">✨</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">Efek Pendaran Neon (Glow Effect)</span>
                      <span className="text-[11px] text-[#78716C]">Menambahkan pendaran neon halus pada outline teks untuk estetika futuristik</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.glow_effect}
                    onChange={(e) => setForm({ ...form, glow_effect: e.target.checked })}
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>
              </div>

              {/* 4. POSISI Y SUBTITLE MANUAL SLIDER */}
              <div className="p-4 bg-[#F5F5F4] border border-[#E7E5E4] rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-[#1C1917] uppercase tracking-wider flex items-center space-x-1.5">
                    <Sliders className="w-3.5 h-3.5 text-[#C2410C]" />
                    <span>Posisi Vertikal Subtitle (Posisi Y)</span>
                  </label>
                  <span className="font-mono text-xs font-bold text-[#C2410C]">
                    {form.margin_v} px
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => handlePositionPresetClick('bottom')}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 340
                        ? 'bg-[#C2410C] text-white border-[#C2410C]'
                        : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]'
                    }`}
                  >
                    Bawah (340px)
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePositionPresetClick('middle')}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 920
                        ? 'bg-[#C2410C] text-white border-[#C2410C]'
                        : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]'
                    }`}
                  >
                    Tengah (920px)
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePositionPresetClick('top')}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 1540
                        ? 'bg-[#C2410C] text-white border-[#C2410C]'
                        : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]'
                    }`}
                  >
                    Atas (1540px)
                  </button>
                </div>

                <div className="pt-1">
                  <input
                    type="range"
                    min="100"
                    max="1750"
                    step="10"
                    value={form.margin_v}
                    onChange={(e) => handleCustomYChange(parseInt(e.target.value))}
                    className="w-full accent-[#C2410C] cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-[#78716C] mt-1 font-mono">
                    <span>100px (Dekat Bawah)</span>
                    <span>Geser bebas naik/turun</span>
                    <span>1750px (Dekat Atas)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: AUDIO & VOICEOVER */}
          {activeTab === 'audio' && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-5 shadow-xs">
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2">
                  Mode Audio Default
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['mix', 'replace', 'original'] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setForm({ ...form, audio_mode: m })}
                      className={`py-2.5 text-xs font-bold rounded-xl border transition-all ${
                        form.audio_mode === m
                          ? 'bg-[#C2410C] text-white border-[#C2410C]'
                          : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                      }`}
                    >
                      {m === 'mix' ? 'Gabung (Mix)' : m === 'replace' ? 'Ganti (Replace)' : 'Suara Asli'}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-bold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                    <Music className="w-3.5 h-3.5 text-[#C2410C]" />
                    <span>Musik Latar Default (BGM)</span>
                  </label>
                  <span className="font-mono text-xs font-bold text-[#C2410C]">
                    {Math.round(form.bgm_volume * 100)}%
                  </span>
                </div>

                <select
                  value={form.audio_track_id ?? ''}
                  onChange={(e) => setForm({ ...form, audio_track_id: e.target.value || null })}
                  className="w-full px-3.5 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                >
                  <option value="">Tanpa BGM default</option>
                  {audioTracks.map((t) => (
                    <option key={t.id} value={t.id}>{t.title}</option>
                  ))}
                </select>

                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={Math.round(form.bgm_volume * 100)}
                  onChange={(e) => setForm({ ...form, bgm_volume: parseInt(e.target.value) / 100 })}
                  className="w-full accent-[#C2410C] cursor-pointer mt-2.5"
                />
              </div>

              <div className="p-4 bg-[#F5F5F4] border border-[#E7E5E4] rounded-2xl space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <div className="flex items-center space-x-2">
                    <Mic className="w-4 h-4 text-[#C2410C]" />
                    <span className="text-xs font-bold text-[#1C1917]">Aktifkan Voiceover AI secara default</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.use_voiceover}
                    onChange={(e) => setForm({ ...form, use_voiceover: e.target.checked })}
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </label>

                {form.use_voiceover && (
                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[#E7E5E4]">
                    <div>
                      <label className="block text-[11px] font-semibold text-[#78716C] mb-1">
                        Pilihan Suara
                      </label>
                      <select
                        value={form.narration_voice}
                        onChange={(e) => setForm({ ...form, narration_voice: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-[#D6D3D1] rounded-lg text-xs font-medium text-[#1C1917] outline-none"
                      >
                        {voices.length === 0 && <option value="id-ID-ArdiNeural">id-ID-ArdiNeural</option>}
                        {voices.map((v) => (
                          <option key={v.id} value={v.id}>{v.name} ({v.lang})</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-[#78716C] mb-1">
                        Gaya Narasi
                      </label>
                      <select
                        value={form.narration_style}
                        onChange={(e) => setForm({ ...form, narration_style: e.target.value as any })}
                        className="w-full px-3 py-2 bg-white border border-[#D6D3D1] rounded-lg text-xs font-medium text-[#1C1917] outline-none"
                      >
                        <option value="hook_story">Hook Story</option>
                        <option value="summary">Ringkasan</option>
                        <option value="educational">Edukatif</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Bottom Action Buttons */}
          <div className="flex items-center justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onBack}
              className="px-5 py-2.5 text-xs font-bold text-[#57534E] hover:bg-[#F5F5F4] rounded-xl transition-colors"
            >
              Batal
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={saving || !form.name.trim()}
              className="px-6 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#C2410C]/25 transition-all disabled:opacity-50 flex items-center space-x-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span>{isEditing && !preset?.is_builtin ? 'Simpan Perubahan' : 'Simpan Sebagai Preset'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PresetEditorPage;
