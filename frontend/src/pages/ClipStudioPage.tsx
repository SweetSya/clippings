import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Play,
  Pause,
  Scissors,
  Sliders,
  Type,
  Palette,
  CheckCircle,
  AlertCircle,
  Loader2,
  Crop,
  Volume2,
  VolumeX,
  RotateCcw,
  Layers,
  ArrowRight,
  ArrowLeft,
  Search,
  Film,
  Clock,
  HardDrive,
  Calendar,
  CheckCircle2,
  Zap,
  ExternalLink,
  LayoutGrid,
  List,
  CheckSquare,
  Square,
  Trash2,
  X,
  Music,
  Mic,
  Save,
  Wand2,
  AudioLines,
  Bookmark,
  RefreshCw,
  Plus,
} from 'lucide-react';
import { videosApi, clipsApi, shortsApi, settingsApi, presetsApi, audioApi, ttsApi, sfxApi, SFXTrack } from '../services/api';
import { SubtitleFrame } from '../components/SubtitleFrame';
import {
  VideoItem,
  ClipItem,
  VideoStatus,
  SystemSettings,
  ReframePreview,
  TextPreset,
  AudioTrack,
  AudioMode,
  NarrationStyle,
  VoiceItem,
  SubtitleMotionType,
  FramingLayout,
  ScreenMode,
  PersonShape,
} from '../types';

const FONT_OPTIONS = [
  { value: 'Poppins', label: 'Poppins (Tebal & Modern - Rekomendasi)' },
  { value: 'Anton', label: 'Anton (Impact Shorts Tegas)' },
  { value: 'Montserrat', label: 'Montserrat (Bold & Clean)' },
  { value: 'Bebas Neue', label: 'Bebas Neue (All-Caps Punchy)' },
  { value: 'Inter', label: 'Inter (Clean Sans Modern)' },
  { value: 'Oswald', label: 'Oswald (Condensed Dynamic)' },
  { value: 'Rubik', label: 'Rubik (Rounded Heavy)' },
  { value: 'Outfit', label: 'Outfit (Modern Tech)' },
  { value: 'Space Grotesk', label: 'Space Grotesk (Futuristik)' },
  { value: 'Syne', label: 'Syne (Artistik Bold)' },
  { value: 'Archivo Black', label: 'Archivo Black (Ultra Heavy)' },
  { value: 'Playfair Display', label: 'Playfair Display (Serif Elegan)' },
  { value: 'Cinzel', label: 'Cinzel (Cinematic Epic)' },
  { value: 'Permanent Marker', label: 'Permanent Marker (Handwritten)' },
  { value: 'Caveat', label: 'Caveat (Casual Script)' },
  { value: 'Impact', label: 'Impact (Klasik Meme)' },
  { value: 'Arial', label: 'Arial (Standar Universal)' },
];

interface ClipStudioPageProps {
  selectedVideoId: string | null;
  selectedAudioTrackId?: string | null;
  onNavigateShorts: () => void;
  onNavigateSettings?: () => void;
  onNavigateAudioLibrary?: () => void;
  onNavigatePresets?: () => void;
}

export const ClipStudioPage: React.FC<ClipStudioPageProps> = ({
  selectedVideoId,
  selectedAudioTrackId,
  onNavigateShorts,
  onNavigateSettings,
  onNavigateAudioLibrary,
  onNavigatePresets,
}) => {
  // Navigation mode: 'list' (Semua Video) or 'detail' (Editor Klipping)
  const [viewMode, setViewMode] = useState<'list' | 'detail'>(
    selectedVideoId ? 'detail' : 'list'
  );

  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [activeVideoId, setActiveVideoId] = useState<string | null>(selectedVideoId);
  const [activeVideo, setActiveVideo] = useState<VideoItem | null>(null);
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [selectedClip, setSelectedClip] = useState<ClipItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderStatusMessage, setRenderStatusMessage] = useState('');

  // List view filters & search
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTab, setFilterTab] = useState<'all' | 'clipped' | 'unclipped'>('all');

  // Layout mode for catalog (grid vs list) with persistence
  const [catalogLayout, setCatalogLayout] = useState<'grid' | 'list'>('grid');

  // Multi-select & Batch states
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [batchRenderingClips, setBatchRenderingClips] = useState(false);

  // Auto generate action state
  const [autoGeneratingId, setAutoGeneratingId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Re-analyze (1.4) modal state
  const [showReanalyzeModal, setShowReanalyzeModal] = useState(false);
  const [reanalyzeMinDur, setReanalyzeMinDur] = useState(15);
  const [reanalyzeMaxDur, setReanalyzeMaxDur] = useState(60);
  const [reanalyzePrompt, setReanalyzePrompt] = useState('');
  const [reanalyzing, setReanalyzing] = useState(false);

  // Face anchor analysis (5.1) state
  const [faceAnchor, setFaceAnchor] = useState<{
    dominant_zone: string;
    recommended_layout: string;
    recommended_preset_id: string | null;
    face_coverage: number;
    warning: string | null;
  } | null>(null);
  const [analyzingFace, setAnalyzingFace] = useState(false);

  // System settings for AI connection check
  const [settings, setSettings] = useState<SystemSettings | null>(null);

  // Video preview player state
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [showGridGuide, setShowGridGuide] = useState(true);

  // Edit states for selected clip
  const [clipTitle, setClipTitle] = useState('');
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(0);

  // Render configuration
  const [cropMode, setCropMode] = useState<'center' | 'manual' | 'smart'>('center');
  const [cropOffsetX, setCropOffsetX] = useState(0);
  const [smartDeadzone, setSmartDeadzone] = useState(0.5);
  const [smartSnap, setSmartSnap] = useState(false);
  const [reframePreview, setReframePreview] = useState<ReframePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Multi-Layer Framing (Layar + Orang)
  const [framingLayout, setFramingLayout] = useState<FramingLayout>('single');
  const [screenMode, setScreenMode] = useState<ScreenMode>('full');
  const [personShape, setPersonShape] = useState<PersonShape>('circle');
  const [personScale, setPersonScale] = useState<number>(0.35);
  const [personOffsetX, setPersonOffsetX] = useState(0);
  const [personOffsetY, setPersonOffsetY] = useState(0);
  const [screenOffsetX, setScreenOffsetX] = useState(0);
  const [screenOffsetY, setScreenOffsetY] = useState(0);
  const [screenScale, setScreenScale] = useState(1.0);
  const [screenAspect, setScreenAspect] = useState<'16:9' | '9:16'>('16:9');
  const [videoFilter, setVideoFilter] = useState('none');
  const [ovIntro, setOvIntro] = useState(false);
  const [ovOutro, setOvOutro] = useState(false);
  const [ovOutroText, setOvOutroText] = useState('Follow untuk lebih banyak!');
  const [ovLower, setOvLower] = useState(false);
  const [ovLowerText, setOvLowerText] = useState('');

  const [font, setFont] = useState('Poppins');
  const [fontSize, setFontSize] = useState(44);
  const [activeColor, setActiveColor] = useState('#FFCC00'); // Gold / Amber
  const [primaryColor, setPrimaryColor] = useState('#FFFFFF');
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'middle' | 'top' | 'custom'>('bottom');
  const [marginV, setMarginV] = useState<number>(340); // Vertical Y offset in pixels
  const [outlineWidth, setOutlineWidth] = useState(2);
  const [shadowDepth, setShadowDepth] = useState(1);
  const [isUppercase, setIsUppercase] = useState(false);
  const [motionType, setMotionType] = useState<SubtitleMotionType>('karaoke');
  const [highlightBgColor, setHighlightBgColor] = useState('#FFCC00');
  const [enableKeywordColor, setEnableKeywordColor] = useState(true);
  const [keywordColor, setKeywordColor] = useState('#10B981');
  const [enableDynamicScaling, setEnableDynamicScaling] = useState(false);
  const [enableEmojiInjection, setEnableEmojiInjection] = useState(false);
  const [glowEffect, setGlowEffect] = useState(false);
  const [enableVocalDynamics, setEnableVocalDynamics] = useState(false);

  // Control panel tab & Preset mode
  const [controlTab, setControlTab] = useState<'visual' | 'audio'>('visual');
  const [presetMode, setPresetMode] = useState<'preset' | 'custom'>('preset');

  // Presets
  const [presets, setPresets] = useState<TextPreset[]>([]);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [presetCat, setPresetCat] = useState('semua');
  const [showPresetForm, setShowPresetForm] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [presetDescription, setPresetDescription] = useState('');
  const [savingPreset, setSavingPreset] = useState(false);

  // Audio
  const [audioTracks, setAudioTracks] = useState<AudioTrack[]>([]);
  const [audioTrackId, setAudioTrackId] = useState<string | null>(selectedAudioTrackId ?? null);
  const [bgmVolume, setBgmVolume] = useState(0.2);
  const [audioMode, setAudioMode] = useState<AudioMode>('mix');

  // Sound effects (3.2)
  const [sfxList, setSfxList] = useState<SFXTrack[]>([]);
  const [sfxTriggers, setSfxTriggers] = useState<{ sfx_id: string; start_t: number }[]>([]);
  const [sfxPickId, setSfxPickId] = useState('');
  const [sfxPickAt, setSfxPickAt] = useState(0.5);
  const [sfxAuto, setSfxAuto] = useState(false);
  const [sfxAutoId, setSfxAutoId] = useState('');
  const [sfxThreshold, setSfxThreshold] = useState(90);

  // Voiceover / narration
  const [voices, setVoices] = useState<VoiceItem[]>([]);
  const [narrationText, setNarrationText] = useState('');
  const [narrationVoice, setNarrationVoice] = useState('id-ID-ArdiNeural');
  const [narrationStyle, setNarrationStyle] = useState<NarrationStyle>('hook_story');
  const [narrationAudioUrl, setNarrationAudioUrl] = useState<string | null>(null);
  const [narrationDuration, setNarrationDuration] = useState<number | null>(null);
  const [useVoiceover, setUseVoiceover] = useState(false);
  const [generatingNarration, setGeneratingNarration] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  // Load videos and settings on mount
  useEffect(() => {
    fetchVideos();
    settingsApi.get().then((s) => {
      setSettings(s);
      if (s.clip_view_mode === 'grid' || s.clip_view_mode === 'list') {
        setCatalogLayout(s.clip_view_mode);
      }
    }).catch(console.error);
  }, []);

  // Load presets, audio library, and TTS voices once
  useEffect(() => {
    presetsApi.list().then(setPresets).catch((e) => console.error('Gagal memuat preset', e));
    audioApi.list().then(setAudioTracks).catch((e) => console.error('Gagal memuat pustaka audio', e));
    sfxApi.list().then(setSfxList).catch((e) => console.error('Gagal memuat SFX', e));
    ttsApi.getVoices().then(setVoices).catch((e) => console.error('Gagal memuat daftar suara', e));
  }, []);

  // Trek yang dipilih di Audio Library langsung dipakai sebagai BGM di sini
  useEffect(() => {
    if (selectedAudioTrackId) {
      setAudioTrackId(selectedAudioTrackId);
      setControlTab('audio');
    }
  }, [selectedAudioTrackId]);

  const applyPreset = (preset: TextPreset) => {
    setPresetId(preset.id);

    // 1. Visual Framing
    if (preset.crop_mode) setCropMode(preset.crop_mode as any);
    if (preset.crop_offset_x !== undefined && preset.crop_offset_x !== null) setCropOffsetX(preset.crop_offset_x);
    if (preset.smart_deadzone !== undefined && preset.smart_deadzone !== null) setSmartDeadzone(preset.smart_deadzone);
    if (preset.framing_layout) setFramingLayout(preset.framing_layout as FramingLayout);
    if (preset.screen_mode) setScreenMode(preset.screen_mode as ScreenMode);
    if (preset.person_shape) setPersonShape(preset.person_shape as PersonShape);
    if (preset.person_scale !== undefined && preset.person_scale !== null) setPersonScale(preset.person_scale);
    if (preset.person_offset_x !== undefined && preset.person_offset_x !== null) setPersonOffsetX(preset.person_offset_x);
    if (preset.person_offset_y !== undefined && preset.person_offset_y !== null) setPersonOffsetY(preset.person_offset_y);
    if (preset.screen_offset_x !== undefined && preset.screen_offset_x !== null) setScreenOffsetX(preset.screen_offset_x);
    if (preset.screen_offset_y !== undefined && preset.screen_offset_y !== null) setScreenOffsetY(preset.screen_offset_y);
    if (preset.screen_scale !== undefined && preset.screen_scale !== null) setScreenScale(preset.screen_scale);
    if (preset.screen_aspect) setScreenAspect(preset.screen_aspect as any);
    if ((preset as any).video_filter) setVideoFilter((preset as any).video_filter);
    setOvIntro(Boolean((preset as any).enable_intro_title));
    setOvOutro(Boolean((preset as any).enable_outro_cta));
    if ((preset as any).outro_cta_text) setOvOutroText((preset as any).outro_cta_text);
    setOvLower(Boolean((preset as any).enable_lower_third));
    if ((preset as any).lower_third_text) setOvLowerText((preset as any).lower_third_text);

    // 2. Text & Subtitle Styling
    setFont(preset.font || 'Poppins');
    setFontSize(preset.font_size || 44);
    setActiveColor(preset.active_color || '#FFCC00');
    setPrimaryColor(preset.primary_color || '#FFFFFF');
    setSubtitlePosition((preset.subtitle_position as any) || 'bottom');
    setMarginV(preset.margin_v ?? 340);
    setOutlineWidth(preset.outline_width ?? 3);
    setShadowDepth(preset.shadow_depth ?? 1);
    setIsUppercase(boolOr(preset.is_uppercase, false));
    if (preset.motion_type) setMotionType(preset.motion_type as SubtitleMotionType);
    if (preset.highlight_bg_color) setHighlightBgColor(preset.highlight_bg_color);
    if (preset.enable_keyword_color !== undefined && preset.enable_keyword_color !== null) setEnableKeywordColor(Boolean(preset.enable_keyword_color));
    if (preset.keyword_color) setKeywordColor(preset.keyword_color);
    if (preset.enable_dynamic_scaling !== undefined && preset.enable_dynamic_scaling !== null) setEnableDynamicScaling(Boolean(preset.enable_dynamic_scaling));
    if (preset.enable_emoji_injection !== undefined && preset.enable_emoji_injection !== null) setEnableEmojiInjection(Boolean(preset.enable_emoji_injection));
    if (preset.glow_effect !== undefined && preset.glow_effect !== null) setGlowEffect(Boolean(preset.glow_effect));
    if (preset.enable_vocal_dynamics !== undefined && preset.enable_vocal_dynamics !== null) setEnableVocalDynamics(Boolean(preset.enable_vocal_dynamics));

    // 3. Audio & Voiceover
    if (preset.audio_track_id !== undefined) setAudioTrackId(preset.audio_track_id);
    if (preset.bgm_volume !== undefined && preset.bgm_volume !== null) setBgmVolume(preset.bgm_volume);
    if (preset.audio_mode) setAudioMode(preset.audio_mode);
    setSfxAuto(Boolean((preset as any).sfx_on_hook));
    if ((preset as any).sfx_hook_sfx_id) setSfxAutoId((preset as any).sfx_hook_sfx_id);
    if ((preset as any).sfx_hook_threshold !== undefined && (preset as any).sfx_hook_threshold !== null) setSfxThreshold((preset as any).sfx_hook_threshold);
    if (preset.use_voiceover !== undefined && preset.use_voiceover !== null) setUseVoiceover(Boolean(preset.use_voiceover));
    if (preset.narration_voice) setNarrationVoice(preset.narration_voice);
    if (preset.narration_style) setNarrationStyle(preset.narration_style);

    showNotification('success', `Preset "${preset.name}" disalin ke editor! Anda bebas menyesuaikan pengaturan.`);
  };

  function boolOr(val: any, fallback: boolean): boolean {
    return val !== undefined && val !== null ? Boolean(val) : fallback;
  }

  const currentPresetPayload = (name: string, description?: string) => ({
    name,
    description: description?.trim() || undefined,
    crop_mode: cropMode,
    crop_offset_x: cropOffsetX,
    smart_deadzone: smartDeadzone,
    smart_pan_seconds: 0.5,
    framing_layout: framingLayout,
    screen_mode: screenMode,
    person_shape: personShape,
    person_scale: personScale,
    person_offset_x: personOffsetX,
    person_offset_y: personOffsetY,
    screen_offset_x: screenOffsetX,
    screen_offset_y: screenOffsetY,
    screen_scale: screenScale,
    screen_aspect: screenAspect,
    video_filter: videoFilter,
    enable_intro_title: ovIntro,
    enable_outro_cta: ovOutro,
    outro_cta_text: ovOutroText,
    enable_lower_third: ovLower,
    lower_third_text: ovLowerText || null,
    font,
    font_size: fontSize,
    primary_color: primaryColor,
    active_color: activeColor,
    subtitle_position: subtitlePosition,
    margin_v: marginV,
    outline_width: outlineWidth,
    shadow_depth: shadowDepth,
    is_uppercase: isUppercase,
    motion_type: motionType,
    highlight_bg_color: highlightBgColor,
    enable_keyword_color: enableKeywordColor,
    keyword_color: keywordColor,
    enable_dynamic_scaling: enableDynamicScaling,
    enable_emoji_injection: enableEmojiInjection,
    glow_effect: glowEffect,
    enable_vocal_dynamics: enableVocalDynamics,
    audio_track_id: audioTrackId,
    bgm_volume: bgmVolume,
    audio_mode: audioMode,
    sfx_on_hook: sfxAuto,
    sfx_hook_sfx_id: sfxAutoId || null,
    sfx_hook_threshold: sfxThreshold,
    use_voiceover: useVoiceover,
    narration_voice: narrationVoice,
    narration_style: narrationStyle,
  });

  const handleSavePreset = async () => {
    const name = presetName.trim();
    if (!name) return;

    setSavingPreset(true);
    try {
      const created = await presetsApi.create(currentPresetPayload(name, presetDescription));
      const updated = await presetsApi.list();
      setPresets(updated);
      setPresetId(created.id);
      setShowPresetForm(false);
      setPresetName('');
      setPresetDescription('');
      showNotification('success', `Preset "${created.name}" disimpan sebagai template utuh.`);
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal menyimpan preset.');
    } finally {
      setSavingPreset(false);
    }
  };

  const handleUpdatePreset = async () => {
    if (!presetId) return;
    const target = presets.find((p) => p.id === presetId);
    if (!target) return;

    setSavingPreset(true);
    try {
      const updated = await presetsApi.update(presetId, currentPresetPayload(target.name, target.description || undefined));
      setPresets((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      showNotification('success', `Preset "${updated.name}" diperbarui.`);
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal memperbarui preset.');
    } finally {
      setSavingPreset(false);
    }
  };

  const handleDeletePreset = async () => {
    if (!presetId) return;
    const target = presets.find((p) => p.id === presetId);
    if (!target) return;

    try {
      await presetsApi.remove(presetId);
      setPresets(await presetsApi.list());
      setPresetId(null);
      showNotification('success', `Preset "${target.name}" dihapus.`);
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal menghapus preset.');
    }
  };

  const handleGenerateNarration = async () => {
    if (!selectedClip) return;

    setGeneratingNarration(true);
    try {
      const result = await clipsApi.generateNarration(selectedClip.id, { style: narrationStyle });
      setNarrationText(result.narration_text);
      setNarrationDuration(result.estimated_duration_seconds);
      showNotification('success', 'Naskah narasi berhasil dibuat.');
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal membuat narasi AI.');
    } finally {
      setGeneratingNarration(false);
    }
  };

  const handleSynthesizeVoice = async () => {
    if (!selectedClip || !narrationText.trim()) return;

    setSynthesizing(true);
    try {
      const result = await clipsApi.synthesizeVoice(selectedClip.id, {
        text: narrationText.trim(),
        voice: narrationVoice,
      });
      setNarrationAudioUrl(clipsApi.getNarrationAudioUrl(selectedClip.id));
      setNarrationDuration(result.duration_seconds);
      showNotification('success', 'Audio voiceover berhasil dibuat.');
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal membuat audio voiceover.');
    } finally {
      setSynthesizing(false);
    }
  };

  const handleToggleCatalogLayout = async (layout: 'grid' | 'list') => {
    setCatalogLayout(layout);
    try {
      await settingsApi.updateUIPreferences({ clip_view_mode: layout });
    } catch (e) {
      console.error('Failed to save clip_view_mode preference', e);
    }
  };

  const toggleSelectVideo = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSelectedVideoIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAllVideos = (itemsToSelect: VideoItem[]) => {
    if (selectedVideoIds.length === itemsToSelect.length && itemsToSelect.length > 0) {
      setSelectedVideoIds([]);
    } else {
      setSelectedVideoIds(itemsToSelect.map((v) => v.id));
    }
  };

  const handleBatchAutoGenerate = async () => {
    if (selectedVideoIds.length === 0) return;
    setBatchProcessing(true);
    try {
      const res = await videosApi.batchAutoGenerate(selectedVideoIds);
      showNotification('success', res.message || `${res.success_count} video berhasil dijadwalkan untuk auto-generate shorts.`);
      setSelectedVideoIds([]);
      await fetchVideos();
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal menjalankan batch auto-generate.');
    } finally {
      setBatchProcessing(false);
    }
  };

  const handleBatchDeleteVideos = async () => {
    if (selectedVideoIds.length === 0) return;
    if (!window.confirm(`Hapus ${selectedVideoIds.length} video terpilih beserta seluruh data klip dan transkripnya?`)) return;
    setBatchProcessing(true);
    try {
      const res = await videosApi.batchDelete(selectedVideoIds);
      showNotification('success', res.message || `${res.success_count} video berhasil dihapus.`);
      setSelectedVideoIds([]);
      await fetchVideos();
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal menghapus video.');
    } finally {
      setBatchProcessing(false);
    }
  };

  const handleDeleteSingleVideo = async (videoId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Hapus video ini beserta seluruh data klip dan transkripnya?')) return;
    try {
      await videosApi.deleteVideo(videoId);
      showNotification('success', 'Video berhasil dihapus.');
      setSelectedVideoIds((prev) => prev.filter((id) => id !== videoId));
      await fetchVideos();
    } catch (err: any) {
      showNotification('error', 'Gagal menghapus video.');
    }
  };

  // Sync prop changes
  useEffect(() => {
    if (selectedVideoId) {
      setActiveVideoId(selectedVideoId);
      setViewMode('detail');
    }
  }, [selectedVideoId]);

  const fetchVideos = async () => {
    setLoadingVideos(true);
    try {
      const data = await videosApi.list(1, 100);
      setVideos(data.items);
      if (activeVideoId) {
        const found = data.items.find((v) => v.id === activeVideoId);
        if (found) setActiveVideo(found);
      }
    } catch (e) {
      console.error('Failed to fetch videos', e);
    } finally {
      setLoadingVideos(false);
    }
  };

  // When activeVideoId changes in detail view
  useEffect(() => {
    if (!activeVideoId) {
      setSelectedClip(null);
      setClips([]);
      setVideoStatus(null);
      return;
    }

    const found = videos.find((v) => v.id === activeVideoId);
    if (found) setActiveVideo(found);

    setSelectedClip(null);
    setLoading(true);

    let isSubscribed = true;
    let pollInterval: any = null;

    const loadData = async () => {
      try {
        const st = await videosApi.getStatus(activeVideoId);
        if (!isSubscribed) return;
        setVideoStatus(st);

        if (st.status === 'READY') {
          const clipList = await videosApi.getClips(activeVideoId);
          if (!isSubscribed) return;
          setClips(clipList);
        } else {
          setClips([]);
          // If video is still processing, poll until it becomes READY
          if (st.status !== 'ERROR' && st.status !== 'FAILED') {
            pollInterval = setInterval(async () => {
              if (!isSubscribed) return;
              try {
                const currentStatus = await videosApi.getStatus(activeVideoId);
                if (!isSubscribed) return;
                setVideoStatus(currentStatus);
                if (currentStatus.status === 'READY') {
                  const clipList = await videosApi.getClips(activeVideoId);
                  if (!isSubscribed) return;
                  setClips(clipList);
                  clearInterval(pollInterval);
                } else if (currentStatus.status === 'ERROR' || currentStatus.status === 'FAILED') {
                  clearInterval(pollInterval);
                }
              } catch (e) {
                console.error('Error polling status', e);
              }
            }, 3000);
          }
        }
      } catch (err) {
        console.error('Error loading clip data', err);
      } finally {
        if (isSubscribed) setLoading(false);
      }
    };

    loadData();

    return () => {
      isSubscribed = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [activeVideoId]);

  const selectClipItem = (clip: ClipItem) => {
    setSelectedClip(clip);
    setFaceAnchor(null);
    setClipTitle(clip.title);
    setStartTime(clip.start_time_seconds);
    setEndTime(clip.end_time_seconds);

    // Pulihkan naskah & voiceover yang sudah tersimpan untuk klip ini
    setNarrationText(clip.narration_text || '');
    setNarrationVoice(clip.narration_voice || 'id-ID-ArdiNeural');
    setNarrationDuration(null);
    if (clip.narration_audio_path) {
      setNarrationAudioUrl(clipsApi.getNarrationAudioUrl(clip.id));
      setUseVoiceover(true);
    } else {
      setNarrationAudioUrl(null);
      setUseVoiceover(false);
    }

    // Sync preview video
    if (videoRef.current) {
      videoRef.current.currentTime = clip.start_time_seconds;
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
    }
  };

  const handleOpenDetail = (video: VideoItem) => {
    setActiveVideoId(video.id);
    setActiveVideo(video);
    setViewMode('detail');
  };

  const handleBackToList = () => {
    setViewMode('list');
    fetchVideos();
  };

  const handleAutoGenerate = async (videoId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setAutoGeneratingId(videoId);
    try {
      const res = await videosApi.autoGenerate(videoId);
      showNotification('success', res.message || `${res.clips_queued} klip berhasil dimasukkan ke antrean render otomatis!`);
      await fetchVideos();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Gagal memulai auto-generate shorts';
      showNotification('error', msg);
    } finally {
      setAutoGeneratingId(null);
    }
  };

  const handleAnalyzeFaceAnchor = async () => {
    if (!selectedClip || analyzingFace) return;
    setAnalyzingFace(true);
    try {
      const res = await clipsApi.analyzeFaceAnchor(selectedClip.id);
      setFaceAnchor(res);
      setClips((prev) => prev.map((c) => (c.id === res.clip_id ? { ...c, face_coverage: res.face_coverage } : c)));
      const zoneLabel = res.dominant_zone === 'top' ? 'ATAS' : res.dominant_zone === 'bottom' ? 'BAWAH' : 'TENGAH';
      showNotification('success', `Wajah terdeteksi di zona ${zoneLabel} (coverage ${Math.round(res.face_coverage * 100)}%).${res.warning ? ' ' + res.warning : ''}`);
    } catch (err: any) {
      showNotification('error', err.response?.data?.detail || 'Gagal menganalisis posisi wajah.');
    } finally {
      setAnalyzingFace(false);
    }
  };

  const applyFaceRecommendation = () => {
    if (!faceAnchor) return;
    if (faceAnchor.recommended_preset_id) {
      const preset = presets.find((p) => p.id === faceAnchor.recommended_preset_id);
      if (preset) {
        applyPreset(preset);
        return;
      }
    }
    setFramingLayout(faceAnchor.recommended_layout as FramingLayout);
    showNotification('success', `Layout "${faceAnchor.recommended_layout}" diterapkan.`);
  };

  const handleReanalyze = async () => {
    if (!activeVideoId || reanalyzing) return;
    if (reanalyzeMinDur <= 0 || reanalyzeMaxDur <= 0) {
      showNotification('error', 'Durasi min/max harus lebih dari 0.');
      return;
    }
    if (reanalyzeMaxDur < reanalyzeMinDur) {
      showNotification('error', 'Durasi max harus >= min.');
      return;
    }
    setReanalyzing(true);
    try {
      await videosApi.reanalyze(activeVideoId, {
        min_dur: reanalyzeMinDur,
        max_dur: reanalyzeMaxDur,
        custom_prompt_override: reanalyzePrompt.trim() || undefined,
      });
      setShowReanalyzeModal(false);
      setSelectedClip(null);
      setClips([]);
      showNotification('success', 'Analisis ulang dimulai. Halaman akan terupdate otomatis.');
      // Refresh status → polling existing di useEffect akan menangani, tapi paksa fetch sekali
      const st = await videosApi.getStatus(activeVideoId);
      setVideoStatus(st);
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || err.message || 'Gagal memulai analisis ulang';
      showNotification('error', typeof msg === 'string' ? msg : 'Gagal memulai analisis ulang');
    } finally {
      setReanalyzing(false);
    }
  };

  // Keep playback loop strictly within clip boundary [startTime, endTime]
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const curr = videoRef.current.currentTime;
    if (curr >= endTime || curr < startTime - 0.5) {
      videoRef.current.currentTime = startTime;
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      if (videoRef.current.currentTime < startTime || videoRef.current.currentTime >= endTime) {
        videoRef.current.currentTime = startTime;
      }
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleUpdateClip = async () => {
    if (!selectedClip) return;
    try {
      const updated = await clipsApi.update(selectedClip.id, {
        title: clipTitle,
        start_time_seconds: startTime,
        end_time_seconds: endTime,
      });
      setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setSelectedClip(updated);
      showNotification('success', 'Klip berhasil diperbarui!');
    } catch (e) {
      showNotification('error', 'Gagal memperbarui klip.');
    }
  };

  const handleRender = async () => {
    if (!selectedClip) return;
    setRendering(true);
    setRenderProgress(10);
    setRenderStatusMessage('Mengirim tugas render ke antrean background...');

    try {
      const res = await clipsApi.render(selectedClip.id, {
        crop_mode: cropMode,
        crop_offset_x: cropOffsetX,
        smart_deadzone: smartDeadzone,
        smart_snap: smartSnap,
        framing_layout: framingLayout,
        screen_mode: screenMode,
        person_shape: personShape,
        person_scale: personScale,
        person_offset_x: personOffsetX,
        person_offset_y: personOffsetY,
        screen_offset_x: screenOffsetX,
        screen_offset_y: screenOffsetY,
        screen_scale: screenScale,
        screen_aspect: screenAspect,
        video_filter: videoFilter,
        enable_intro_title: ovIntro,
        enable_outro_cta: ovOutro,
        outro_cta_text: ovOutroText,
        enable_lower_third: ovLower,
        lower_third_text: ovLowerText || null,
        enable_vocal_dynamics: enableVocalDynamics,
        preset_id: presetId,
        font,
        font_size: fontSize,
        active_color: activeColor,
        primary_color: primaryColor,
        subtitle_position: subtitlePosition,
        margin_v: marginV,
        outline_width: outlineWidth,
        shadow_depth: shadowDepth,
        is_uppercase: isUppercase,
        motion_type: motionType,
        highlight_bg_color: highlightBgColor,
        enable_keyword_color: enableKeywordColor,
        keyword_color: keywordColor,
        enable_dynamic_scaling: enableDynamicScaling,
        enable_emoji_injection: enableEmojiInjection,
        glow_effect: glowEffect,
        use_voiceover: useVoiceover,
        narration_text: narrationText.trim() || null,
        narration_voice: narrationVoice,
        audio_track_id: audioTrackId,
        bgm_volume: bgmVolume,
        audio_mode: audioMode,
        sfx_triggers: sfxTriggers.map((t) => ({ sfx_id: t.sfx_id, start_t: t.start_t, volume: 0.8 })),
        sfx_on_hook: sfxAuto,
        sfx_hook_sfx_id: sfxAutoId || null,
        sfx_hook_threshold: sfxThreshold,
      });

      const shortId = res.short_id;
      setRenderStatusMessage('Menunggu worker memulai proses video 9:16...');

      const pollTimer = setInterval(async () => {
        try {
          const detail = await shortsApi.getDetail(shortId);
          if (detail.render_progress) {
            setRenderProgress(Math.max(15, detail.render_progress));
          }

          if (detail.render_status === 'RENDERING' || detail.render_status === 'PENDING') {
            setRenderStatusMessage(`FFmpeg sedang memproses crop 9:16 & membakar subtitle karaoke (${detail.render_progress || 50}%)...`);
          } else if (detail.render_status === 'COMPLETED') {
            clearInterval(pollTimer);
            setRenderProgress(100);
            setRenderStatusMessage('Video 9:16 berhasil dirender! Mengarahkan ke halaman Shorts...');
            setTimeout(() => {
              setRendering(false);
              onNavigateShorts();
            }, 800);
          } else if (detail.render_status === 'FAILED') {
            clearInterval(pollTimer);
            setRendering(false);
            showNotification('error', 'Render gagal diproses oleh sistem worker.');
          }
        } catch (e) {
          console.error('Polling render error', e);
        }
      }, 1000);
    } catch (err: any) {
      showNotification('error', 'Gagal memulai render: ' + (err.response?.data?.error?.message || err.message));
      setRendering(false);
    }
  };

  const handleBatchRenderAllClips = async () => {
    if (clips.length === 0) return;
    setBatchRenderingClips(true);
    try {
      const renderPayload = {
        crop_mode: cropMode,
        crop_offset_x: cropOffsetX,
        smart_deadzone: smartDeadzone,
        smart_pan_seconds: 0.5,
        smart_snap: smartSnap,
        framing_layout: framingLayout,
        screen_mode: screenMode,
        person_shape: personShape,
        person_scale: personScale,
        person_offset_x: personOffsetX,
        person_offset_y: personOffsetY,
        screen_offset_x: screenOffsetX,
        screen_offset_y: screenOffsetY,
        screen_scale: screenScale,
        screen_aspect: screenAspect,
        video_filter: videoFilter,
        enable_intro_title: ovIntro,
        enable_outro_cta: ovOutro,
        outro_cta_text: ovOutroText,
        enable_lower_third: ovLower,
        lower_third_text: ovLowerText || null,
        enable_vocal_dynamics: enableVocalDynamics,
        preset_id: presetId,
        font,
        font_size: fontSize,
        active_color: activeColor,
        primary_color: primaryColor,
        subtitle_position: subtitlePosition,
        margin_v: marginV,
        outline_width: outlineWidth,
        shadow_depth: shadowDepth,
        is_uppercase: isUppercase,
        motion_type: motionType,
        highlight_bg_color: highlightBgColor,
        enable_keyword_color: enableKeywordColor,
        keyword_color: keywordColor,
        enable_dynamic_scaling: enableDynamicScaling,
        enable_emoji_injection: enableEmojiInjection,
        glow_effect: glowEffect,
        use_voiceover: useVoiceover,
        narration_voice: narrationVoice,
        audio_track_id: audioTrackId,
        bgm_volume: bgmVolume,
        audio_mode: audioMode,
        sfx_triggers: sfxTriggers.map((t) => ({ sfx_id: t.sfx_id, start_t: t.start_t, volume: 0.8 })),
        sfx_on_hook: sfxAuto,
        sfx_hook_sfx_id: sfxAutoId || null,
        sfx_hook_threshold: sfxThreshold,
      };

      const res = await clipsApi.batchRender(clips.map((c) => c.id), renderPayload);
      showNotification('success', `Berhasil! ${res.success_count} kandidat klip telah dimasukkan ke antrean render background.`);
    } catch (err: any) {
      showNotification('error', 'Gagal mengantrekan render batch: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setBatchRenderingClips(false);
    }
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '0:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const colorPresets = [
    { label: 'Gold / Amber', hex: '#FFCC00' },
    { label: 'Terracotta', hex: '#C2410C' },
    { label: 'Emerald Neon', hex: '#10B981' },
    { label: 'Sky Cyan', hex: '#0EA5E9' },
    { label: 'Rose Pink', hex: '#F43F5E' },
  ];

  const objectPositionX = cropMode === 'manual' ? `${Math.max(10, Math.min(90, 50 + (cropOffsetX - 150) / 10))}%` : '50%';

  // Smart reframe: ambil timeline lintasan kepala untuk klip terpilih (di-debounce saat slider digeser)
  useEffect(() => {
    if (cropMode !== 'smart' || !selectedClip) {
      setReframePreview(null);
      setLoadingPreview(false);
      return;
    }

    let cancelled = false;
    setLoadingPreview(true);

    const timer = setTimeout(() => {
      clipsApi.getReframePreview(selectedClip.id, smartDeadzone, smartSnap)
        .then((data) => {
          if (!cancelled) setReframePreview(data);
        })
        .catch(() => {
          if (!cancelled) setReframePreview(null);
        })
        .finally(() => {
          if (!cancelled) setLoadingPreview(false);
        });
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [cropMode, selectedClip?.id, smartDeadzone, smartSnap]);

  // Simulator: geser crop secara imperatif agar animasi pan tidak memicu re-render setiap frame
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    const preview = reframePreview;
    if (cropMode !== 'smart' || !preview || preview.keyframes.length === 0) {
      el.style.objectPosition = `${objectPositionX} 50%`;
      return;
    }

    const { keyframes } = preview;
    const maxOffset = Math.max(1, preview.max_offset_x);

    const offsetAt = (localTime: number) => {
      if (localTime <= keyframes[0].t) return keyframes[0].x;
      for (let i = 1; i < keyframes.length; i += 1) {
        if (localTime < keyframes[i].t) {
          const span = keyframes[i].t - keyframes[i - 1].t;
          if (span <= 0) return keyframes[i].x;
          const ratio = (localTime - keyframes[i - 1].t) / span;
          return keyframes[i - 1].x + (keyframes[i].x - keyframes[i - 1].x) * ratio;
        }
      }
      return keyframes[keyframes.length - 1].x;
    };

    let animationFrame = 0;
    let lastValue = '';

    const tick = () => {
      const percentage = (offsetAt(el.currentTime - startTime) / maxOffset) * 100;
      const value = `${percentage.toFixed(2)}% 50%`;
      if (value !== lastValue) {
        el.style.objectPosition = value;
        lastValue = value;
      }
      animationFrame = requestAnimationFrame(tick);
    };
    tick();

    return () => cancelAnimationFrame(animationFrame);
  }, [cropMode, objectPositionX, reframePreview, startTime]);

  const cameraMoves = reframePreview
    ? reframePreview.keyframes.filter((k, i, arr) => i > 0 && k.x !== arr[i - 1].x).length
    : 0;

  const selectedAudioTrack = audioTracks.find((t) => t.id === audioTrackId) || null;

  // Preset boleh menimpa MarginV; bila tidak, pratinjau memakai bawaan per posisi.
  const activeMarginV = presets.find((p) => p.id === presetId)?.margin_v ?? null;

  // Filter videos for list view
  const filteredVideos = videos.filter((v) => {
    const matchesSearch = v.original_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (v.description && v.description.toLowerCase().includes(searchQuery.toLowerCase()));

    const isClipped = (v.clips_count || 0) > 0 || (v.rendered_count || 0) > 0;

    if (!matchesSearch) return false;
    if (filterTab === 'clipped') return isClipped;
    if (filterTab === 'unclipped') return !isClipped;
    return true;
  });

  const clippedCount = videos.filter((v) => (v.clips_count || 0) > 0 || (v.rendered_count || 0) > 0).length;
  const unclippedCount = videos.length - clippedCount;

  return (
    <div className="space-y-6">
      {/* Toast Notification (Floating Top Overlay - No Layout Shift) */}
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

      {/* Modal Analisis Ulang (1.4) */}
      {showReanalyzeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !reanalyzing && setShowReanalyzeModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg text-[#1C1917] flex items-center gap-2">
                <RefreshCw className="w-5 h-5 text-[#C2410C]" />
                Analisis Ulang Klip
              </h3>
              <button type="button" onClick={() => !reanalyzing && setShowReanalyzeModal(false)} className="p-1 rounded-lg hover:bg-[#F5F5F4] text-[#78716C]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-[#78716C]">
              Kandidat lama akan dihapus dan diganti hasil baru. Transkrip dipakai ulang, tanpa upload ulang.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Min durasi (s)</label>
                <input type="number" min={1} value={reanalyzeMinDur} onChange={(e) => setReanalyzeMinDur(parseFloat(e.target.value) || 0)} className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-mono focus:border-[#C2410C] outline-none" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Max durasi (s)</label>
                <input type="number" min={1} value={reanalyzeMaxDur} onChange={(e) => setReanalyzeMaxDur(parseFloat(e.target.value) || 0)} className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-mono focus:border-[#C2410C] outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Prompt kustom (opsional)</label>
              <textarea value={reanalyzePrompt} onChange={(e) => setReanalyzePrompt(e.target.value)} rows={3} placeholder="Contoh: fokus ke momen lucu & kontroversial..." className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm focus:border-[#C2410C] outline-none resize-none" />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" disabled={reanalyzing} onClick={() => setShowReanalyzeModal(false)} className="px-4 py-2 text-sm font-semibold text-[#57534E] bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-xl disabled:opacity-50">
                Batal
              </button>
              <button type="button" disabled={reanalyzing} onClick={handleReanalyze} className="px-4 py-2 text-sm font-bold text-white bg-[#C2410C] hover:bg-[#9A3412] rounded-xl disabled:opacity-50 flex items-center gap-2">
                {reanalyzing && <Loader2 className="w-4 h-4 animate-spin" />}
                {reanalyzing ? 'Memulai...' : 'Mulai Analisis'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          VIEW 1: SEMUA VIDEO (LIST VIEW)
          ========================================================================= */}
      {viewMode === 'list' && (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="font-display font-bold text-3xl text-[#1C1917]">Semua Video Sumber</h2>
              <p className="text-[#57534E] text-sm mt-1">
                Katalog seluruh video yang telah diunggah. Pilih video untuk membuka detail klipping atau gunakan Auto-Generate.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              {/* Layout Mode Toggle (Grid vs List) */}
              <div className="flex bg-[#F5F5F4] p-1 rounded-xl border border-[#D6D3D1]">
                <button
                  type="button"
                  onClick={() => handleToggleCatalogLayout('grid')}
                  className={`p-1.5 rounded-lg transition-all ${
                    catalogLayout === 'grid'
                      ? 'bg-white text-[#C2410C] shadow-xs'
                      : 'text-[#78716C] hover:text-[#1C1917]'
                  }`}
                  title="Tampilan Grid"
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleCatalogLayout('list')}
                  className={`p-1.5 rounded-lg transition-all ${
                    catalogLayout === 'list'
                      ? 'bg-white text-[#C2410C] shadow-xs'
                      : 'text-[#78716C] hover:text-[#1C1917]'
                  }`}
                  title="Tampilan List"
                >
                  <List className="w-4 h-4" />
                </button>
              </div>

              {settings && !settings.llm_connected && (
                <div className="flex items-center space-x-2 bg-amber-50 border border-amber-200 px-3 py-2 rounded-xl text-xs text-amber-800">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>AI belum terhubung.</span>
                  {onNavigateSettings && (
                    <button
                      onClick={onNavigateSettings}
                      className="font-bold underline hover:text-[#C2410C]"
                    >
                      Uji Koneksi
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Search Bar & Filter Tabs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#E7E5E4]">
            {/* Filter Tabs */}
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => setFilterTab('all')}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  filterTab === 'all'
                    ? 'bg-[#C2410C] text-white shadow-xs'
                    : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
                }`}
              >
                Semua Video ({videos.length})
              </button>

              <button
                type="button"
                onClick={() => setFilterTab('clipped')}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                  filterTab === 'clipped'
                    ? 'bg-[#C2410C] text-white shadow-xs'
                    : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Sudah Diklip ({clippedCount})</span>
              </button>

              <button
                type="button"
                onClick={() => setFilterTab('unclipped')}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                  filterTab === 'unclipped'
                    ? 'bg-[#C2410C] text-white shadow-xs'
                    : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-[#A8A29E]" />
                <span>Belum Diklip ({unclippedCount})</span>
              </button>
            </div>

            {/* Search Input & Select All */}
            <div className="flex items-center space-x-2">
              {filteredVideos.length > 0 && (
                <button
                  type="button"
                  onClick={() => toggleSelectAllVideos(filteredVideos)}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#57534E] text-xs font-semibold rounded-xl transition-all whitespace-nowrap"
                >
                  {selectedVideoIds.length === filteredVideos.length && filteredVideos.length > 0 ? (
                    <>
                      <CheckSquare className="w-3.5 h-3.5 text-[#C2410C]" />
                      <span>Batal Pilih</span>
                    </>
                  ) : (
                    <>
                      <Square className="w-3.5 h-3.5" />
                      <span>Pilih Semua</span>
                    </>
                  )}
                </button>
              )}

              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 text-[#A8A29E] absolute left-3 top-2.5 pointer-events-none" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari judul video..."
                  className="w-full pl-9 pr-3 py-1.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none"
                />
              </div>
            </div>
          </div>

          {/* Videos Content */}
          {loadingVideos ? (
            <div className="py-16 text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-[#C2410C] mx-auto" />
              <p className="text-xs text-[#78716C]">Memuat daftar video...</p>
            </div>
          ) : filteredVideos.length === 0 ? (
            <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-12 text-center space-y-3">
              <Film className="w-10 h-10 text-[#A8A29E] mx-auto" />
              <h3 className="font-semibold text-base text-[#1C1917]">Tidak Ada Video Ditemukan</h3>
              <p className="text-xs text-[#78716C] max-w-sm mx-auto">
                {searchQuery
                  ? `Tidak ada video yang cocok dengan kata kunci "${searchQuery}".`
                  : 'Belum ada video di kategori ini. Silakan unggah video baru di tab Tambah Video.'}
              </p>
            </div>
          ) : catalogLayout === 'grid' ? (
            /* =========================================================================
               GRID CATALOG VIEW
               ========================================================================= */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredVideos.map((video) => {
                const isClipped = (video.clips_count || 0) > 0;
                const isGenerating = autoGeneratingId === video.id;
                const isSelected = selectedVideoIds.includes(video.id);

                return (
                  <div
                    key={video.id}
                    onClick={() => handleOpenDetail(video)}
                    className={`bg-white border rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between group relative ${
                      isSelected ? 'border-[#C2410C] ring-2 ring-[#C2410C]/20' : 'border-[#D6D3D1] hover:border-[#C2410C]'
                    }`}
                  >
                    <div>
                      {/* Thumbnail with Overlay Badges */}
                      <div className="relative aspect-video bg-black/90 overflow-hidden">
                        {video.thumbnail_url ? (
                          <img
                            src={videosApi.getThumbnailUrl(video.id)}
                            alt={video.original_name}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-[#78716C]">
                            <Film className="w-10 h-10 opacity-40" />
                          </div>
                        )}

                        {/* Multi-Select Checkbox overlay */}
                        <div
                          onClick={(e) => toggleSelectVideo(video.id, e)}
                          className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 backdrop-blur-xs text-white cursor-pointer z-10 transition-transform active:scale-95"
                          title={isSelected ? 'Batalkan pilihan' : 'Pilih video'}
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-[#C2410C] fill-[#C2410C] bg-white rounded-xs" />
                          ) : (
                            <Square className="w-4 h-4 text-white/80" />
                          )}
                        </div>

                        {/* Duration Badge */}
                        <div className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/70 backdrop-blur-xs text-white text-[11px] font-mono font-semibold rounded-md flex items-center space-x-1">
                          <Clock className="w-3 h-3 text-white/70" />
                          <span>{formatDuration(video.duration_seconds)}</span>
                        </div>

                        {/* Top Clipping Status Badge */}
                        <div className="absolute top-2 left-2">
                          {isClipped ? (
                            <span className="px-2.5 py-1 bg-emerald-600/90 text-white backdrop-blur-xs text-[11px] font-bold rounded-lg shadow-sm flex items-center space-x-1">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Sudah Diklip ({video.clips_count})</span>
                            </span>
                          ) : video.status === 'READY' ? (
                            <span className="px-2.5 py-1 bg-[#1C1917]/80 text-white/90 backdrop-blur-xs text-[11px] font-medium rounded-lg shadow-sm">
                              Belum Diklip
                            </span>
                          ) : video.status === 'FAILED' ? (
                            <span className="px-2.5 py-1 bg-red-600/90 text-white backdrop-blur-xs text-[11px] font-bold rounded-lg shadow-sm">
                              Gagal
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 bg-amber-500/90 text-white backdrop-blur-xs text-[11px] font-bold rounded-lg shadow-sm flex items-center space-x-1">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              <span>{video.status}</span>
                            </span>
                          )}
                        </div>

                        {/* Auto Generate Badge if enabled */}
                        {video.auto_generate_shorts && (
                          <div className="absolute bottom-2 left-2">
                            <span className="px-2 py-0.5 bg-[#C2410C]/90 text-white backdrop-blur-xs text-[10px] font-bold rounded-md flex items-center space-x-1 shadow-sm">
                              <Zap className="w-2.5 h-2.5" />
                              <span>Auto-Gen</span>
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Content Area */}
                      <div className="p-4 space-y-2">
                        <h4 className="font-semibold text-sm text-[#1C1917] line-clamp-2 leading-snug group-hover:text-[#C2410C] transition-colors">
                          {video.original_name}
                        </h4>

                        {video.description && (
                          <p className="text-xs text-[#78716C] line-clamp-2 italic">
                            {video.description}
                          </p>
                        )}

                        <div className="flex items-center justify-between text-[11px] text-[#78716C] font-mono pt-2 border-t border-[#F5F5F4]">
                          <span className="flex items-center space-x-1">
                            <HardDrive className="w-3 h-3" />
                            <span>{(video.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                          </span>
                          <span className="flex items-center space-x-1">
                            <Calendar className="w-3 h-3" />
                            <span>{new Date(video.created_at).toLocaleDateString()}</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Card Actions */}
                    <div className="p-4 pt-0 flex gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(video);
                        }}
                        className="flex-1 py-2 px-3 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5"
                      >
                        <span>Buka Editor Klip</span>
                        <ArrowRight className="w-3.5 h-3.5 text-[#C2410C]" />
                      </button>

                      {video.status === 'READY' && (
                        <button
                          type="button"
                          onClick={(e) => handleAutoGenerate(video.id, e)}
                          disabled={isGenerating}
                          title="Otomatis render semua klip menjadi video shorts vertikal"
                          className="py-2 px-3 bg-[#C2410C]/10 hover:bg-[#C2410C] text-[#C2410C] hover:text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1 shrink-0"
                        >
                          {isGenerating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Zap className="w-3.5 h-3.5" />
                          )}
                          <span className="hidden sm:inline">Auto-Gen</span>
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={(e) => handleDeleteSingleVideo(video.id, e)}
                        className="p-2 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-xl transition-colors shrink-0"
                        title="Hapus Video"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* =========================================================================
               LIST CATALOG VIEW
               ========================================================================= */
            <div className="space-y-3">
              {filteredVideos.map((video) => {
                const isClipped = (video.clips_count || 0) > 0;
                const isGenerating = autoGeneratingId === video.id;
                const isSelected = selectedVideoIds.includes(video.id);

                return (
                  <div
                    key={video.id}
                    onClick={() => handleOpenDetail(video)}
                    className={`bg-white border rounded-2xl p-3 shadow-xs hover:shadow-md transition-all flex items-center justify-between gap-4 cursor-pointer group ${
                      isSelected ? 'border-[#C2410C] ring-2 ring-[#C2410C]/20' : 'border-[#D6D3D1] hover:border-[#C2410C]'
                    }`}
                  >
                    {/* Left: Checkbox + Thumbnail + Info */}
                    <div className="flex items-center space-x-3.5 min-w-0">
                      <div
                        onClick={(e) => toggleSelectVideo(video.id, e)}
                        className="p-1 cursor-pointer text-[#78716C] hover:text-[#C2410C]"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-5 h-5 text-[#C2410C]" />
                        ) : (
                          <Square className="w-5 h-5" />
                        )}
                      </div>

                      {/* Video Thumbnail */}
                      <div className="relative w-28 h-18 aspect-video bg-black/90 rounded-xl overflow-hidden shrink-0 shadow-xs">
                        {video.thumbnail_url ? (
                          <img
                            src={videosApi.getThumbnailUrl(video.id)}
                            alt={video.original_name}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-[#78716C]">
                            <Film className="w-6 h-6 opacity-40" />
                          </div>
                        )}
                        <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/70 text-white text-[10px] font-mono rounded">
                          {formatDuration(video.duration_seconds)}
                        </div>
                      </div>

                      {/* Title & Metadata */}
                      <div className="space-y-1 min-w-0">
                        <h4 className="font-semibold text-sm text-[#1C1917] truncate group-hover:text-[#C2410C] transition-colors">
                          {video.original_name}
                        </h4>
                        <div className="flex flex-wrap items-center gap-2.5 text-xs text-[#78716C]">
                          <span className="flex items-center space-x-1">
                            <HardDrive className="w-3 h-3" />
                            <span>{(video.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                          </span>
                          <span>•</span>
                          <span className="flex items-center space-x-1">
                            <Calendar className="w-3 h-3" />
                            <span>{new Date(video.created_at).toLocaleDateString()}</span>
                          </span>
                          <span>•</span>
                          {isClipped ? (
                            <span className="text-emerald-700 font-semibold flex items-center space-x-1">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>{video.clips_count} Klip</span>
                            </span>
                          ) : (
                            <span className="text-[#A8A29E]">Belum diklip</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center space-x-2 shrink-0">
                      {video.status === 'READY' && (
                        <button
                          type="button"
                          onClick={(e) => handleAutoGenerate(video.id, e)}
                          disabled={isGenerating}
                          className="py-1.5 px-3 bg-[#C2410C]/10 hover:bg-[#C2410C] text-[#C2410C] hover:text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1"
                          title="Auto-Generate Shorts"
                        >
                          {isGenerating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Zap className="w-3.5 h-3.5" />
                          )}
                          <span className="hidden sm:inline">Auto-Gen</span>
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(video);
                        }}
                        className="py-1.5 px-3 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center space-x-1"
                      >
                        <span>Buka Klip</span>
                        <ArrowRight className="w-3.5 h-3.5 text-[#C2410C]" />
                      </button>

                      <button
                        type="button"
                        onClick={(e) => handleDeleteSingleVideo(video.id, e)}
                        className="p-1.5 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
                        title="Hapus Video"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Floating Action Bar for Selected Videos */}
          {selectedVideoIds.length > 0 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-[#1C1917] text-white px-5 py-3 rounded-2xl shadow-2xl border border-stone-700 flex items-center space-x-4 animate-in fade-in slide-in-from-bottom-4 duration-200">
              <span className="text-xs font-semibold whitespace-nowrap">
                {selectedVideoIds.length} video dipilih
              </span>

              <div className="h-4 w-px bg-white/20" />

              <button
                type="button"
                onClick={handleBatchAutoGenerate}
                disabled={batchProcessing}
                className="px-3.5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {batchProcessing ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Zap className="w-3.5 h-3.5" />
                )}
                <span>⚡ Auto-Generate Shorts</span>
              </button>

              <button
                type="button"
                onClick={handleBatchDeleteVideos}
                disabled={batchProcessing}
                className="px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Hapus Terpilih</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedVideoIds([])}
                className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
                title="Batalkan Pilihan"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          VIEW 2: DETAIL KLIPPING (EDITOR WORKSPACE)
          ========================================================================= */}
      {viewMode === 'detail' && (
        <div className="space-y-6">
          {/* Top Bar with Back Button & Breadcrumb */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E7E5E4]">
            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={handleBackToList}
                className="p-2 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#1C1917] rounded-xl transition-all flex items-center space-x-1 text-xs font-semibold"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="hidden sm:inline">Semua Video</span>
              </button>

              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-[#78716C] font-mono">Editor Klip /</span>
                  <h3 className="font-bold text-lg text-[#1C1917] truncate max-w-[300px] sm:max-w-md">
                    {activeVideo?.original_name || 'Detail Video'}
                  </h3>
                </div>
                <div className="flex items-center space-x-3 text-xs text-[#78716C] mt-0.5">
                  <span>Durasi: {formatDuration(activeVideo?.duration_seconds || 0)}</span>
                  <span>•</span>
                  <span>{clips.length} Kandidat Klip</span>
                  {activeVideo?.auto_generate_shorts && (
                    <>
                      <span>•</span>
                      <span className="text-[#C2410C] font-bold">⚡ Auto-Generate Aktif</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Header Action Buttons */}
            <div className="flex items-center space-x-2">
              {activeVideoId && (
                <button
                  type="button"
                  onClick={(e) => handleAutoGenerate(activeVideoId, e)}
                  disabled={autoGeneratingId === activeVideoId || clips.length === 0}
                  className="px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all shadow-sm flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {autoGeneratingId === activeVideoId ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Zap className="w-3.5 h-3.5" />
                  )}
                  <span>Render Semua Klip ({clips.length})</span>
                </button>
              )}

              <button
                type="button"
                onClick={onNavigateShorts}
                className="px-4 py-2 bg-white hover:bg-[#F5F5F4] border border-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center space-x-1"
              >
                <span>Lihat Shorts Jadi</span>
                <ArrowRight className="w-3.5 h-3.5 text-[#C2410C]" />
              </button>
            </div>
          </div>

          {/* AI Unconnected Warning Banner */}
          {settings && !settings.llm_connected && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between text-xs text-amber-800">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>AI Belum Terhubung:</strong> Pengambilan highlight dengan Konteks Besar (transkrip penuh) & Konteks Kecil membutuhkan AI aktif.
                </span>
              </div>
              {onNavigateSettings && (
                <button
                  onClick={onNavigateSettings}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-semibold transition-all shrink-0 ml-3"
                >
                  Uji Koneksi AI Sekarang
                </button>
              )}
            </div>
          )}

          {/* Processing Banner if video not ready */}
          {videoStatus && videoStatus.status !== 'READY' && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-[#C2410C] mx-auto" />
              <h3 className="font-semibold text-lg text-[#1C1917]">
                Video Sedang Diproses: {videoStatus.status}
              </h3>
              <p className="text-sm text-[#57534E] max-w-md mx-auto">
                Whisper lokal sedang mentranskripsi kata-per-kata dan AI sedang mencari kandidat klip terbaik. Halaman akan otomatis terupdate saat selesai.
              </p>
            </div>
          )}

          {/* Studio Workspace if Ready */}
          {videoStatus?.status === 'READY' && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Column Left: Clip Candidates List (4 cols) */}
              <div className="lg:col-span-4 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold text-base text-[#1C1917] flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-[#C2410C]" />
                    <span>Kandidat Klip AI ({clips.length})</span>
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowReanalyzeModal(true)}
                      className="px-3 py-1.5 bg-white hover:bg-[#F5F5F4] text-[#57534E] border border-[#D6D3D1] text-xs font-bold rounded-lg transition-all flex items-center space-x-1.5 shadow-xs"
                      title="Minta ulang analisis AI dengan durasi/prompt berbeda"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Analisis Ulang</span>
                    </button>
                  {clips.length > 0 && (
                    <button
                      type="button"
                      onClick={handleBatchRenderAllClips}
                      disabled={batchRenderingClips}
                      className="px-3 py-1.5 bg-[#FFF7ED] hover:bg-[#FFEDD5] text-[#C2410C] border border-[#FDBA74] text-xs font-bold rounded-lg transition-all flex items-center space-x-1.5 disabled:opacity-50 shadow-xs"
                      title="Render semua kandidat klip ke antrean background"
                    >
                      {batchRenderingClips ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Mengantrekan...</span>
                        </>
                      ) : (
                        <>
                          <Layers className="w-3.5 h-3.5" />
                          <span>Render Semua ({clips.length})</span>
                        </>
                      )}
                      </button>
                    )}
                  </div>
                </div>

                {clips.length === 0 ? (
                  <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-8 text-center space-y-3">
                    <p className="text-xs text-[#78716C]">
                      Belum ada kandidat klip yang dihasilkan untuk video ini.
                    </p>
                    {activeVideoId && (
                      <button
                        onClick={() => videosApi.process(activeVideoId)}
                        className="px-4 py-2 bg-[#C2410C] text-white text-xs font-semibold rounded-xl"
                      >
                        Jalankan Analisis AI Sekarang
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {clips.map((clip) => {
                      const isSelected = selectedClip?.id === clip.id;
                      return (
                        <div
                          key={clip.id}
                          onClick={() => selectClipItem(clip)}
                          className={`p-4 rounded-xl border cursor-pointer transition-all duration-150 ${
                            isSelected
                              ? 'bg-white border-[#C2410C] shadow-md border-l-4'
                              : 'bg-white/80 border-[#D6D3D1] hover:border-[#78716C] hover:bg-white'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                              <span className="px-2 py-0.5 bg-[#C2410C]/10 text-[#C2410C] text-xs font-semibold rounded-md font-mono" title={`LLM ${clip.hook_score} • rate ${(clip.speech_rate ?? 0).toFixed(2)} k/dtk • keyword ${((clip.keyword_density ?? 0) * 100).toFixed(1)}%`}>
                                Skor: {(clip.composite_score ?? 0) > 0 ? clip.composite_score : clip.hook_score}/100
                              </span>
                            <span className="text-xs text-[#78716C] font-mono">
                              {clip.duration_seconds.toFixed(1)}s
                            </span>
                          </div>

                          <h4 className="font-semibold text-sm text-[#1C1917] leading-snug">
                            {clip.title}
                          </h4>

                          {clip.virality_reason && (
                            <p className="text-xs text-[#57534E] mt-2 line-clamp-2 italic bg-[#F5F5F4] p-2 rounded-lg border border-[#E7E5E4]">
                              "{clip.virality_reason}"
                            </p>
                          )}

                          <div className="flex items-center justify-between text-[11px] text-[#78716C] font-mono mt-3 pt-2 border-t border-[#F5F5F4]">
                            <span>Mulai: {clip.start_time_seconds}s</span>
                            <span>Selesai: {clip.end_time_seconds}s</span>
                          </div>

                          {(() => {
                            const cov = clip.face_coverage ?? 0;
                            const badge =
                              cov <= 0
                                ? { cls: 'bg-[#F5F5F4] text-[#A8A29E] border-[#E7E5E4]', icon: '⚪', label: 'Wajah: belum dianalisis' }
                                : cov >= 0.7
                                ? { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: '🟢', label: `Wajah ${Math.round(cov * 100)}% • crop optimal` }
                                : cov >= 0.3
                                ? { cls: 'bg-amber-50 text-amber-700 border-amber-200', icon: '🟡', label: `Wajah ${Math.round(cov * 100)}% • parsial` }
                                : { cls: 'bg-red-50 text-red-600 border-red-200', icon: '🔴', label: `Wajah ${Math.round(cov * 100)}% • center crop` };
                            return (
                              <div className="mt-2">
                                <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${badge.cls}`}>
                                  {badge.icon} {badge.label}
                                </span>
                              </div>
                            );
                          })()}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Column Center & Right: Preview Simulator & Customization (8 cols) */}
              <div className="lg:col-span-8 space-y-6">
                {selectedClip ? (
                  <div className="bg-white border border-[#D6D3D1] rounded-2xl ps-6 py-6 pe-2 shadow-sm space-y-6">
                    {/* Clip Title & Timing Bar */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pb-4 border-b border-[#D6D3D1]">
                      <div className="md:col-span-2">
                        <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                          Judul Klip
                        </label>
                        <input
                          type="text"
                          value={clipTitle}
                          onChange={(e) => setClipTitle(e.target.value)}
                          className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                        />
                      </div>

                      <div className="flex space-x-2">
                        <div className="flex-1">
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                            Start (s)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            value={startTime}
                            onChange={(e) => setStartTime(parseFloat(e.target.value) || 0)}
                            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                          />
                        </div>
                        <div className="flex-1">
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                            End (s)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            value={endTime}
                            onChange={(e) => setEndTime(parseFloat(e.target.value) || 0)}
                            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* 9:16 Vertical Crop Simulator */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                      {/* Visual 9:16 Phone Mockup Box with Real Video Stream */}
                      <div className="flex flex-col items-center md:sticky md:top-36">
                        {/* Bezel ponsel; ukuran layar ditentukan rasio 9:16 sesungguhnya */}
                        <div className="w-[230px] p-[5px] bg-[#292524] rounded-[36px] shadow-2xl">
                          <SubtitleFrame
                            font={font}
                            fontSize={fontSize}
                            primaryColor={primaryColor}
                            activeColor={activeColor}
                            outlineWidth={outlineWidth}
                            shadowDepth={shadowDepth}
                            isUppercase={isUppercase}
                            position={subtitlePosition}
                            marginV={marginV}
                            motionType={motionType}
                            highlightBgColor={highlightBgColor}
                            enableKeywordColor={enableKeywordColor}
                            keywordColor={keywordColor}
                            enableDynamicScaling={enableDynamicScaling}
                            enableEmojiInjection={enableEmojiInjection}
                            glowEffect={glowEffect}
                            framingLayout={framingLayout}
                            screenMode={screenMode}
                            personShape={personShape}
                            personScale={personScale}
                            personOffsetX={personOffsetX}
                            personOffsetY={personOffsetY}
                            screenOffsetX={screenOffsetX}
                            screenOffsetY={screenOffsetY}
                            screenScale={screenScale}
                            screenAspect={screenAspect}
                            enableVocalDynamics={enableVocalDynamics}
                            videoFilter={videoFilter}
                            overlayIntro={ovIntro ? clipTitle : null}
                            overlayOutro={ovOutro ? ovOutroText : null}
                            overlayLowerThird={ovLower ? ovLowerText || 'Nama' : null}
                            videoSrc={activeVideoId ? videosApi.getStreamUrl(activeVideoId) : undefined}
                            cropOffsetX={cropOffsetX}
                            videoRef={videoRef}
                            onTimeUpdate={handleTimeUpdate}
                            onVideoClick={togglePlay}
                            isMuted={isMuted}
                            className="rounded-[31px] text-white select-none"
                          >
                            {/* Top Phone Sensor Notch */}
                            <div className="absolute top-2 left-1/2 -translate-x-1/2 w-20 h-4 bg-[#292524] rounded-full flex items-center justify-center">
                              <div className="w-2.5 h-2.5 rounded-full bg-black/60 mr-1" />
                              <div className="w-1.5 h-1.5 rounded-full bg-blue-900/50" />
                            </div>

                            {/* Header indicators inside screen */}
                            <div className="absolute top-0 left-0 right-0 flex justify-between items-center text-[10px] text-white/70 font-mono pt-4 px-3">
                              <span>9:16</span>
                              <span className="bg-black/50 px-1.5 py-0.5 rounded backdrop-blur-xs">1080×1920</span>
                            </div>

                            {/* Optional Rule-of-Thirds Grid Overlay */}
                            {showGridGuide && (
                              <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 opacity-30">
                                <div className="border-r border-b border-white/50" />
                                <div className="border-r border-b border-white/50" />
                                <div className="border-b border-white/50" />
                                <div className="border-r border-b border-white/50" />
                                <div className="border-r border-b border-white/50" />
                                <div className="border-b border-white/50" />
                                <div className="border-r border-white/50" />
                                <div className="border-r border-white/50" />
                                <div />
                              </div>
                            )}

                            {/* Center Play/Pause Overlay Indicator */}
                            {!isPlaying && (
                              <div
                                onClick={togglePlay}
                                className="absolute inset-0 bg-black/30 backdrop-blur-xs flex items-center justify-center cursor-pointer pointer-events-auto group"
                              >
                                <div className="w-12 h-12 rounded-full bg-white/80 group-hover:bg-[#C2410C] text-[#1C1917] group-hover:text-white flex items-center justify-center shadow-lg transition-transform group-hover:scale-110">
                                  <Play className="w-6 h-6 ml-0.5 fill-current" />
                                </div>
                              </div>
                            )}

                            {/* Bottom Phone Bar */}
                            <div className="absolute bottom-1 left-1/2 -translate-x-1/2 w-24 h-1 bg-white/40 rounded-full" />
                          </SubtitleFrame>
                        </div>

                        {/* Preview controls under phone */}
                        <div className="flex items-center space-x-3 mt-3">
                          <button
                            type="button"
                            onClick={togglePlay}
                            className="px-3 py-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-lg text-xs font-semibold text-[#1C1917] flex items-center space-x-1 transition-colors"
                          >
                            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                            <span>{isPlaying ? 'Jeda' : 'Putar'}</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              if (videoRef.current) {
                                videoRef.current.currentTime = startTime;
                              }
                            }}
                            className="p-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-lg text-xs text-[#57534E]"
                            title="Ulangi dari awal klip"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>

                          <button
                            type="button"
                            onClick={() => setIsMuted(!isMuted)}
                            className="p-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-lg text-xs text-[#57534E]"
                            title={isMuted ? 'Buka Suara' : 'Bisukan'}
                          >
                            {isMuted ? <VolumeX className="w-3.5 h-3.5 text-red-500" /> : <Volume2 className="w-3.5 h-3.5" />}
                          </button>

                          <button
                            type="button"
                            onClick={() => setShowGridGuide(!showGridGuide)}
                            className={`p-1.5 rounded-lg text-xs transition-colors ${
                              showGridGuide ? 'bg-[#C2410C]/10 text-[#C2410C]' : 'bg-[#F5F5F4] text-[#78716C]'
                            }`}
                            title="Panduan Garis Sepertiga (Rule of Thirds)"
                          >
                            <Layers className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <p className="text-[11px] font-mono text-[#78716C] mt-2">
                          Segmen {startTime.toFixed(1)}s – {endTime.toFixed(1)}s ({Math.max(0, endTime - startTime).toFixed(1)}s)
                        </p>
                      </div>

                      {/* Framing, Subtitle & Audio Controls */}
                      {/* Framing, Subtitle & Audio Controls (No scroll inside scroll, opens to parent div) */}
                      <div className="space-y-4">
                        {/* Mode Switcher: Gunakan Preset vs Kustom */}
                        <div className="p-1 bg-[#F5F5F4] rounded-2xl border border-[#E7E5E4] flex items-center space-x-1">
                          <button
                            type="button"
                            onClick={() => setPresetMode('preset')}
                            className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                              presetMode === 'preset'
                                ? 'bg-[#C2410C] text-white shadow-xs'
                                : 'text-[#78716C] hover:text-[#1C1917]'
                            }`}
                          >
                            <Sparkles className="w-4 h-4" />
                            <span>Pilih Template Preset</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setPresetMode('custom');
                              setPresetId(null);
                            }}
                            className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                              presetMode === 'custom'
                                ? 'bg-[#C2410C] text-white shadow-xs'
                                : 'text-[#78716C] hover:text-[#1C1917]'
                            }`}
                          >
                            <Sliders className="w-4 h-4" />
                            <span>Kustomisasi Bebas</span>
                          </button>
                        </div>

                        {/* ====================================================
                            MODE 1: PILIH TEMPLATE PRESET (Tanpa tab Visual/Audio)
                            ==================================================== */}
                        {presetMode === 'preset' && (
                          <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-2 text-xs font-bold text-[#1C1917]">
                                  <Bookmark className="w-4 h-4 text-[#C2410C]" />
                                  <span>Pilih Template Shorts</span>
                                </div>
                                {onNavigatePresets && (
                                  <button
                                    type="button"
                                    onClick={onNavigatePresets}
                                    className="text-xs font-semibold text-[#C2410C] hover:underline flex items-center space-x-1"
                                  >
                                    <Plus className="w-3.5 h-3.5" />
                                    <span>Buat Preset Baru</span>
                                  </button>
                                )}
                              </div>

                              <p className="text-xs text-[#57534E] leading-relaxed">
                                Klik salah satu template di bawah untuk menerapkan framing kamera, gaya teks, posisi Y, dan musiknya secara otomatis.
                              </p>

                              {/* Filter kategori */}
                              <div className="flex flex-wrap gap-1.5">
                                {['semua', 'streamer', 'podcast', 'educational', 'motivational', 'gaming', 'text'].map((c) => (
                                  <button
                                    key={c}
                                    type="button"
                                    onClick={() => setPresetCat(c)}
                                    className={`px-2.5 py-1 text-[11px] font-bold rounded-full transition-all ${
                                      presetCat === c
                                        ? 'bg-[#C2410C] text-white'
                                        : 'bg-[#F5F5F4] text-[#57534E] hover:bg-[#E7E5E4]'
                                    }`}
                                  >
                                    {c === 'semua' ? 'Semua' : c}
                                  </button>
                                ))}
                              </div>

                              {/* Daftar Template - Natural parent flow, no inner scroll */}
                              <div className="grid grid-cols-1 gap-2.5">
                                {presets.filter((p) => presetCat === 'semua' || (p.category || 'text') === presetCat).map((p) => {
                                  const isSelected = presetId === p.id;
                                  return (
                                    <div
                                      key={p.id}
                                      onClick={() => applyPreset(p)}
                                      className={`p-3.5 rounded-2xl border text-left cursor-pointer transition-all ${
                                        isSelected
                                          ? 'bg-amber-50/90 border-[#C2410C] shadow-sm ring-2 ring-[#C2410C]/30'
                                          : 'bg-white border-[#E7E5E4] hover:border-[#C2410C]/50 hover:bg-[#FAFAF9]'
                                      }`}
                                    >
                                      <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center space-x-2">
                                          <span className="text-xs font-bold text-[#1C1917]">{p.name}</span>
                                          {p.is_builtin ? (
                                            <span className="px-1.5 py-0.5 bg-[#E7E5E4] text-[#57534E] text-[10px] font-semibold rounded">
                                              Bawaan
                                            </span>
                                          ) : (
                                            <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-semibold rounded">
                                              Kustom
                                            </span>
                                          )}
                                          {p.category && p.category !== 'text' && (
                                            <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-[10px] font-semibold rounded">
                                              {p.category}
                                            </span>
                                          )}
                                        </div>

                                        <div className="flex items-center space-x-1.5">
                                          <div
                                            className="w-3 h-3 rounded-full border border-black/20"
                                            style={{ backgroundColor: p.active_color }}
                                            title={`Warna Aktif: ${p.active_color}`}
                                          />
                                          <div
                                            className="w-3 h-3 rounded-full border border-black/20"
                                            style={{ backgroundColor: p.primary_color }}
                                            title={`Warna Dasar: ${p.primary_color}`}
                                          />
                                        </div>
                                      </div>

                                      {p.description && (
                                        <p className="text-xs text-[#78716C] line-clamp-1 mb-2">
                                          {p.description}
                                        </p>
                                      )}

                                      <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                                        <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md">
                                          {p.crop_mode === 'smart' ? '👁️ Smart Crop' : '📐 Center Crop'}
                                        </span>
                                        <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md">
                                          {p.font} • {p.font_size}px
                                        </span>
                                        <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-mono rounded-md font-semibold">
                                          Pos Y: {p.margin_v ?? 340}px
                                        </span>
                                        <span className="px-2 py-0.5 bg-[#F5F5F4] text-[#57534E] font-medium rounded-md">
                                          BGM: {Math.round((p.bgm_volume ?? 0.2) * 100)}%
                                        </span>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>

                            {/* Tombol Lanjutkan Perubahan setelah pilih preset */}
                            <div className="space-y-2 pt-1">
                              <button
                                type="button"
                                onClick={() => setPresetMode('custom')}
                                className="w-full py-3.5 px-4 bg-[#C2410C] hover:bg-[#9A3412] text-white font-bold rounded-xl shadow-lg shadow-[#C2410C]/25 transition-all flex items-center justify-center space-x-2 text-sm"
                              >
                                <Sliders className="w-4 h-4" />
                                <span>Lanjutkan Perubahan</span>
                                <ArrowRight className="w-4 h-4" />
                              </button>
                              <p className="text-center text-xs text-[#78716C]">
                                Buka kustomisasi untuk menggeser posisi Y teks, mengubah warna, atau mengatur audio secara manual.
                              </p>
                            </div>
                          </div>
                        )}

                        {/* ====================================================
                            MODE 2: KUSTOMISASI BEBAS (Tab Visual & Audio)
                            ==================================================== */}
                        {presetMode === 'custom' && (
                          <div className="space-y-4 animate-in fade-in duration-200">
                            <div className="flex items-center justify-between p-3 bg-stone-100 rounded-xl border border-stone-200">
                              <div className="flex items-center space-x-2 text-xs font-bold text-stone-800">
                                <Sliders className="w-4 h-4 text-[#C2410C]" />
                                <span>Mode Kustomisasi Aktif</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setPresetMode('preset')}
                                className="text-xs font-semibold text-[#C2410C] hover:underline flex items-center space-x-1"
                              >
                                <ArrowLeft className="w-3.5 h-3.5" />
                                <span>Pilih Template Lain</span>
                              </button>
                            </div>

                            {/* Control Panel Tabs */}
                            <div className="grid grid-cols-2 gap-2 p-1 bg-[#F5F5F4] rounded-xl">
                          <button
                            type="button"
                            onClick={() => setControlTab('visual')}
                            className={`py-2 text-xs font-semibold rounded-lg transition-all flex items-center justify-center space-x-1.5 ${
                              controlTab === 'visual'
                                ? 'bg-white text-[#C2410C] shadow-sm'
                                : 'text-[#78716C] hover:text-[#1C1917]'
                            }`}
                          >
                            <Palette className="w-3.5 h-3.5" />
                            <span>Visual</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setControlTab('audio')}
                            className={`py-2 text-xs font-semibold rounded-lg transition-all flex items-center justify-center space-x-1.5 ${
                              controlTab === 'audio'
                                ? 'bg-white text-[#C2410C] shadow-sm'
                                : 'text-[#78716C] hover:text-[#1C1917]'
                            }`}
                          >
                            <AudioLines className="w-3.5 h-3.5" />
                            <span>Audio</span>
                          </button>
                        </div>

                        <div className={controlTab === 'visual' ? 'space-y-5' : 'hidden'}>
                          {/* 1. LEVEL 1: JENIS KOMPOSISI UTAMA */}
                          <div>
                            <label className="block text-xs font-bold text-[#78716C] uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                              <Layers className="w-3.5 h-3.5 text-[#C2410C]" />
                              <span>Tata Letak Komposisi (Layout)</span>
                            </label>
                            <div className="grid grid-cols-3 gap-2 p-1 bg-[#F5F5F4] rounded-xl">
                              {[
                                { id: 'single', name: 'Without Overlay', icon: '📱' },
                                { id: 'pip', name: 'With Overlay', icon: '🎴' },
                                { id: 'streamer', name: 'Streamer', icon: '🎮' },
                              ].map((cat) => {
                                const isSelected =
                                  cat.id === 'pip'
                                    ? framingLayout === 'pip_full' || framingLayout === 'pip_center' || framingLayout === 'overlay_pip'
                                    : cat.id === 'streamer'
                                    ? framingLayout === 'streamer_face_top' || framingLayout === 'streamer_face_bottom'
                                    : framingLayout === 'single' || framingLayout === 'fit_16_9_center';

                                return (
                                  <button
                                    key={cat.id}
                                    type="button"
                                    onClick={() => {
                                      if (cat.id === 'pip') {
                                        setFramingLayout(screenMode === 'center' ? 'pip_center' : 'pip_full');
                                      } else if (cat.id === 'streamer') {
                                        setFramingLayout('streamer_face_top');
                                      } else {
                                        setFramingLayout(screenMode === 'center' ? 'fit_16_9_center' : 'single');
                                      }
                                    }}
                                    className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                                      isSelected
                                        ? 'bg-white text-[#C2410C] shadow-xs'
                                        : 'text-[#78716C] hover:text-[#1C1917]'
                                    }`}
                                  >
                                    <span>{cat.icon}</span>
                                    <span>{cat.name}</span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>

                          {/* Deteksi Posisi Wajah (5.1 Face Anchor) */}
                          <div className="p-3 bg-[#FFF7ED] border border-[#FDBA74] rounded-xl space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold text-[#1C1917]">🎯 Posisi Wajah Streamer</span>
                              <button
                                type="button"
                                onClick={handleAnalyzeFaceAnchor}
                                disabled={!selectedClip || analyzingFace}
                                className="px-3 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-bold rounded-lg transition-all flex items-center space-x-1.5 disabled:opacity-50"
                                title="Analisis zona wajah untuk rekomendasi layout"
                              >
                                {analyzingFace ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : null}
                                <span>{analyzingFace ? 'Menganalisis...' : 'Deteksi Posisi Wajah'}</span>
                              </button>
                            </div>
                            {faceAnchor && (
                              <div className="text-xs text-[#57534E] space-y-1.5">
                                <p>
                                  Zona <strong className="text-[#C2410C] uppercase">{faceAnchor.dominant_zone}</strong>
                                  {' '}• coverage {Math.round(faceAnchor.face_coverage * 100)}%
                                  {' '}• saran layout <strong className="font-mono">{faceAnchor.recommended_layout}</strong>
                                </p>
                                {faceAnchor.warning && (
                                  <p className="text-amber-700">⚠️ {faceAnchor.warning}</p>
                                )}
                                <button
                                  type="button"
                                  onClick={applyFaceRecommendation}
                                  className="px-3 py-1.5 bg-white hover:bg-[#F5F5F4] text-[#C2410C] border border-[#FDBA74] text-xs font-bold rounded-lg transition-all"
                                >
                                  Terapkan Saran Layout
                                </button>
                              </div>
                            )}
                          </div>

                          {/* ========================================================
                              KATEGORI 1: WITHOUT OVERLAY
                             ======================================================== */}
                          {(framingLayout === 'single' || framingLayout === 'fit_16_9_center') && (
                            <div className="space-y-4 pt-1 animate-in fade-in duration-200">
                              {/* Format Tampilan */}
                              <div>
                                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                                  Format Tampilan
                                </label>
                                <div className="grid grid-cols-2 gap-2">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setFramingLayout('single');
                                      setScreenMode('full');
                                    }}
                                    className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                                      framingLayout === 'single'
                                        ? 'bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]'
                                        : 'bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]'
                                    }`}
                                  >
                                    <span>📱 9:16 Penuh (Vertikal)</span>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setFramingLayout('fit_16_9_center');
                                      setScreenMode('center');
                                    }}
                                    className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                                      framingLayout === 'fit_16_9_center'
                                        ? 'bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]'
                                        : 'bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]'
                                    }`}
                                  >
                                    <span>🖼️ 16:9 di Tengah (Ambient Blur)</span>
                                  </button>
                                </div>
                              </div>

                              {/* Jika 9:16 Penuh: Tampilkan Mode Pemotongan Kamera */}
                              {framingLayout === 'single' && (
                                <div className="space-y-4 pt-2 border-t border-[#E7E5E4]">
                                  <div>
                                    <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                                      Kamera AI & Pemotongan
                                    </label>
                                    <div className="grid grid-cols-3 gap-2">
                                      {[
                                        { id: 'smart', label: '👁️ Ikuti Wajah' },
                                        { id: 'center', label: '📐 Posisi Tengah' },
                                        { id: 'manual', label: '↔️ Geser Manual' },
                                      ].map((mode) => (
                                        <button
                                          key={mode.id}
                                          type="button"
                                          onClick={() => {
                                            setCropMode(mode.id as any);
                                            if (mode.id === 'center') setCropOffsetX(0);
                                          }}
                                          className={`py-2 rounded-xl border text-xs font-bold transition-all ${
                                            cropMode === mode.id
                                              ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                              : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                          }`}
                                        >
                                          {mode.label}
                                        </button>
                                      ))}
                                    </div>
                                  </div>

                                  {/* Smart Deadzone & Transitions */}
                                  {cropMode === 'smart' && (
                                    <div className="space-y-3 pt-1">
                                      <div className="space-y-1.5">
                                        <div className="flex justify-between items-center text-xs">
                                          <span className="font-semibold text-[#57534E]">Batas Gerak Kepala (Deadzone)</span>
                                          <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                            {Math.round(smartDeadzone * 100)}%
                                          </span>
                                        </div>
                                        <input
                                          type="range"
                                          min="10"
                                          max="90"
                                          step="5"
                                          value={Math.round(smartDeadzone * 100)}
                                          onChange={(e) => setSmartDeadzone(parseInt(e.target.value) / 100)}
                                          className="w-full accent-[#C2410C] cursor-pointer"
                                        />
                                        <p className="text-[11px] text-[#78716C]">
                                          Kepala bebas bergerak di pita tengah selebar {Math.round(smartDeadzone * 100)}% tanpa menggeser kamera.
                                        </p>
                                      </div>

                                      <div className="space-y-1.5">
                                        <span className="block text-xs font-semibold text-[#57534E]">Transisi Pergeseran</span>
                                        <div className="grid grid-cols-2 gap-2">
                                          <button
                                            type="button"
                                            onClick={() => setSmartSnap(false)}
                                            className={`py-1.5 text-xs font-bold rounded-xl border transition-all ${
                                              !smartSnap
                                                ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                                : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                            }`}
                                          >
                                            Halus (Smooth Pan)
                                          </button>
                                          <button
                                            type="button"
                                            onClick={() => setSmartSnap(true)}
                                            className={`py-1.5 text-xs font-bold rounded-xl border transition-all ${
                                              smartSnap
                                                ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                                : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                            }`}
                                          >
                                            Snap (Seketika)
                                          </button>
                                        </div>
                                      </div>

                                      {/* Detection Feedback */}
                                      {loadingPreview ? (
                                        <p className="text-[11px] text-[#78716C] flex items-center space-x-1.5 pt-1">
                                          <Loader2 className="w-3 h-3 animate-spin" />
                                          <span>Mendeteksi posisi wajah pada klip ini...</span>
                                        </p>
                                      ) : reframePreview && reframePreview.detected ? (
                                        <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-[11px] text-emerald-800 flex items-center space-x-1.5">
                                          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                                          <span>
                                            Wajah terdeteksi di {Math.round(reframePreview.coverage * 100)}% frame ·{' '}
                                            {cameraMoves === 0
                                              ? 'kamera tidak perlu bergeser'
                                              : `kamera bergeser ${cameraMoves}x`}
                                          </span>
                                        </div>
                                      ) : reframePreview ? (
                                        <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-800 flex items-center space-x-1.5">
                                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                                          <span>Wajah tidak terdeteksi — crop memakai posisi tengah.</span>
                                        </div>
                                      ) : null}
                                    </div>
                                  )}

                                  {/* Manual X Offset Slider */}
                                  {cropMode === 'manual' && (
                                    <div className="space-y-1.5 pt-1">
                                      <div className="flex justify-between items-center text-xs">
                                        <span className="font-semibold text-[#57534E]">Geser Horizontal (X)</span>
                                        <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                          {cropOffsetX} px
                                        </span>
                                      </div>
                                      <input
                                        type="range"
                                        min="0"
                                        max="600"
                                        step="10"
                                        value={cropOffsetX}
                                        onChange={(e) => setCropOffsetX(parseInt(e.target.value))}
                                        className="w-full accent-[#C2410C] cursor-pointer"
                                      />
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Jika 16:9 di Tengah: Skala Layar Slider */}
                              {framingLayout === 'fit_16_9_center' && (
                                <div className="space-y-4 pt-2 border-t border-[#E7E5E4]">
                                  <div className="space-y-1.5">
                                    <div className="flex justify-between items-center text-xs">
                                      <span className="font-semibold text-[#57534E]">Zoom Skala Layar</span>
                                      <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                        {Math.round(screenScale * 100)}%
                                      </span>
                                    </div>
                                    <input
                                      type="range"
                                      min="50"
                                      max="150"
                                      step="5"
                                      value={Math.round(screenScale * 100)}
                                      onChange={(e) => setScreenScale(parseInt(e.target.value) / 100)}
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
                          {(framingLayout === 'streamer_face_top' || framingLayout === 'streamer_face_bottom') && (
                            <div className="space-y-4 pt-1 animate-in fade-in duration-200">
                              <div className="grid grid-cols-2 gap-2">
                                <button
                                  type="button"
                                  onClick={() => setFramingLayout('streamer_face_top')}
                                  className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all ${
                                    framingLayout === 'streamer_face_top'
                                      ? 'bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]'
                                      : 'bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]'
                                  }`}
                                >
                                  <span>🎮 Wajah Atas (40/60)</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setFramingLayout('streamer_face_bottom')}
                                  className={`py-2.5 px-3 rounded-xl border text-xs font-bold transition-all ${
                                    framingLayout === 'streamer_face_bottom'
                                      ? 'bg-[#FFF7ED] border-[#C2410C] text-[#C2410C] ring-1 ring-[#C2410C]'
                                      : 'bg-white border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]'
                                  }`}
                                >
                                  <span>🎮 Wajah Bawah (60/40)</span>
                                </button>
                              </div>
                              <p className="text-[11px] text-[#78716C]">
                                Posisi vertikal wajah terdeteksi otomatis saat render (tombol 🎯 di atas). Gagal deteksi → fallback split biasa.
                              </p>
                            </div>
                          )}

                          {/* ========================================================
                              KATEGORI 2: WITH OVERLAY
                             ======================================================== */}
                          {(framingLayout === 'pip_full' || framingLayout === 'pip_center' || framingLayout === 'overlay_pip') && (
                            <div className="space-y-4 pt-1 animate-in fade-in duration-200">
                              <div className="grid grid-cols-2 gap-3">
                                {/* Mode Layar Dasar */}
                                <div>
                                  <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                                    Layar Dasar
                                  </label>
                                  <div className="grid grid-cols-2 gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setScreenMode('full');
                                        setFramingLayout('pip_full');
                                      }}
                                      className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                                        screenMode === 'full'
                                          ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                          : 'bg-white text-[#57534E] border-[#D6D3D1]'
                                      }`}
                                    >
                                      9:16 Full
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setScreenMode('center');
                                        setFramingLayout('pip_center');
                                      }}
                                      className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                                        screenMode === 'center'
                                          ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                          : 'bg-white text-[#57534E] border-[#D6D3D1]'
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
                                      { id: 'circle', label: '⭕ Lingkaran' },
                                      { id: 'rounded', label: '🔲 Kotak' },
                                      { id: 'rectangle', label: '⏹️ Persegi' },
                                    ].map((s) => (
                                      <button
                                        key={s.id}
                                        type="button"
                                        onClick={() => setPersonShape(s.id as any)}
                                        className={`py-2 text-[11px] font-bold rounded-xl border transition-all ${
                                          personShape === s.id
                                            ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                            : 'bg-white text-[#57534E] border-[#D6D3D1]'
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
                                      { id: 'ai', label: '👁️ AI Wajah', mode: 'smart', x: 0 },
                                      { id: 'br', label: '↘️ Kanan Bwh', mode: 'manual', x: 1380 },
                                      { id: 'bl', label: '↙️ Kiri Bwh', mode: 'manual', x: 0 },
                                      { id: 'mid', label: '📐 Tengah', mode: 'manual', x: 690 },
                                    ].map((pos) => {
                                      const isAct =
                                        pos.id === 'ai'
                                          ? cropMode === 'smart'
                                          : cropMode === 'manual' &&
                                            (pos.id === 'br' ? cropOffsetX >= 1100 : pos.id === 'bl' ? cropOffsetX <= 200 : cropOffsetX > 200 && cropOffsetX < 1100);

                                      return (
                                        <button
                                          key={pos.id}
                                          type="button"
                                          onClick={() => {
                                            setCropMode(pos.mode as any);
                                            setCropOffsetX(pos.x);
                                          }}
                                          className={`py-2 text-[11px] font-bold rounded-xl border transition-all ${
                                            isAct
                                              ? 'bg-[#C2410C] text-white border-[#C2410C]'
                                              : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                          }`}
                                        >
                                          {pos.label}
                                        </button>
                                      );
                                    })}
                                  </div>
                                </div>

                                {cropMode === 'manual' && (
                                  <div className="space-y-1.5">
                                    <div className="flex justify-between items-center text-xs">
                                      <span className="font-semibold text-[#57534E]">Posisi Sumber Kamera (X)</span>
                                      <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                        {cropOffsetX} px
                                      </span>
                                    </div>
                                    <input
                                      type="range"
                                      min="0"
                                      max="1380"
                                      step="20"
                                      value={cropOffsetX}
                                      onChange={(e) => setCropOffsetX(parseInt(e.target.value))}
                                      className="w-full accent-[#C2410C] cursor-pointer"
                                    />
                                  </div>
                                )}
                              </div>

                              {/* Minimalist Facecam Controls */}
                              <div className="space-y-3.5 pt-3 border-t border-[#E7E5E4]">
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-bold text-[#1C1917] uppercase tracking-wider">
                                    Ukuran & Posisi Tampilan Facecam
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setPersonOffsetX(0);
                                      setPersonOffsetY(400);
                                      setPersonScale(0.35);
                                      setPersonShape('circle');
                                    }}
                                    className="text-xs text-[#C2410C] hover:underline flex items-center space-x-1 font-semibold"
                                  >
                                    <RotateCcw className="w-3.5 h-3.5" />
                                    <span>Reset Posisi</span>
                                  </button>
                                </div>

                                {/* Skala Facecam */}
                                <div className="space-y-1.5">
                                  <div className="flex justify-between items-center text-xs">
                                    <span className="font-semibold text-[#57534E]">Ukuran Facecam (Skala PIP)</span>
                                    <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                      {Math.round(personScale * 100)}%
                                    </span>
                                  </div>
                                  <input
                                    type="range"
                                    min="15"
                                    max="75"
                                    step="5"
                                    value={Math.round(personScale * 100)}
                                    onChange={(e) => setPersonScale(parseInt(e.target.value) / 100)}
                                    className="w-full accent-[#C2410C] cursor-pointer"
                                  />
                                </div>

                                {/* Posisi X & Y Facecam */}
                                <div className="grid grid-cols-2 gap-3">
                                  <div className="space-y-1.5">
                                    <div className="flex justify-between items-center text-xs">
                                      <span className="font-semibold text-[#57534E]">Geser X (Horizontal)</span>
                                      <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                        {personOffsetX} px
                                      </span>
                                    </div>
                                    <input
                                      type="range"
                                      min="-450"
                                      max="450"
                                      step="10"
                                      value={personOffsetX}
                                      onChange={(e) => setPersonOffsetX(parseInt(e.target.value))}
                                      className="w-full accent-[#C2410C] cursor-pointer"
                                    />
                                  </div>

                                  <div className="space-y-1.5">
                                    <div className="flex justify-between items-center text-xs">
                                      <span className="font-semibold text-[#57534E]">Geser Y (Vertikal)</span>
                                      <span className="font-mono font-bold text-[#C2410C] bg-orange-50 px-2 py-0.5 rounded border border-orange-200 text-[11px]">
                                        {personOffsetY} px
                                      </span>
                                    </div>
                                    <input
                                      type="range"
                                      min="-800"
                                      max="800"
                                      step="10"
                                      value={personOffsetY}
                                      onChange={(e) => setPersonOffsetY(parseInt(e.target.value))}
                                      className="w-full accent-[#C2410C] cursor-pointer"
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                        {/* Save Preset Action Card */}
                        <div className="p-3 bg-[#F5F5F4] rounded-2xl border border-[#E7E5E4] space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                              <Bookmark className="w-3.5 h-3.5" />
                              <span>Simpan Konfigurasi Preset</span>
                            </span>
                            {presetId && (
                              <span className="text-[10px] px-2 py-0.5 bg-amber-100/80 text-amber-900 rounded-full font-semibold">
                                Berbasis: {presets.find((p) => p.id === presetId)?.name || 'Preset'}
                              </span>
                            )}
                          </div>

                          {showPresetForm ? (
                            <div className="space-y-2.5 p-2.5 bg-white rounded-xl border border-[#E7E5E4]">
                              <div>
                                <label className="block text-[11px] font-semibold text-[#57534E] mb-1">
                                  Nama Preset Baru <span className="text-red-500">*</span>
                                </label>
                                <input
                                  type="text"
                                  value={presetName}
                                  onChange={(e) => setPresetName(e.target.value)}
                                  placeholder="Contoh: Podcast Dark Minimalis..."
                                  className="w-full px-3 py-1.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-lg text-xs text-[#1C1917] focus:border-[#C2410C] outline-none"
                                />
                              </div>

                              <div>
                                <label className="block text-[11px] font-semibold text-[#57534E] mb-1">
                                  Deskripsi (Opsional)
                                </label>
                                <input
                                  type="text"
                                  value={presetDescription}
                                  onChange={(e) => setPresetDescription(e.target.value)}
                                  placeholder="Penjelasan singkat gaya..."
                                  className="w-full px-3 py-1.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-lg text-xs text-[#1C1917] focus:border-[#C2410C] outline-none"
                                />
                              </div>

                              <div className="p-2 bg-[#F5F5F4] rounded-lg text-[10px] text-[#57534E] space-y-0.5">
                                <div><strong>Akan menyimpan:</strong> Layout {framingLayout}, Visual {cropMode}, {font} {fontSize}px, Pos Y: {marginV}px, BGM {Math.round(bgmVolume * 100)}% ({audioMode})</div>
                              </div>

                              <div className="flex items-center space-x-2 pt-1">
                                <button
                                  type="button"
                                  onClick={handleSavePreset}
                                  disabled={savingPreset || !presetName.trim()}
                                  className="flex-1 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-lg transition-all disabled:opacity-50 flex items-center justify-center space-x-1.5"
                                >
                                  {savingPreset ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                                  <span>Simpan Preset Utuh</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setShowPresetForm(false);
                                    setPresetName('');
                                    setPresetDescription('');
                                  }}
                                  className="px-3 py-1.5 text-xs font-semibold text-[#57534E] hover:bg-[#E7E5E4] rounded-lg transition-colors"
                                >
                                  Batal
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center space-x-2">
                              <button
                                type="button"
                                onClick={() => setShowPresetForm(true)}
                                className="flex-1 py-2 text-xs font-semibold text-[#1C1917] bg-white border border-[#D6D3D1] hover:border-[#C2410C] hover:text-[#C2410C] rounded-xl transition-all flex items-center justify-center space-x-1.5 shadow-xs"
                              >
                                <Save className="w-3.5 h-3.5 text-[#C2410C]" />
                                <span>Simpan Konfigurasi Sebagai Preset</span>
                              </button>

                              {presetId && !presets.find((p) => p.id === presetId)?.is_builtin && (
                                <button
                                  type="button"
                                  onClick={handleUpdatePreset}
                                  disabled={savingPreset}
                                  className="px-3 py-2 text-xs font-semibold text-[#57534E] bg-white border border-[#D6D3D1] hover:border-[#C2410C] hover:text-[#C2410C] rounded-xl transition-all disabled:opacity-50 flex items-center space-x-1"
                                  title="Perbarui preset ini dengan seluruh pengaturan saat ini"
                                >
                                  <RefreshCw className="w-3 h-3" />
                                  <span>Update</span>
                                </button>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Subtitle Motion Type Quick Selector */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />
                            <span>Gaya Animasi Subtitle (Motion Type)</span>
                          </label>
                          <div className="grid grid-cols-4 gap-1.5 p-1 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4]">
                            {[
                              { id: 'single_word_pop', label: 'Hormozi', icon: '🔥' },
                              { id: 'karaoke', label: 'Karaoke', icon: '🎤' },
                              { id: 'background_box', label: 'Sticker', icon: '🏷️' },
                              { id: 'typewriter', label: 'Typewriter', icon: '⌨️' },
                              { id: 'slide_up', label: 'Slide Up', icon: '⬆️' },
                              { id: 'bounce_in', label: 'Bounce', icon: '🏀' },
                              { id: 'zoom_flash', label: 'Zoom', icon: '💥' },
                              { id: 'glitch_reveal', label: 'Glitch', icon: '👾' },
                            ].map((m) => (
                              <button
                                key={m.id}
                                type="button"
                                onClick={() => setMotionType(m.id as any)}
                                className={`py-2 px-1 text-[11px] font-bold rounded-lg transition-all flex flex-col items-center justify-center space-y-0.5 ${
                                  motionType === m.id
                                    ? 'bg-[#C2410C] text-white shadow-xs'
                                    : 'text-[#57534E] hover:bg-[#E7E5E4]'
                                }`}
                              >
                                <span className="text-sm">{m.icon}</span>
                                <span className="truncate">{m.label}</span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Video Filter Pack Quick Selector */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                            🎬 Filter Video
                          </label>
                          <div className="grid grid-cols-4 gap-1.5 p-1 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4]">
                            {[
                              { id: 'none', label: 'Tanpa', icon: '🚫' },
                              { id: 'cinematic', label: 'Sinema', icon: '🎬' },
                              { id: 'vivid', label: 'Vivid', icon: '🌈' },
                              { id: 'warm', label: 'Hangat', icon: '🌅' },
                              { id: 'cool', label: 'Sejuk', icon: '❄️' },
                              { id: 'drama', label: 'Drama', icon: '🎭' },
                              { id: 'vintage', label: 'Vint', icon: '📼' },
                            ].map((f) => (
                              <button
                                key={f.id}
                                type="button"
                                onClick={() => setVideoFilter(f.id)}
                                className={`py-2 px-1 text-[11px] font-bold rounded-lg transition-all flex flex-col items-center justify-center space-y-0.5 ${
                                  videoFilter === f.id
                                    ? 'bg-[#C2410C] text-white shadow-xs'
                                    : 'text-[#57534E] hover:bg-[#E7E5E4]'
                                }`}
                              >
                                <span className="text-sm">{f.icon}</span>
                                <span className="truncate">{f.label}</span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Overlay & Animasi */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-2">
                            ✨ Overlay & Animasi
                          </label>
                          <div className="space-y-2">
                            <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                              <span className="text-xs font-semibold text-[#1C1917]">Judul Intro</span>
                              <input type="checkbox" checked={ovIntro} onChange={(e) => setOvIntro(e.target.checked)} className="w-4 h-4 accent-[#C2410C] cursor-pointer" />
                            </label>
                            <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                              <span className="text-xs font-semibold text-[#1C1917]">CTA Outro</span>
                              <input type="checkbox" checked={ovOutro} onChange={(e) => setOvOutro(e.target.checked)} className="w-4 h-4 accent-[#C2410C] cursor-pointer" />
                            </label>
                            {ovOutro && (
                              <input type="text" value={ovOutroText} onChange={(e) => setOvOutroText(e.target.value)} placeholder="Follow untuk lebih banyak!" className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none" />
                            )}
                            <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                              <span className="text-xs font-semibold text-[#1C1917]">Lower Third</span>
                              <input type="checkbox" checked={ovLower} onChange={(e) => setOvLower(e.target.checked)} className="w-4 h-4 accent-[#C2410C] cursor-pointer" />
                            </label>
                            {ovLower && (
                              <input type="text" value={ovLowerText} onChange={(e) => setOvLowerText(e.target.value)} placeholder="Nama pembicara / channel" className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none" />
                            )}
                          </div>
                        </div>

                        {/* Quick Visual Emphasis Toggles */}
                        <div className="grid grid-cols-2 gap-2">
                          <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                            <span className="text-xs font-semibold text-[#1C1917] flex items-center space-x-1">
                              <span>🚀</span>
                              <span>Smart Emoji</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={enableEmojiInjection}
                              onChange={(e) => setEnableEmojiInjection(e.target.checked)}
                              className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                            />
                          </label>
                          <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                            <span className="text-xs font-semibold text-[#1C1917] flex items-center space-x-1">
                              <span>✨</span>
                              <span>Neon Glow</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={glowEffect}
                              onChange={(e) => setGlowEffect(e.target.checked)}
                              className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                            />
                          </label>
                        </div>

                        {/* Vocal Dynamics Audio Emotion Detection Toggle */}
                        <div className="p-3 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-base">🎙️</span>
                            <div>
                              <span className="text-xs font-bold text-[#1C1917] block">Deteksi Penekanan Vokal Otomatis (Vocal Dynamics)</span>
                              <span className="text-[11px] text-[#78716C]">Kata tegas membesar dinamis (125%-135%) dan kata pelan mengecil halus</span>
                            </div>
                          </div>
                          <input
                            type="checkbox"
                            checked={enableVocalDynamics}
                            onChange={(e) => setEnableVocalDynamics(e.target.checked)}
                            className="w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0"
                          />
                        </div>

                        {/* Font Selection */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
                            <Type className="w-3.5 h-3.5" />
                            <span>Tipografi Subtitle</span>
                          </label>
                          <select
                            value={font}
                            onChange={(e) => setFont(e.target.value)}
                            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                          >
                            {FONT_OPTIONS.map((f) => (
                              <option key={f.value} value={f.value}>
                                {f.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Font Size */}
                        <div>
                          <div className="flex justify-between text-xs text-[#57534E] mb-1">
                            <span>Ukuran Font</span>
                            <span className="font-mono font-semibold text-[#C2410C]">{fontSize} px</span>
                          </div>
                          <input
                            type="range"
                            min="18"
                            max="90"
                            step="2"
                            value={fontSize}
                            onChange={(e) => setFontSize(parseInt(e.target.value))}
                            className="w-full accent-[#C2410C] cursor-pointer"
                          />
                        </div>

                        {/* Active Karaoke Color Picker */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
                            <Palette className="w-3.5 h-3.5" />
                            <span>Warna Kata Aktif (Karaoke Burn-in)</span>
                          </label>
                          <div className="flex items-center space-x-2">
                            {colorPresets.map((p) => (
                              <button
                                key={p.hex}
                                type="button"
                                onClick={() => setActiveColor(p.hex)}
                                className={`w-7 h-7 rounded-full border-2 transition-all ${
                                  activeColor.toUpperCase() === p.hex
                                    ? 'scale-110 border-[#1C1917] shadow-md'
                                    : 'border-white hover:scale-105'
                                }`}
                                style={{ backgroundColor: p.hex }}
                                title={p.label}
                              />
                            ))}
                            <input
                              type="color"
                              value={activeColor}
                              onChange={(e) => setActiveColor(e.target.value)}
                              className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                              title="Pilih warna custom"
                            />
                          </div>
                        </div>

                        {/* Base Subtitle Color */}
                        <div>
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
                            <Palette className="w-3.5 h-3.5" />
                            <span>Warna Dasar Teks</span>
                          </label>
                          <div className="flex items-center space-x-2">
                            <input
                              type="color"
                              value={primaryColor}
                              onChange={(e) => setPrimaryColor(e.target.value)}
                              className="w-8 h-8 rounded-lg cursor-pointer bg-transparent border-0"
                              title="Pilih warna dasar teks"
                            />
                            <span className="font-mono text-xs text-[#57534E]">{primaryColor.toUpperCase()}</span>
                          </div>
                        </div>

                        {/* Outline & Shadow */}
                        <div className="space-y-3">
                          <div>
                            <div className="flex justify-between text-xs text-[#57534E] mb-1">
                              <span>Ketebalan Outline</span>
                              <span className="font-mono font-semibold text-[#C2410C]">{outlineWidth}</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="10"
                              step="1"
                              value={outlineWidth}
                              onChange={(e) => setOutlineWidth(parseInt(e.target.value))}
                              className="w-full accent-[#C2410C] cursor-pointer"
                            />
                          </div>

                          <div>
                            <div className="flex justify-between text-xs text-[#57534E] mb-1">
                              <span>Kedalaman Shadow</span>
                              <span className="font-mono font-semibold text-[#C2410C]">{shadowDepth}</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="10"
                              step="1"
                              value={shadowDepth}
                              onChange={(e) => setShadowDepth(parseInt(e.target.value))}
                              className="w-full accent-[#C2410C] cursor-pointer"
                            />
                          </div>

                          <label className="flex items-center justify-between p-2.5 bg-[#F5F5F4] rounded-xl cursor-pointer">
                            <span className="text-xs font-semibold text-[#57534E]">HURUF BESAR SEMUA</span>
                            <input
                              type="checkbox"
                              checked={isUppercase}
                              onChange={(e) => setIsUppercase(e.target.checked)}
                              className="w-4 h-4 accent-[#C2410C] cursor-pointer"
                            />
                          </label>
                        </div>

                        {/* Subtitle Position Selection & Manual Y Slider */}
                        <div className="space-y-3">
                          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                            <Sliders className="w-3.5 h-3.5" />
                            <span>Posisi Vertikal Subtitle (Posisi Y)</span>
                          </label>

                          <div className="grid grid-cols-4 gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setSubtitlePosition('bottom');
                                setMarginV(340);
                              }}
                              className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                subtitlePosition === 'bottom' && marginV === 340
                                  ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                  : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                              }`}
                            >
                              Bawah
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSubtitlePosition('middle');
                                setMarginV(920);
                              }}
                              className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                subtitlePosition === 'middle' && marginV === 920
                                  ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                  : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                              }`}
                            >
                              Tengah
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSubtitlePosition('top');
                                setMarginV(1540);
                              }}
                              className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                subtitlePosition === 'top' && marginV === 1540
                                  ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                  : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                              }`}
                            >
                              Atas
                            </button>
                            <button
                              type="button"
                              onClick={() => setSubtitlePosition('custom')}
                              className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                subtitlePosition === 'custom' || (marginV !== 340 && marginV !== 920 && marginV !== 1540)
                                  ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                  : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                              }`}
                            >
                              Kustom
                            </button>
                          </div>

                          {/* Interactive Continuous Y-Slider */}
                          <div className="p-3 bg-[#F5F5F4] rounded-xl space-y-2 border border-[#E7E5E4]">
                            <div className="flex justify-between items-center text-xs">
                              <span className="font-semibold text-[#57534E]">Geser Bebas Posisi Y</span>
                              <span className="font-mono font-bold text-[#C2410C] bg-white px-2 py-0.5 rounded-md border border-[#D6D3D1] text-[11px]">
                                {marginV} px ({Math.round(((1920 - marginV) / 1920) * 100)}% dari atas)
                              </span>
                            </div>
                            <input
                              type="range"
                              min="100"
                              max="1750"
                              step="10"
                              value={marginV}
                              onChange={(e) => {
                                const val = parseInt(e.target.value);
                                setMarginV(val);
                                if (val >= 1300) setSubtitlePosition('top');
                                else if (val >= 700) setSubtitlePosition('middle');
                                else setSubtitlePosition('bottom');
                              }}
                              className="w-full accent-[#C2410C] cursor-pointer"
                            />
                            <div className="flex justify-between text-[10px] text-[#78716C]">
                              <span>Dekat Bawah (100px)</span>
                              <span>Tengah (920px)</span>
                              <span>Dekat Atas (1750px)</span>
                            </div>
                            <p className="text-[11px] text-[#78716C] mt-0.5">
                              Teks pada pratinjau ponsel di samping bergerak secara langsung saat slider digeser.
                            </p>
                          </div>
                        </div>
                        </div>

                        <div className={controlTab === 'audio' ? 'space-y-4' : 'hidden'}>
                          {/* Audio Mode */}
                          <div>
                            <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
                              <AudioLines className="w-3.5 h-3.5" />
                              <span>Mode Audio</span>
                            </label>
                            <div className="grid grid-cols-3 gap-2">
                              <button
                                type="button"
                                onClick={() => setAudioMode('mix')}
                                className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                  audioMode === 'mix'
                                    ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                    : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                }`}
                                title="Suara asli + BGM + narasi"
                              >
                                Gabung
                              </button>
                              <button
                                type="button"
                                onClick={() => setAudioMode('replace')}
                                className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                  audioMode === 'replace'
                                    ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                    : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                }`}
                                title="Hanya BGM dan narasi, suara asli dibuang"
                              >
                                Ganti
                              </button>
                              <button
                                type="button"
                                onClick={() => setAudioMode('original')}
                                className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                                  audioMode === 'original'
                                    ? 'bg-[#C2410C] text-white border-[#C2410C] shadow-xs'
                                    : 'bg-white text-[#57534E] border-[#D6D3D1] hover:bg-[#F5F5F4]'
                                }`}
                                title="Abaikan BGM dan narasi"
                              >
                                Suara Asli
                              </button>
                            </div>
                            <p className="text-[11px] text-[#78716C] mt-1">
                              {audioMode === 'mix' && 'Suara asli dipadukan dengan BGM dan narasi.'}
                              {audioMode === 'replace' && 'Suara asli dibuang, hanya BGM dan narasi yang terdengar.'}
                              {audioMode === 'original' && 'BGM dan narasi diabaikan, memakai audio video apa adanya.'}
                            </p>
                          </div>

                          {/* BGM */}
                          <div className="p-3 bg-[#F5F5F4] rounded-xl space-y-2.5">
                            <div className="flex items-center justify-between">
                              <label className="text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                                <Music className="w-3.5 h-3.5" />
                                <span>Musik Latar</span>
                              </label>
                              {onNavigateAudioLibrary && (
                                <button
                                  type="button"
                                  onClick={onNavigateAudioLibrary}
                                  className="text-[11px] font-semibold text-[#C2410C] hover:underline"
                                >
                                  Kelola Audio Library
                                </button>
                              )}
                            </div>

                            <select
                              value={audioTrackId ?? ''}
                              onChange={(e) => setAudioTrackId(e.target.value || null)}
                              disabled={audioMode === 'original'}
                              className="w-full px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none disabled:opacity-50"
                            >
                              <option value="">Tanpa musik latar</option>
                              {audioTracks.map((track) => (
                                <option key={track.id} value={track.id}>{track.title}</option>
                              ))}
                            </select>

                            {audioTracks.length === 0 && (
                              <p className="text-[11px] text-[#78716C]">
                                Pustaka audio masih kosong. Unggah trek di halaman Audio Library.
                              </p>
                            )}

                            {selectedAudioTrack && (
                              <audio
                                controls
                                preload="none"
                                src={audioApi.getStreamUrl(selectedAudioTrack)}
                                className="w-full h-8"
                              />
                            )}

                            <div>
                              <div className="flex justify-between text-xs text-[#57534E] mb-1">
                                <span>Volume BGM</span>
                                <span className="font-mono font-semibold text-[#C2410C]">{Math.round(bgmVolume * 100)}%</span>
                              </div>
                              <input
                                type="range"
                                min="0"
                                max="100"
                                step="5"
                                value={Math.round(bgmVolume * 100)}
                                onChange={(e) => setBgmVolume(parseInt(e.target.value) / 100)}
                                disabled={audioMode === 'original'}
                                className="w-full accent-[#C2410C] cursor-pointer disabled:opacity-50"
                              />
                            </div>
                          </div>

                          {/* Sound Effects */}
                          <div className="p-3 bg-[#F5F5F4] rounded-xl space-y-2.5">
                            <label className="text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                              <span>🔔</span>
                              <span>Sound Effects</span>
                            </label>

                            <div className="flex gap-2">
                              <select
                                value={sfxPickId}
                                onChange={(e) => setSfxPickId(e.target.value)}
                                disabled={audioMode === 'original'}
                                className="flex-1 px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none disabled:opacity-50"
                              >
                                <option value="">Pilih SFX...</option>
                                {sfxList.map((s) => (
                                  <option key={s.id} value={s.id}>{s.title}</option>
                                ))}
                              </select>
                              <input
                                type="number"
                                min="0"
                                step="0.5"
                                value={sfxPickAt}
                                onChange={(e) => setSfxPickAt(parseFloat(e.target.value) || 0)}
                                title="Offset detik dalam klip"
                                className="w-20 px-2 py-2 bg-white border border-[#D6D3D1] rounded-xl text-sm font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                              />
                              <button
                                type="button"
                                disabled={!sfxPickId || audioMode === 'original'}
                                onClick={() => {
                                  setSfxTriggers((prev) => [...prev, { sfx_id: sfxPickId, start_t: Math.max(0, sfxPickAt) }]);
                                  setSfxPickId('');
                                }}
                                className="px-3 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-bold rounded-xl disabled:opacity-50"
                              >
                                + Tambah
                              </button>
                            </div>

                            {sfxTriggers.length > 0 && (
                              <div className="space-y-1.5">
                                {sfxTriggers.map((t, i) => {
                                  const s = sfxList.find((x) => x.id === t.sfx_id);
                                  return (
                                    <div key={i} className="flex items-center justify-between bg-white border border-[#E7E5E4] rounded-lg px-2.5 py-1.5 text-xs">
                                      <span className="font-semibold text-[#1C1917]">🔔 {s?.title || t.sfx_id} <span className="font-mono text-[#78716C]">@{t.start_t}s</span></span>
                                      <button type="button" onClick={() => setSfxTriggers((prev) => prev.filter((_, j) => j !== i))} className="text-[#78716C] hover:text-red-600 font-bold px-1">✕</button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            <label className="flex items-start justify-between gap-2 pt-1 border-t border-[#E7E5E4] cursor-pointer">
                              <span>
                                <span className="block text-xs font-semibold text-[#1C1917]">Otomatis saat skor hook tinggi</span>
                                <span className="block text-[11px] text-[#78716C]">Mainkan SFX di 0.5 detik pertama bila skor ≥ ambang.</span>
                              </span>
                              <input type="checkbox" checked={sfxAuto} onChange={(e) => setSfxAuto(e.target.checked)} disabled={audioMode === 'original'} className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0" />
                            </label>
                            {sfxAuto && (
                              <div className="flex gap-2">
                                <select value={sfxAutoId} onChange={(e) => setSfxAutoId(e.target.value)} className="flex-1 px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none">
                                  <option value="">Pilih SFX...</option>
                                  {sfxList.map((s) => (
                                    <option key={s.id} value={s.id}>{s.title}</option>
                                  ))}
                                </select>
                                <input type="number" min="0" max="100" step="1" value={sfxThreshold} onChange={(e) => setSfxThreshold(parseInt(e.target.value) || 0)} title="Ambang skor" className="w-20 px-2 py-2 bg-white border border-[#D6D3D1] rounded-xl text-sm font-mono text-[#1C1917] focus:border-[#C2410C] outline-none" />
                              </div>
                            )}
                          </div>

                          {/* Voiceover */}
                          <div className="p-3 bg-[#F5F5F4] rounded-xl space-y-2.5">
                            <div className="flex items-center justify-between">
                              <label className="text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center space-x-1.5">
                                <Mic className="w-3.5 h-3.5" />
                                <span>Voiceover / Narasi</span>
                              </label>
                              {narrationDuration !== null && (
                                <span className="text-[11px] font-mono text-[#78716C]">
                                  ≈ {narrationDuration}s
                                </span>
                              )}
                            </div>

                            {settings && !settings.llm_connected && (
                              <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">
                                AI belum terhubung. Hubungkan di Pengaturan untuk membuat naskah otomatis, atau tulis naskahnya manual.
                              </p>
                            )}

                            <div className="flex items-center space-x-2">
                              <select
                                value={narrationStyle}
                                onChange={(e) => setNarrationStyle(e.target.value as NarrationStyle)}
                                className="flex-1 px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-xs font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                              >
                                <option value="hook_story">Hook Story</option>
                                <option value="summary">Ringkasan</option>
                                <option value="educational">Edukatif</option>
                              </select>

                              <button
                                type="button"
                                onClick={handleGenerateNarration}
                                disabled={generatingNarration || !selectedClip || settings?.llm_connected === false}
                                className="px-3 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all disabled:opacity-50 flex items-center space-x-1.5 shrink-0"
                              >
                                {generatingNarration ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <Wand2 className="w-3.5 h-3.5" />
                                )}
                                <span>Buat dengan AI</span>
                              </button>
                            </div>

                            <textarea
                              value={narrationText}
                              onChange={(e) => setNarrationText(e.target.value)}
                              rows={4}
                              placeholder="Naskah narasi akan muncul di sini dan bisa diedit bebas..."
                              className="w-full px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none resize-none"
                            />

                            <div className="flex items-center space-x-2">
                              <select
                                value={narrationVoice}
                                onChange={(e) => setNarrationVoice(e.target.value)}
                                className="flex-1 px-3 py-2 bg-white border border-[#D6D3D1] rounded-xl text-xs font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                              >
                                {voices.length === 0 && <option value="id-ID-ArdiNeural">Suara default</option>}
                                {voices.map((voice) => (
                                  <option key={voice.id} value={voice.id}>
                                    {voice.name} ({voice.lang})
                                  </option>
                                ))}
                              </select>

                              <button
                                type="button"
                                onClick={handleSynthesizeVoice}
                                disabled={synthesizing || !narrationText.trim()}
                                className="px-3 py-2 bg-[#1C1917] hover:bg-black text-white text-xs font-semibold rounded-xl transition-all disabled:opacity-50 flex items-center space-x-1.5 shrink-0"
                              >
                                {synthesizing ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <Music className="w-3.5 h-3.5" />
                                )}
                                <span>Buat Audio</span>
                              </button>
                            </div>

                            {narrationAudioUrl && (
                              <audio controls src={narrationAudioUrl} className="w-full h-8" />
                            )}

                            <label className="flex items-center justify-between p-2.5 bg-white border border-[#D6D3D1] rounded-xl cursor-pointer">
                              <span className="text-xs font-semibold text-[#57534E]">Pakai voiceover saat render</span>
                              <input
                                type="checkbox"
                                checked={useVoiceover}
                                onChange={(e) => setUseVoiceover(e.target.checked)}
                                disabled={!narrationText.trim() || audioMode === 'original'}
                                className="w-4 h-4 accent-[#C2410C] cursor-pointer disabled:opacity-50"
                              />
                            </label>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                    {/* Render Progress Banner when active */}
                    {rendering && (
                      <div className="p-4 bg-[#C2410C]/10 border border-[#C2410C]/20 rounded-xl space-y-2 animate-in fade-in duration-200 sticky bottom-28 z-10 bg-white/95 backdrop-blur shadow-sm">
                        <div className="flex items-center justify-between text-xs font-semibold text-[#C2410C] gap-2">
                          <span className="flex items-center space-x-1.5 truncate">
                            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                            <span className="truncate">{renderStatusMessage}</span>
                          </span>
                          <div className="flex items-center space-x-2 shrink-0">
                            <span className="font-mono text-sm">{renderProgress}%</span>
                            <button
                              type="button"
                              onClick={() => {
                                setRendering(false);
                                showNotification('success', 'Render tetap berjalan di antrean background worker. Anda dapat memantau atau mengunduh hasilnya di halaman Shorts.');
                              }}
                              className="text-[11px] bg-white text-[#C2410C] hover:bg-[#FFF7ED] border border-[#C2410C]/30 px-2 py-0.5 rounded-md font-medium transition-all shadow-xs"
                            >
                              Jalankan di Background
                            </button>
                          </div>
                        </div>
                        <div className="w-full h-2 bg-[#C2410C]/20 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#C2410C] transition-all duration-300 rounded-full"
                            style={{ width: `${renderProgress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Render Button & Save */}
                    <div className="shadow-md flex flex-col sm:flex-row items-center justify-between gap-4 sticky bottom-4 rounded p-4 bg-white">
                      <button
                        onClick={handleUpdateClip}
                        className="px-4 py-2 text-xs font-semibold text-[#57534E] hover:text-[#1C1917] hover:bg-[#E7E5E4] rounded-xl transition-all"
                      >
                        Simpan Perubahan Klip
                      </button>

                      <button
                        onClick={handleRender}
                        disabled={rendering}
                        className="w-full sm:w-auto px-7 py-3 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold text-sm rounded-xl shadow-lg shadow-[#C2410C]/25 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
                      >
                        {rendering ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Merender 9:16 ({renderProgress}%)...</span>
                          </>
                        ) : (
                          <>
                            <Scissors className="w-4 h-4" />
                            <span>Render Video 9:16 (Shorts)</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-white border border-[#E7E5E4] rounded-2xl p-12 text-center flex flex-col items-center justify-center space-y-4 shadow-xs min-h-[460px]">
                    <div className="w-16 h-16 rounded-2xl bg-orange-50 text-[#C2410C] flex items-center justify-center text-2xl shadow-xs border border-orange-100">
                      <Film className="w-8 h-8" />
                    </div>
                    <div className="space-y-1.5 max-w-md">
                      <h3 className="text-base font-bold text-[#1C1917]">
                        Pilih Kandidat Klip Terlebih Dahulu
                      </h3>
                      <p className="text-xs text-[#78716C] leading-relaxed">
                        Klik salah satu kandidat klip AI di kolom sebelah kiri untuk membuka editor studio, mengatur framing visual, posisi subtitle, dan merender video 9:16.
                      </p>
                    </div>
                    {clips.length > 0 && (
                      <button
                        type="button"
                        onClick={() => selectClipItem(clips[0])}
                        className="mt-2 px-4 py-2 bg-[#FFF7ED] text-[#C2410C] border border-[#FDBA74] hover:bg-[#FFEDD5] text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Pilih Klip Terbaik Pertama ({clips[0].hook_score} Score)</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
