import React, { useState, useEffect } from "react";
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
  Layout,
  Layers,
  RotateCcw,
} from "lucide-react";
import { presetsApi, audioApi, ttsApi } from "../services/api";
import { SubtitleFrame } from "../components/SubtitleFrame";
import {
  TextPreset,
  TextPresetPayload,
  AudioTrack,
  VoiceItem,
  AudioMode,
  NarrationStyle,
  SubtitleMotionType,
  FramingLayout,
} from "../types";

interface PresetEditorPageProps {
  preset: TextPreset | null;
  onBack: () => void;
  onSaved: (savedPreset: TextPreset) => void;
}

interface PresetFormState extends TextPresetPayload {
  name: string;
  description: string;
  crop_mode: "smart" | "center" | "manual";
  crop_offset_x: number;
  smart_deadzone: number;
  smart_pan_seconds: number;
  framing_layout: FramingLayout;
  screen_mode: "full" | "center";
  person_shape: "circle" | "rounded" | "rectangle";
  person_scale: number;
  person_offset_x: number;
  person_offset_y: number;
  screen_offset_x: number;
  screen_offset_y: number;
  screen_scale: number;
  screen_aspect: string;
  video_filter: string;
  font: string;
  font_size: number;
  primary_color: string;
  active_color: string;
  subtitle_position: "bottom" | "middle" | "top" | "custom" | string;
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
  enable_vocal_dynamics: boolean;
  audio_track_id: string | null;
  bgm_volume: number;
  audio_mode: AudioMode;
  use_voiceover: boolean;
  narration_voice: string;
  narration_style: NarrationStyle;
}

const FONT_OPTIONS = [
  "Poppins",
  "Anton",
  "Montserrat",
  "Bebas Neue",
  "Inter",
  "Oswald",
  "Rubik",
  "Outfit",
  "Space Grotesk",
  "Syne",
  "Archivo Black",
  "Playfair Display",
  "Cinzel",
  "Permanent Marker",
  "Caveat",
  "Impact",
  "Arial",
];

const COLOR_SWATCHES = [
  { label: "Gold / Amber", hex: "#FFCC00" },
  { label: "Terracotta", hex: "#C2410C" },
  { label: "Cyan Neon", hex: "#00F0FF" },
  { label: "Emerald Neon", hex: "#10B981" },
  { label: "Sky Blue", hex: "#38BDF8" },
  { label: "Rose Pink", hex: "#F43F5E" },
  { label: "Pure White", hex: "#FFFFFF" },
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
    name: preset?.name ?? "",
    description: preset?.description ?? "",
    crop_mode: (preset?.crop_mode as any) ?? "smart",
    crop_offset_x: preset?.crop_offset_x ?? 0,
    smart_deadzone: preset?.smart_deadzone ?? 0.4,
    smart_pan_seconds: preset?.smart_pan_seconds ?? 0.4,
    framing_layout: (preset?.framing_layout as FramingLayout) || "single",
    screen_mode: (preset?.screen_mode as any) || "full",
    person_shape: (preset?.person_shape as any) || "circle",
    person_scale: preset?.person_scale ?? 0.35,
    person_offset_x: preset?.person_offset_x ?? 0,
    person_offset_y: preset?.person_offset_y ?? 0,
    screen_offset_x: preset?.screen_offset_x ?? 0,
    screen_offset_y: preset?.screen_offset_y ?? 0,
    screen_scale: preset?.screen_scale ?? 1.0,
    screen_aspect: preset?.screen_aspect || "16:9",
    video_filter: (preset as any)?.video_filter || "none",
    enable_intro_title: Boolean((preset as any)?.enable_intro_title),
    intro_title_duration: (preset as any)?.intro_title_duration ?? 1.5,
    intro_title_style: (preset as any)?.intro_title_style || "fade_slide",
    enable_outro_cta: Boolean((preset as any)?.enable_outro_cta),
    outro_cta_text: (preset as any)?.outro_cta_text || "Follow untuk lebih banyak!",
    outro_cta_duration: (preset as any)?.outro_cta_duration ?? 2.0,
    enable_lower_third: Boolean((preset as any)?.enable_lower_third),
    lower_third_text: (preset as any)?.lower_third_text || "",
    sticker_path: (preset as any)?.sticker_path || "",
    sticker_position: (preset as any)?.sticker_position || "top_right",
    sticker_scale: (preset as any)?.sticker_scale ?? 0.15,
    font: preset?.font || "Poppins",
    font_size: preset?.font_size || 44,
    primary_color: preset?.primary_color || "#FFFFFF",
    active_color: preset?.active_color || "#FFCC00",
    subtitle_position: preset?.subtitle_position || "bottom",
    margin_v:
      preset?.margin_v ??
      (DEFAULT_MARGIN_V[preset?.subtitle_position || "bottom"] || 340),
    outline_width: preset?.outline_width ?? 3,
    shadow_depth: preset?.shadow_depth ?? 2,
    is_uppercase: preset?.is_uppercase ?? true,
    motion_type: (preset?.motion_type as SubtitleMotionType) || "karaoke",
    highlight_bg_color: preset?.highlight_bg_color || "#FFCC00",
    enable_keyword_color: preset?.enable_keyword_color ?? true,
    keyword_color: preset?.keyword_color || "#10B981",
    enable_dynamic_scaling: Boolean(preset?.enable_dynamic_scaling),
    enable_emoji_injection: Boolean(preset?.enable_emoji_injection),
    glow_effect: Boolean(preset?.glow_effect),
    enable_vocal_dynamics: Boolean(preset?.enable_vocal_dynamics),
    audio_track_id: preset?.audio_track_id ?? null,
    bgm_volume: preset?.bgm_volume ?? 0.2,
    audio_mode: preset?.audio_mode || "mix",
    use_voiceover: Boolean(preset?.use_voiceover),
    narration_voice: preset?.narration_voice || "id-ID-ArdiNeural",
    narration_style: preset?.narration_style || "hook_story",
  }));

  const [activeTab, setActiveTab] = useState<
    "info" | "visual" | "text" | "audio"
  >("info");
  const [audioTracks, setAudioTracks] = useState<AudioTrack[]>([]);
  const [voices, setVoices] = useState<VoiceItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const showNotification = (type: "success" | "error", message: string) => {
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

  const handlePositionPresetClick = (pos: "bottom" | "middle" | "top") => {
    setForm((prev) => ({
      ...prev,
      subtitle_position: pos,
      margin_v: DEFAULT_MARGIN_V[pos],
    }));
  };

  const handleCustomYChange = (val: number) => {
    setForm((prev) => ({
      ...prev,
      subtitle_position: "custom",
      margin_v: val,
    }));
  };

  const handleSubmit = async () => {
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      showNotification("error", "Nama preset wajib diisi.");
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
        framing_layout: form.framing_layout,
        screen_mode: form.screen_mode,
        person_shape: form.person_shape,
        person_scale: form.person_scale,
        person_offset_x: form.person_offset_x,
        person_offset_y: form.person_offset_y,
        screen_offset_x: form.screen_offset_x,
        screen_offset_y: form.screen_offset_y,
        screen_scale: form.screen_scale,
        screen_aspect: form.screen_aspect,
        video_filter: form.video_filter || "none",
        enable_intro_title: form.enable_intro_title,
        intro_title_duration: form.intro_title_duration,
        intro_title_style: form.intro_title_style,
        enable_outro_cta: form.enable_outro_cta,
        outro_cta_text: form.outro_cta_text,
        outro_cta_duration: form.outro_cta_duration,
        enable_lower_third: form.enable_lower_third,
        lower_third_text: form.lower_third_text || null,
        sticker_path: form.sticker_path || null,
        sticker_position: form.sticker_position,
        sticker_scale: form.sticker_scale,
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
        enable_vocal_dynamics: form.enable_vocal_dynamics,
        audio_track_id: form.audio_track_id || null,
        bgm_volume: form.bgm_volume,
        audio_mode: form.audio_mode,
        use_voiceover: form.use_voiceover,
        narration_voice: form.narration_voice,
        category: (form as any).category || "text",
        narration_style: form.narration_style,
      };

      let result: TextPreset;
      if (preset && !preset.is_builtin) {
        result = await presetsApi.update(preset.id, payload);
        showNotification(
          "success",
          `Preset "${trimmedName}" berhasil diperbarui.`,
        );
      } else {
        result = await presetsApi.create(payload);
        showNotification("success", `Preset "${trimmedName}" berhasil dibuat.`);
      }

      onSaved(result);
    } catch (err: any) {
      showNotification(
        "error",
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          "Gagal menyimpan preset.",
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
              notification.type === "success"
                ? "bg-[#1C1917]/95 text-white border-emerald-500/40 ring-1 ring-emerald-500/20"
                : "bg-[#1C1917]/95 text-white border-rose-500/40 ring-1 ring-rose-500/20"
            }`}
          >
            {notification.type === "success" ? (
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
                {isEditing
                  ? `Ubah Preset: ${preset?.name}`
                  : "Buat Template Preset Baru"}
              </h2>
            </div>
            <p className="text-xs text-[#57534E] mt-0.5">
              Halaman khusus untuk mengonfigurasi framing vertikal 9:16,
              tipografi subtitle, dan audio template.
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          {preset?.is_builtin && (
            <span className="px-2 py-0.5 bg-[#E7E5E4] text-[#57534E] text-xs font-semibold rounded-md uppercase">
              Bawaan (Akan disimpan sebagai salinan baru)
            </span>
          )}
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
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>
                {isEditing && !preset?.is_builtin
                  ? "Simpan Perubahan"
                  : "Simpan Sebagai Preset"}
              </span>
            </button>
          </div>
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
              framingLayout={form.framing_layout}
              screenMode={form.screen_mode}
              personShape={form.person_shape}
              personScale={form.person_scale}
              personOffsetX={form.person_offset_x}
              personOffsetY={form.person_offset_y}
              screenOffsetX={form.screen_offset_x}
              screenOffsetY={form.screen_offset_y}
              screenScale={form.screen_scale}
              screenAspect={form.screen_aspect}
              enableVocalDynamics={form.enable_vocal_dynamics}
              videoFilter={form.video_filter}
              overlayIntro={form.enable_intro_title ? "Judul Klip…" : null}
              overlayOutro={form.enable_outro_cta ? form.outro_cta_text || "Follow untuk lebih banyak!" : null}
              overlayLowerThird={form.enable_lower_third ? form.lower_third_text || "Nama Pembicara" : null}
              className="rounded-[30px]"
            />
          </div>

          {/* Quick Summary Card */}
          <div className="mt-4 w-full bg-white p-4 rounded-2xl border border-[#E7E5E4] text-xs space-y-2 text-[#57534E] shadow-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Layout className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Tata Letak:</span>
              </span>
              <span className="font-medium text-[#1C1917]">
                {form.framing_layout === "pip_full"
                  ? "With Overlay (9:16 Penuh)"
                  : form.framing_layout === "pip_center"
                    ? "With Overlay (16:9 Tengah)"
                    : form.framing_layout === "fit_16_9_center"
                      ? "Without Overlay (16:9 Tengah)"
                      : "Without Overlay (9:16 Penuh)"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Crop className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Framing Kamera:</span>
              </span>
              <span className="font-medium text-[#1C1917]">
                {form.crop_mode === "smart"
                  ? "Smart (Ikuti Wajah)"
                  : "Center Crop"}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-semibold flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Gaya Animasi:</span>
              </span>
              <span className="font-bold text-[#C2410C] capitalize">
                {form.motion_type === "single_word_pop"
                  ? "Hormozi Pop"
                  : form.motion_type === "background_box"
                    ? "Highlighter Box"
                    : form.motion_type === "typewriter"
                      ? "Typewriter"
                      : form.motion_type === "slide_up"
                        ? "Slide Up"
                        : form.motion_type === "bounce_in"
                          ? "Bounce In"
                          : form.motion_type === "zoom_flash"
                            ? "Zoom Flash"
                            : form.motion_type === "glitch_reveal"
                              ? "Glitch Reveal"
                              : "Karaoke"}
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
              onClick={() => setActiveTab("info")}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === "info"
                  ? "bg-white text-[#C2410C] shadow-xs"
                  : "text-[#78716C] hover:text-[#1C1917]"
              }`}
            >
              <Bookmark className="w-3.5 h-3.5" />
              <span>Informasi</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("visual")}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === "visual"
                  ? "bg-white text-[#C2410C] shadow-xs"
                  : "text-[#78716C] hover:text-[#1C1917]"
              }`}
            >
              <Crop className="w-3.5 h-3.5" />
              <span>Framing Visual</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("text")}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === "text"
                  ? "bg-white text-[#C2410C] shadow-xs"
                  : "text-[#78716C] hover:text-[#1C1917]"
              }`}
            >
              <Type className="w-3.5 h-3.5" />
              <span>Tipografi & Subtitle</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("audio")}
              className={`py-2.5 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 ${
                activeTab === "audio"
                  ? "bg-white text-[#C2410C] shadow-xs"
                  : "text-[#78716C] hover:text-[#1C1917]"
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>Audio & Narasi</span>
            </button>
          </div>

          {/* TAB 1: INFORMASI UMUM */}
          {activeTab === "info" && (
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
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                  placeholder="Jelaskan karakteristik preset ini (misal: Font tebal kuning aktif, smart follow face, cocok untuk video monolog)..."
                  rows={4}
                  className="w-full px-4 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] focus:bg-white outline-none resize-none transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-1.5">
                  Kategori
                </label>
                <select
                  value={(form as any).category || "text"}
                  onChange={(e) => setForm({ ...form, category: e.target.value } as any)}
                  className="w-full px-4 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] focus:bg-white outline-none transition-all"
                >
                  <option value="text">Teks — styling subtitle saja</option>
                  <option value="full">Full — template utuh</option>
                  <option value="streamer">Streamer</option>
                  <option value="podcast">Podcast</option>
                  <option value="educational">Edukasi</option>
                  <option value="motivational">Motivasi</option>
                  <option value="gaming">Gaming</option>
                </select>
              </div>
            </div>
          )}

          {/* TAB 2: FRAMING & TATA LETAK VISUAL */}
          {activeTab === "visual" && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-6 shadow-xs">
              {/* 1. LEVEL 1: JENIS KOMPOSISI UTAMA */}
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <Layers className="w-3.5 h-3.5 text-[#C2410C]" />
                  <span>Tata Letak Komposisi (Layout)</span>
                </label>
                <div className="grid grid-cols-3 gap-2 p-1 bg-[#F5F5F4] rounded-xl">
                  {[
                    { id: "single", name: "Without Overlay", icon: "📱" },
                    { id: "pip", name: "With Overlay", icon: "🎴" },
                    { id: "streamer", name: "Streamer", icon: "🎮" },
                  ].map((cat) => {
                    const isSelected =
                      cat.id === "pip"
                        ? form.framing_layout === "pip_full" ||
                          form.framing_layout === "pip_center" ||
                          form.framing_layout === "overlay_pip"
                        : cat.id === "streamer"
                        ? form.framing_layout === "streamer_face_top" ||
                          form.framing_layout === "streamer_face_bottom"
                        : form.framing_layout === "single" ||
                          form.framing_layout === "fit_16_9_center";

                    return (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => {
                          if (cat.id === "pip") {
                            setForm({
                              ...form,
                              framing_layout:
                                form.screen_mode === "center"
                                  ? "pip_center"
                                  : "pip_full",
                            });
                          } else if (cat.id === "streamer") {
                            setForm({
                              ...form,
                              framing_layout: "streamer_face_top",
                            });
                          } else {
                            setForm({
                              ...form,
                              framing_layout:
                                form.screen_mode === "center"
                                  ? "fit_16_9_center"
                                  : "single",
                            });
                          }
                        }}
                        className={`py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                          isSelected
                            ? "bg-white text-[#C2410C] shadow-xs"
                            : "text-[#78716C] hover:text-[#1C1917]"
                        }`}
                      >
                        <span>{cat.icon}</span>
                        <span>{cat.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ========================================================
                  KATEGORI 1: WITHOUT OVERLAY
                 ======================================================== */}
              {(form.framing_layout === "single" ||
                form.framing_layout === "fit_16_9_center") && (
                <div className="space-y-5 pt-1 animate-in fade-in duration-200">
                  {/* Pilihan Format Rasio Layar */}
                  <div>
                    <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                      Format Tampilan
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setForm({
                            ...form,
                            framing_layout: "single",
                            screen_mode: "full",
                          })
                        }
                        className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                          form.framing_layout === "single"
                            ? "bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]"
                            : "bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]"
                        }`}
                      >
                        <span>📱 9:16 Penuh (Vertikal)</span>
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setForm({
                            ...form,
                            framing_layout: "fit_16_9_center",
                            screen_mode: "center",
                          })
                        }
                        className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                          form.framing_layout === "fit_16_9_center"
                            ? "bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]"
                            : "bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]"
                        }`}
                      >
                        <span>🖼️ 16:9 di Tengah (Ambient Blur)</span>
                      </button>
                    </div>
                  </div>

                  {/* Jika 9:16 Penuh: Tampilkan Mode Framing Kamera */}
                  {form.framing_layout === "single" && (
                    <div className="space-y-4 pt-2 border-t border-[#E7E5E4]">
                      <div>
                        <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                          Kamera AI & Pemotongan
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            { id: "smart", label: "👁️ Ikuti Wajah" },
                            { id: "center", label: "📐 Posisi Tengah" },
                            { id: "manual", label: "↔️ Geser Manual" },
                          ].map((mode) => (
                            <button
                              key={mode.id}
                              type="button"
                              onClick={() =>
                                setForm({ ...form, crop_mode: mode.id as any })
                              }
                              className={`py-2 rounded-xl border text-xs font-bold transition-all ${
                                form.crop_mode === mode.id
                                  ? "bg-[#C2410C] text-white border-[#C2410C]"
                                  : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]"
                              }`}
                            >
                              {mode.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Smart Deadzone Slider */}
                      {form.crop_mode === "smart" && (
                        <div className="space-y-1.5 pt-1">
                          <div className="flex justify-between items-center text-xs">
                            <span className="font-semibold text-[#57534E]">
                              Batas Gerak Kepala (Deadzone)
                            </span>
                            <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
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
                              setForm({
                                ...form,
                                smart_deadzone: parseInt(e.target.value) / 100,
                              })
                            }
                            className="w-full accent-[#C2410C] cursor-pointer"
                          />
                          <p className="text-[11px] text-[#78716C]">
                            Kepala bebas bergerak di pita tengah selebar{" "}
                            {Math.round(form.smart_deadzone * 100)}% tanpa
                            menggeser kamera.
                          </p>
                        </div>
                      )}

                      {/* Manual X Offset Slider */}
                      {form.crop_mode === "manual" && (
                        <div className="space-y-1.5 pt-1">
                          <div className="flex justify-between items-center text-xs">
                            <span className="font-semibold text-[#57534E]">
                              Geser Horizontal (X)
                            </span>
                            <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                              {form.crop_offset_x} px
                            </span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="600"
                            step="10"
                            value={form.crop_offset_x}
                            onChange={(e) =>
                              setForm({
                                ...form,
                                crop_offset_x: parseInt(e.target.value),
                              })
                            }
                            className="w-full accent-[#C2410C] cursor-pointer"
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Jika 16:9 di Tengah: Minimalist Scale Slider */}
                  {form.framing_layout === "fit_16_9_center" && (
                    <div className="space-y-4 pt-2 border-t border-[#E7E5E4]">
                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-[#57534E]">
                            Zoom Skala Layar
                          </span>
                          <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                            {Math.round(form.screen_scale * 100)}%
                          </span>
                        </div>
                        <input
                          type="range"
                          min="50"
                          max="150"
                          step="5"
                          value={Math.round(form.screen_scale * 100)}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              screen_scale: parseInt(e.target.value) / 100,
                            })
                          }
                          className="w-full accent-[#C2410C] cursor-pointer"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ========================================================
                  KATEGORI 3: STREAMER (Y-aware)
                 ======================================================== */}
              {(form.framing_layout === "streamer_face_top" ||
                form.framing_layout === "streamer_face_bottom") && (
                <div className="space-y-4 pt-1 animate-in fade-in duration-200">
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, framing_layout: "streamer_face_top" })}
                      className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all ${
                        form.framing_layout === "streamer_face_top"
                          ? "bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]"
                          : "bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]"
                      }`}
                    >
                      <span>🎮 Wajah Atas (40/60)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, framing_layout: "streamer_face_bottom" })}
                      className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all ${
                        form.framing_layout === "streamer_face_bottom"
                          ? "bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]"
                          : "bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]"
                      }`}
                    >
                      <span>🎮 Wajah Bawah (60/40)</span>
                    </button>
                  </div>
                  <p className="text-[11px] text-[#78716C]">
                    Zona wajah terdeteksi otomatis saat render. Gagal deteksi → fallback split biasa.
                  </p>
                </div>
              )}

              {/* ========================================================
                  KATEGORI 2: WITH OVERLAY
                 ======================================================== */}
              {(form.framing_layout === "pip_full" ||
                form.framing_layout === "pip_center" ||
                form.framing_layout === "overlay_pip") && (
                <div className="space-y-5 pt-1 animate-in fade-in duration-200">
                  <div className="grid grid-cols-2 gap-4">
                    {/* Mode Layar Dasar */}
                    <div>
                      <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                        Layar Dasar (Background)
                      </label>
                      <div className="grid grid-cols-2 gap-1.5">
                        <button
                          type="button"
                          onClick={() =>
                            setForm({
                              ...form,
                              screen_mode: "full",
                              framing_layout: "pip_full",
                            })
                          }
                          className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                            form.screen_mode === "full"
                              ? "bg-[#C2410C] text-white border-[#C2410C]"
                              : "bg-white text-[#57534E] border-[#D6D3D1]"
                          }`}
                        >
                          9:16 Full
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setForm({
                              ...form,
                              screen_mode: "center",
                              framing_layout: "pip_center",
                            })
                          }
                          className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                            form.screen_mode === "center"
                              ? "bg-[#C2410C] text-white border-[#C2410C]"
                              : "bg-white text-[#57534E] border-[#D6D3D1]"
                          }`}
                        >
                          16:9 Center
                        </button>
                      </div>
                    </div>

                    {/* Bentuk Facecam */}
                    <div>
                      <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                        Bentuk Facecam
                      </label>
                      <div className="grid grid-cols-3 gap-1.5">
                        {[
                          { id: "circle", label: "⭕ Lingkaran" },
                          { id: "rounded", label: "🔲 Kotak" },
                          { id: "rectangle", label: "⏹️ Persegi" },
                        ].map((s) => (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() =>
                              setForm({ ...form, person_shape: s.id as any })
                            }
                            className={`py-2 text-[11px] font-bold rounded-xl border transition-all ${
                              form.person_shape === s.id
                                ? "bg-[#C2410C] text-white border-[#C2410C]"
                                : "bg-white text-[#57534E] border-[#D6D3D1]"
                            }`}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Facecam Source Area & Position */}
                  <div className="space-y-3 pt-3 border-t border-[#E7E5E4]">
                    <div>
                      <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                        Sumber Potongan Wajah / Webcam
                      </label>
                      <div className="grid grid-cols-4 gap-1.5">
                        {[
                          {
                            id: "ai",
                            label: "👁️ AI Wajah",
                            mode: "smart",
                            x: 0,
                          },
                          {
                            id: "br",
                            label: "↘️ Kanan Bwh",
                            mode: "manual",
                            x: 1380,
                          },
                          {
                            id: "bl",
                            label: "↙️ Kiri Bwh",
                            mode: "manual",
                            x: 0,
                          },
                          {
                            id: "mid",
                            label: "📐 Tengah",
                            mode: "manual",
                            x: 690,
                          },
                        ].map((pos) => {
                          const isAct =
                            pos.id === "ai"
                              ? form.crop_mode === "smart"
                              : form.crop_mode === "manual" &&
                                (pos.id === "br"
                                  ? form.crop_offset_x >= 1100
                                  : pos.id === "bl"
                                    ? form.crop_offset_x <= 200
                                    : form.crop_offset_x > 200 &&
                                      form.crop_offset_x < 1100);

                          return (
                            <button
                              key={pos.id}
                              type="button"
                              onClick={() => {
                                setForm({
                                  ...form,
                                  crop_mode: pos.mode as any,
                                  crop_offset_x: pos.x,
                                });
                              }}
                              className={`py-2 text-[11px] font-bold rounded-xl border transition-all ${
                                isAct
                                  ? "bg-[#C2410C] text-white border-[#C2410C]"
                                  : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]"
                              }`}
                            >
                              {pos.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {form.crop_mode === "manual" && (
                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-[#57534E]">
                            Posisi Sumber Kamera (X)
                          </span>
                          <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                            {form.crop_offset_x} px
                          </span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="1380"
                          step="20"
                          value={form.crop_offset_x}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              crop_offset_x: parseInt(e.target.value),
                            })
                          }
                          className="w-full accent-[#C2410C] cursor-pointer"
                        />
                      </div>
                    )}
                  </div>

                  {/* Minimalist Facecam Controls */}
                  <div className="space-y-4 pt-3 border-t border-[#E7E5E4]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#1C1917] uppercase tracking-wider">
                        Ukuran & Posisi Tampilan Facecam
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setForm({
                            ...form,
                            person_offset_x: 0,
                            person_offset_y: 400,
                            person_scale: 0.35,
                            person_shape: "circle",
                          })
                        }
                        className="text-xs text-[#C2410C] hover:underline flex items-center space-x-1 font-semibold"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Reset Posisi</span>
                      </button>
                    </div>

                    {/* Ukuran Facecam (Scale) */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-semibold text-[#57534E]">
                          Ukuran Facecam (Skala PIP)
                        </span>
                        <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                          {Math.round(form.person_scale * 100)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="15"
                        max="75"
                        step="5"
                        value={Math.round(form.person_scale * 100)}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            person_scale: parseInt(e.target.value) / 100,
                          })
                        }
                        className="w-full accent-[#C2410C] cursor-pointer"
                      />
                    </div>

                    {/* Posisi X & Y Facecam */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-[#57534E]">
                            Geser X (Horizontal)
                          </span>
                          <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                            {form.person_offset_x} px
                          </span>
                        </div>
                        <input
                          type="range"
                          min="-450"
                          max="450"
                          step="10"
                          value={form.person_offset_x}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              person_offset_x: parseInt(e.target.value),
                            })
                          }
                          className="w-full accent-[#C2410C] cursor-pointer"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center text-xs">
                          <span className="font-semibold text-[#57534E]">
                            Geser Y (Vertikal)
                          </span>
                          <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                            {form.person_offset_y} px
                          </span>
                        </div>
                        <input
                          type="range"
                          min="-800"
                          max="800"
                          step="10"
                          value={form.person_offset_y}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              person_offset_y: parseInt(e.target.value),
                            })
                          }
                          className="w-full accent-[#C2410C] cursor-pointer"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Video Filter Pack (color grading) — semua layout */}
              <div className="space-y-2 pt-4 mt-4 border-t border-[#E7E5E4]">
                <label className="block text-xs font-bold text-[#1C1917] uppercase tracking-wider">
                  Filter Video (Color Grading)
                </label>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {[
                    { id: "none", label: "Tanpa Filter", icon: "🚫" },
                    { id: "cinematic", label: "Sinematik", icon: "🎬" },
                    { id: "vivid", label: "Vivid", icon: "🌈" },
                    { id: "warm", label: "Hangat", icon: "🌅" },
                    { id: "cool", label: "Sejuk", icon: "❄️" },
                    { id: "drama", label: "Drama", icon: "🎭" },
                    { id: "vintage", label: "Vintage", icon: "📼" },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() =>
                        setForm({ ...form, video_filter: f.id as any })
                      }
                      className={`py-2 px-2 rounded-xl border text-xs font-bold transition-all flex flex-col items-center justify-center space-y-0.5 ${
                        (form.video_filter || "none") === f.id
                          ? "bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]"
                          : "bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]"
                      }`}
                    >
                      <span className="text-base">{f.icon}</span>
                      <span>{f.label}</span>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-[#78716C]">
                  Grading ditempel setelah composite video, sebelum subtitle —
                  subtitle tak ikut berubah warna.
                </p>
              </div>

              {/* Overlay & Animasi (motion graphics di atas video) */}
              <div className="space-y-4 pt-4 mt-4 border-t border-[#E7E5E4]">
                <label className="block text-xs font-bold text-[#1C1917] uppercase tracking-wider">
                  Overlay & Animasi
                </label>

                <label className="flex items-start justify-between gap-3 p-3 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl cursor-pointer">
                  <span>
                    <span className="block text-xs font-bold text-[#1C1917]">Judul Intro (1.5 detik pertama)</span>
                    <span className="block text-[11px] text-[#78716C] mt-0.5">Judul klip muncul di atas layar dengan fade + luncur.</span>
                  </span>
                  <input type="checkbox" checked={Boolean(form.enable_intro_title)} onChange={(e) => setForm({ ...form, enable_intro_title: e.target.checked })} className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0" />
                </label>

                <label className="flex items-start justify-between gap-3 p-3 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl cursor-pointer">
                  <span>
                    <span className="block text-xs font-bold text-[#1C1917]">CTA Outro (2 detik terakhir)</span>
                    <span className="block text-[11px] text-[#78716C] mt-0.5">Ajakan mengikuti di akhir video.</span>
                  </span>
                  <input type="checkbox" checked={Boolean(form.enable_outro_cta)} onChange={(e) => setForm({ ...form, enable_outro_cta: e.target.checked })} className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0" />
                </label>
                {Boolean(form.enable_outro_cta) && (
                  <input type="text" value={form.outro_cta_text || ""} onChange={(e) => setForm({ ...form, outro_cta_text: e.target.value })} placeholder="Follow untuk lebih banyak!" className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none" />
                )}

                <label className="flex items-start justify-between gap-3 p-3 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl cursor-pointer">
                  <span>
                    <span className="block text-xs font-bold text-[#1C1917]">Lower Third (nama pembicara)</span>
                    <span className="block text-[11px] text-[#78716C] mt-0.5">Strip nama di kiri bawah sepanjang video.</span>
                  </span>
                  <input type="checkbox" checked={Boolean(form.enable_lower_third)} onChange={(e) => setForm({ ...form, enable_lower_third: e.target.checked })} className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0" />
                </label>
                {Boolean(form.enable_lower_third) && (
                  <input type="text" value={form.lower_third_text || ""} onChange={(e) => setForm({ ...form, lower_third_text: e.target.value })} placeholder="Nama pembicara / channel" className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none" />
                )}
              </div>
            </div>
          )}

          {/* TAB 3: TIPOGRAFI & SUBTITLE */}
          {activeTab === "text" && (
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
                      id: "single_word_pop",
                      name: "Hormozi Pop (1 Kata)",
                      badge: "Retensi Tertinggi",
                      desc: "Hanya menampilkan 1 kata per waktu dengan zoom bounce cepat. Sangat agresif menahan fokus penonton.",
                      icon: "🔥",
                    },
                    {
                      id: "karaoke",
                      name: "Karaoke Highlight",
                      badge: "Paling Populer",
                      desc: "3-4 kata sekaligus dalam satu baris, kata yang sedang diucapkan menyala terang secara real-time.",
                      icon: "🎤",
                    },
                    {
                      id: "background_box",
                      name: "Highlighter Sticker",
                      badge: "CapCut / Opus",
                      desc: "Kata aktif dibungkus badge stiker berlatar kontras tinggi seperti distabilo agar mencolok.",
                      icon: "🏷️",
                    },
                    {
                      id: "typewriter",
                      name: "Typewriter Reveal",
                      badge: "Storytelling",
                      desc: "Kata muncul satu per satu berurutan dan menetap sampai akhir kalimat. Cocok untuk narasi edukatif.",
                      icon: "⌨️",
                    },
                    {
                      id: "slide_up",
                      name: "Slide Up & Fade",
                      badge: "Sinematik",
                      desc: "Kalimat meluncur halus dari bawah dengan transisi fade-in elegan. Tampilan bersih dan modern.",
                      icon: "⬆️",
                    },
                    {
                      id: "bounce_in",
                      name: "Bounce In",
                      badge: "Baru",
                      desc: "Tiap baris jatuh memantul dari atas layar. Scene-entry dramatis ala CapCut.",
                      icon: "🏀",
                    },
                    {
                      id: "zoom_flash",
                      name: "Zoom Flash",
                      badge: "Baru",
                      desc: "Kata aktif meledak 200% lalu menyusut + flash warna. Penekanan maksimal.",
                      icon: "💥",
                    },
                    {
                      id: "glitch_reveal",
                      name: "Glitch Reveal",
                      badge: "Baru",
                      desc: "Efek glitch digital: shake horizontal + inversi warna sesaat. Gaya gaming/tech.",
                      icon: "👾",
                    },
                  ].map((m) => {
                    const isSelected = form.motion_type === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() =>
                          setForm({ ...form, motion_type: m.id as any })
                        }
                        className={`p-4 rounded-xl border text-left transition-all relative ${
                          isSelected
                            ? "bg-[#FFF7ED] border-[#C2410C] shadow-sm ring-1 ring-[#C2410C]"
                            : "bg-white border-[#E7E5E4] hover:bg-[#F5F5F4]"
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-xl">{m.icon}</span>
                            <span className="font-bold text-sm text-[#1C1917]">
                              {m.name}
                            </span>
                          </div>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              isSelected
                                ? "bg-[#C2410C] text-white"
                                : "bg-stone-100 text-[#78716C]"
                            }`}
                          >
                            {m.badge}
                          </span>
                        </div>
                        <p className="text-xs text-[#78716C] mt-2 leading-relaxed">
                          {m.desc}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* JIKA BACKGROUND BOX DIPILIH: PILIH WARNA BACKGROUND STIKER */}
              {form.motion_type === "background_box" && (
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
                        onClick={() =>
                          setForm({ ...form, highlight_bg_color: s.hex })
                        }
                        className={`w-7 h-7 rounded-full border-2 transition-all ${
                          form.highlight_bg_color.toUpperCase() === s.hex
                            ? "scale-110 border-[#1C1917] shadow-md"
                            : "border-stone-200 hover:scale-105"
                        }`}
                        style={{ backgroundColor: s.hex }}
                        title={s.label}
                      />
                    ))}
                    <input
                      type="color"
                      value={form.highlight_bg_color}
                      onChange={(e) =>
                        setForm({ ...form, highlight_bg_color: e.target.value })
                      }
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
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span className="font-bold">Ukuran Font</span>
                    <span className="font-mono font-bold text-[#C2410C]">
                      {form.font_size} px
                    </span>
                  </div>
                  <input
                    type="range"
                    min="20"
                    max="80"
                    step="2"
                    value={form.font_size}
                    onChange={(e) =>
                      setForm({ ...form, font_size: parseInt(e.target.value) })
                    }
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
                          ? "scale-110 border-[#1C1917] shadow-md"
                          : "border-stone-200 hover:scale-105"
                      }`}
                      style={{ backgroundColor: s.hex }}
                      title={s.label}
                    />
                  ))}
                  <input
                    type="color"
                    value={form.active_color}
                    onChange={(e) =>
                      setForm({ ...form, active_color: e.target.value })
                    }
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
                      onChange={(e) =>
                        setForm({ ...form, primary_color: e.target.value })
                      }
                      className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                    />
                    <span className="font-mono text-xs text-[#57534E] font-semibold">
                      {form.primary_color.toUpperCase()}
                    </span>
                  </div>
                </div>

                <label className="flex items-center justify-between p-3 bg-[#F5F5F4] rounded-xl cursor-pointer">
                  <span className="text-xs font-bold text-[#57534E]">
                    HURUF BESAR SEMUA
                  </span>
                  <input
                    type="checkbox"
                    checked={form.is_uppercase}
                    onChange={(e) =>
                      setForm({ ...form, is_uppercase: e.target.checked })
                    }
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span>Ketebalan Outline</span>
                    <span className="font-mono font-bold text-[#C2410C]">
                      {form.outline_width}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={form.outline_width}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        outline_width: parseInt(e.target.value),
                      })
                    }
                    className="w-full accent-[#C2410C] cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs text-[#57534E] mb-1.5">
                    <span>Kedalaman Shadow</span>
                    <span className="font-mono font-bold text-[#C2410C]">
                      {form.shadow_depth}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="8"
                    step="1"
                    value={form.shadow_depth}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        shadow_depth: parseInt(e.target.value),
                      })
                    }
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
                        <span className="text-xs font-bold text-[#1C1917] block">
                          Pewarnaan Kata Kunci Otomatis (Auto-Keyword Color
                          Shift)
                        </span>
                        <span className="text-[11px] text-[#78716C]">
                          Deteksi otomatis angka, nominal uang, & kata emosi
                          tinggi dengan warna kontras
                        </span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={form.enable_keyword_color}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          enable_keyword_color: e.target.checked,
                        })
                      }
                      className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                    />
                  </div>
                  {form.enable_keyword_color && (
                    <div className="flex items-center justify-between pt-2 border-t border-[#E7E5E4] mt-2">
                      <span className="text-xs text-[#57534E] font-medium">
                        Warna Kata Kunci Khusus:
                      </span>
                      <div className="flex items-center space-x-2">
                        <input
                          type="color"
                          value={form.keyword_color}
                          onChange={(e) =>
                            setForm({ ...form, keyword_color: e.target.value })
                          }
                          className="w-7 h-7 rounded-lg cursor-pointer bg-transparent border-0"
                        />
                        <span className="font-mono text-xs font-semibold text-[#1C1917]">
                          {form.keyword_color.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Dynamic Font Scaling */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🔍</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">
                        Skala Font Dinamis (Dynamic Scaling 125%)
                      </span>
                      <span className="text-[11px] text-[#78716C]">
                        Membuat kata-kata kunci 25% lebih besar untuk memancing
                        fokus mata penonton
                      </span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.enable_dynamic_scaling}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        enable_dynamic_scaling: e.target.checked,
                      })
                    }
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>

                {/* Smart Emoji Injection */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🚀</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">
                        Injeksi Emoji Pintar (Smart Emoji)
                      </span>
                      <span className="text-[11px] text-[#78716C]">
                        Menyematkan emoji visual secara cerdas (misal: 💰 cuan,
                        🔥 viral, 🚀 roket)
                      </span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.enable_emoji_injection}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        enable_emoji_injection: e.target.checked,
                      })
                    }
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>

                {/* Neon Glow Outline */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">✨</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">
                        Efek Pendaran Neon (Glow Effect)
                      </span>
                      <span className="text-[11px] text-[#78716C]">
                        Menambahkan pendaran neon halus pada outline teks untuk
                        estetika futuristik
                      </span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.glow_effect}
                    onChange={(e) =>
                      setForm({ ...form, glow_effect: e.target.checked })
                    }
                    className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                  />
                </div>

                {/* Auto Vocal Dynamics & Emotion Detection */}
                <div className="p-3.5 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🎙️</span>
                    <div>
                      <span className="text-xs font-bold text-[#1C1917] block">
                        Deteksi Penekanan Vokal Otomatis (Vocal Dynamics)
                      </span>
                      <span className="text-[11px] text-[#78716C]">
                        AI mendeteksi energi suara tiap kata: kata tegas
                        membesar dinamis (125%-135%) dan kata pelan mengecil
                        halus
                      </span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.enable_vocal_dynamics}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        enable_vocal_dynamics: e.target.checked,
                      })
                    }
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
                    onClick={() => handlePositionPresetClick("bottom")}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 340
                        ? "bg-[#C2410C] text-white border-[#C2410C]"
                        : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]"
                    }`}
                  >
                    Bawah (340px)
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePositionPresetClick("middle")}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 920
                        ? "bg-[#C2410C] text-white border-[#C2410C]"
                        : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]"
                    }`}
                  >
                    Tengah (920px)
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePositionPresetClick("top")}
                    className={`py-2 text-xs font-bold rounded-lg border transition-all ${
                      form.margin_v === 1540
                        ? "bg-[#C2410C] text-white border-[#C2410C]"
                        : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#E7E5E4]"
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
                    onChange={(e) =>
                      handleCustomYChange(parseInt(e.target.value))
                    }
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
          {activeTab === "audio" && (
            <div className="bg-white border border-[#E7E5E4] rounded-2xl p-6 space-y-5 shadow-xs">
              <div>
                <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2">
                  Mode Audio Default
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["mix", "replace", "original"] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setForm({ ...form, audio_mode: m })}
                      className={`py-2.5 text-xs font-bold rounded-xl border transition-all ${
                        form.audio_mode === m
                          ? "bg-[#C2410C] text-white border-[#C2410C]"
                          : "bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]"
                      }`}
                    >
                      {m === "mix"
                        ? "Gabung (Mix)"
                        : m === "replace"
                          ? "Ganti (Replace)"
                          : "Suara Asli"}
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
                  value={form.audio_track_id ?? ""}
                  onChange={(e) =>
                    setForm({ ...form, audio_track_id: e.target.value || null })
                  }
                  className="w-full px-3.5 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                >
                  <option value="">Tanpa BGM default</option>
                  {audioTracks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>

                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={Math.round(form.bgm_volume * 100)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      bgm_volume: parseInt(e.target.value) / 100,
                    })
                  }
                  className="w-full accent-[#C2410C] cursor-pointer mt-2.5"
                />
              </div>

              <div className="p-4 bg-[#F5F5F4] border border-[#E7E5E4] rounded-2xl space-y-3">
                <label className="flex items-center justify-between cursor-pointer">
                  <div className="flex items-center space-x-2">
                    <Mic className="w-4 h-4 text-[#C2410C]" />
                    <span className="text-xs font-bold text-[#1C1917]">
                      Aktifkan Voiceover AI secara default
                    </span>
                  </div>
                  <input
                    type="checkbox"
                    checked={form.use_voiceover}
                    onChange={(e) =>
                      setForm({ ...form, use_voiceover: e.target.checked })
                    }
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
                        onChange={(e) =>
                          setForm({ ...form, narration_voice: e.target.value })
                        }
                        className="w-full px-3 py-2 bg-white border border-[#D6D3D1] rounded-lg text-xs font-medium text-[#1C1917] outline-none"
                      >
                        {voices.length === 0 && (
                          <option value="id-ID-ArdiNeural">
                            id-ID-ArdiNeural
                          </option>
                        )}
                        {voices.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name} ({v.lang})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-[#78716C] mb-1">
                        Gaya Narasi
                      </label>
                      <select
                        value={form.narration_style}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            narration_style: e.target.value as any,
                          })
                        }
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
        </div>
      </div>
    </div>
  );
};

export default PresetEditorPage;
