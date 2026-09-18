import axios from 'axios';
import {
  VideoItem,
  VideoStatus,
  ClipItem,
  RenderedShort,
  ReframePreview,
  TextPreset,
  TextPresetPayload,
  AudioTrack,
  AudioMode,
  NarrationResult,
  NarrationStyle,
  SynthesizeResult,
  TTSItem,
  VoiceItem,
  SystemSettings,
  HealthStatus,
  YouTubeInfo,
  GeneralSettingsUpdate,
  BatchActionResponse,
  SubtitleMotionType,
  FramingLayout,
  ScreenMode,
  PersonShape,
  WahaStatus,
  WahaConfig,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    return Promise.reject(error);
  }
);

export const getMediaUrl = (url?: string | null): string => {
  if (!url) return '';
  const token = localStorage.getItem('token');
  if (!token) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(token)}`;
};

export const authApi = {
  getToken: () => localStorage.getItem('token'),
  setToken: (token: string) => localStorage.setItem('token', token),
  removeToken: () => localStorage.getItem('token') && localStorage.removeItem('token'),
  getStatus: async () => {
    const res = await api.get<{ is_configured: boolean; has_session: boolean }>('/auth/status');
    return res.data;
  },
  setup: async (pin: string) => {
    const res = await api.post<{ token: string }>('/auth/setup', { pin });
    return res.data;
  },
  login: async (pin: string) => {
    const res = await api.post<{ token: string }>('/auth/login', { pin });
    return res.data;
  },
  logout: async () => {
    await api.post('/auth/logout');
    localStorage.removeItem('token');
  },
};

export const videosApi = {
  list: async (page = 1, limit = 20, status?: string) => {
    const params = { page, limit, ...(status ? { status } : {}) };
    const res = await api.get<{ items: VideoItem[]; page: number; limit: number; total: number }>('/videos', { params });
    return res.data;
  },
  upload: async (file: File, autoGenerate = false, description?: string, onProgress?: (pct: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    if (autoGenerate) {
      formData.append('auto_generate', 'true');
    }
    if (description) {
      formData.append('description', description);
    }
    const res = await api.post('/videos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
    return res.data;
  },
  process: async (videoId: string) => {
    const res = await api.post(`/videos/${videoId}/process`);
    return res.data;
  },
  reanalyze: async (videoId: string, payload?: { min_dur?: number; max_dur?: number; custom_prompt_override?: string }) => {
    const res = await api.post<{ status: string; video_id: string; overrides: Record<string, unknown> }>(`/videos/${videoId}/reanalyze`, payload || {});
    return res.data;
  },
  autoGenerate: async (videoId: string) => {
    const res = await api.post<{ message: string; clips_queued: number; status: string }>(`/videos/${videoId}/auto-generate`);
    return res.data;
  },
  getStatus: async (videoId: string) => {
    const res = await api.get<VideoStatus>(`/videos/${videoId}/status`);
    return res.data;
  },
  getTranscript: async (videoId: string) => {
    const res = await api.get<{ full_text: string; language?: string; json_url: string }>(`/videos/${videoId}/transcript`);
    return res.data;
  },
  getClips: async (videoId: string) => {
    const res = await api.get<ClipItem[]>(`/videos/${videoId}/clips`);
    return res.data;
  },
  deleteVideo: async (videoId: string) => {
    await api.delete(`/videos/${videoId}`);
  },
  getYoutubeInfo: async (url: string) => {
    const res = await api.post<YouTubeInfo>('/videos/youtube/info', { url });
    return res.data;
  },
  downloadYoutube: async (url: string, quality?: string, autoGenerate = false) => {
    const res = await api.post<{
      video_id: string;
      filename: string;
      original_name: string;
      duration_seconds: number;
      file_size_bytes: number;
    }>('/videos/youtube/download', { url, quality, auto_generate: autoGenerate });
    return res.data;
  },
  batchDelete: async (ids: string[]) => {
    const res = await api.post<{ success_count: number; failed_count: number; message: string }>('/videos/batch-delete', { ids });
    return res.data;
  },
  batchAutoGenerate: async (ids: string[]) => {
    const res = await api.post<{ success_count: number; failed_count: number; message: string }>('/videos/batch-auto-generate', { ids });
    return res.data;
  },
  getStreamUrl: (videoId: string) => getMediaUrl(`/api/videos/${videoId}/stream`),
  getThumbnailUrl: (videoId: string) => getMediaUrl(`/api/videos/${videoId}/thumbnail`),
};

export const clipsApi = {
  update: async (clipId: string, payload: Partial<ClipItem>) => {
    const res = await api.patch<ClipItem>(`/clips/${clipId}`, payload);
    return res.data;
  },
  render: async (clipId: string, options: {
    crop_mode: string;
    crop_offset_x: number;
    smart_deadzone?: number;
    smart_pan_seconds?: number;
    smart_snap?: boolean;
    framing_layout?: FramingLayout | string;
    screen_mode?: ScreenMode;
    person_shape?: PersonShape;
    person_scale?: number;
    person_offset_x?: number;
    person_offset_y?: number;
    screen_offset_x?: number;
    screen_offset_y?: number;
    screen_scale?: number;
    screen_aspect?: string;
    video_filter?: string;
    enable_intro_title?: boolean;
    intro_title_duration?: number;
    intro_title_style?: string;
    enable_outro_cta?: boolean;
    outro_cta_text?: string;
    outro_cta_duration?: number;
    enable_lower_third?: boolean;
    lower_third_text?: string | null;
    sticker_path?: string | null;
    sticker_position?: string;
    sticker_scale?: number;
    preset_id?: string | null;
    font: string;
    font_size: number;
    active_color: string;
    primary_color: string;
    subtitle_position?: 'bottom' | 'middle' | 'top' | 'custom' | string;
    margin_v?: number;
    outline_width?: number;
    shadow_depth?: number;
    is_uppercase?: boolean;
    motion_type?: SubtitleMotionType | string;
    highlight_bg_color?: string;
    enable_keyword_color?: boolean;
    keyword_color?: string;
    enable_dynamic_scaling?: boolean;
    enable_emoji_injection?: boolean;
    glow_effect?: boolean;
    enable_vocal_dynamics?: boolean;
    use_voiceover?: boolean;
    narration_text?: string | null;
    narration_voice?: string | null;
    audio_track_id?: string | null;
    bgm_volume?: number;
    audio_mode?: AudioMode;
    sfx_triggers?: { sfx_id: string; start_t: number; volume: number }[];
    sfx_on_hook?: boolean;
    sfx_hook_sfx_id?: string | null;
    sfx_hook_threshold?: number;
  }) => {
    const res = await api.post<{ short_id: string; status: string }>(`/clips/${clipId}/render`, options);
    return res.data;
  },
  batchRender: async (clipIds: string[], renderSettings?: any) => {
    const res = await api.post<{ success_count: number; failed_count: number; message: string }>('/clips/batch-render', {
      clip_ids: clipIds,
      render_settings: renderSettings,
    });
    return res.data;
  },
  getReframePreview: async (clipId: string, deadzone = 0.5, snap = false) => {
    const res = await api.get<ReframePreview>(`/clips/${clipId}/reframe-preview`, {
      params: { deadzone, snap },
    });
    return res.data;
  },
  analyzeFaceAnchor: async (clipId: string) => {
    const res = await api.post<{
      clip_id: string;
      dominant_zone: string;
      avg_cx: number;
      avg_cy: number;
      face_coverage: number;
      recommended_layout: string;
      recommended_preset_id: string | null;
      warning: string | null;
    }>(`/clips/${clipId}/analyze-face-anchor`);
    return res.data;
  },
  generateNarration: async (clipId: string, payload: { style: NarrationStyle }) => {
    const res = await api.post<NarrationResult>(`/clips/${clipId}/generate-narration`, payload);
    return res.data;
  },
  synthesizeVoice: async (
    clipId: string,
    payload: { text: string; voice: string; rate?: string; pitch?: string }
  ) => {
    const res = await api.post<SynthesizeResult>(`/clips/${clipId}/synthesize-voice`, payload);
    return res.data;
  },
  // Menyertakan cache-buster agar elemen <audio> memuat ulang setelah narasi dibuat ulang.
  getNarrationAudioUrl: (clipId: string) => {
    const base = getMediaUrl(`/api/clips/${clipId}/narration-audio`);
    return `${base}${base.includes('?') ? '&' : '?'}t=${Date.now()}`;
  },
};

export const jobsApi = {
  list: async (params?: { status?: string; job_type?: string; limit?: number }) => {
    const res = await api.get<QueueJob[]>('/jobs', { params });
    return res.data;
  },
};

export interface QueueJob {
  id: string;
  job_type: string;
  ref_id: string;
  ref_kind: string;
  ref_label: string;
  status: string;
  progress: number;
  attempts: number;
  max_attempts: number;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export const shortsApi = {
  list: async (page = 1, limit = 20) => {
    const res = await api.get<{ items: RenderedShort[]; page: number; limit: number; total: number }>('/shorts', {
      params: { page, limit },
    });
    return res.data;
  },
  getDetail: async (shortId: string) => {
    const res = await api.get<RenderedShort>(`/shorts/${shortId}`);
    return res.data;
  },
  uploadDrive: async (shortId: string) => {
    const res = await api.post<{
      export_id: string;
      status: string;
      message?: string;
      gdrive_file_id?: string;
      gdrive_web_view_link?: string;
    }>(`/shorts/${shortId}/upload-gdrive`);
    return res.data;
  },
  getDriveStatus: async (shortId: string) => {
    const res = await api.get<{
      export_id: string;
      upload_status: string;
      upload_progress: number;
      gdrive_file_id?: string;
      gdrive_web_view_link?: string;
      error_message?: string;
    }>(`/shorts/${shortId}/upload-gdrive/status`);
    return res.data;
  },
  deleteShort: async (shortId: string) => {
    await api.delete(`/shorts/${shortId}`);
  },
  batchDelete: async (ids: string[]) => {
    const res = await api.post<BatchActionResponse>('/shorts/batch-delete', { ids });
    return res.data;
  },
  batchUploadDrive: async (ids: string[]) => {
    const res = await api.post<BatchActionResponse>('/shorts/batch-upload-gdrive', { ids });
    return res.data;
  },
};

export const ttsApi = {
  getVoices: async () => {
    const res = await api.get<VoiceItem[]>('/tts/voices');
    return res.data;
  },
  generate: async (text: string, voice = 'id-ID-ArdiNeural', rate = '+0%', pitch = '+0Hz') => {
    const res = await api.post<TTSItem>('/tts/generate', { text, voice, rate, pitch });
    return res.data;
  },
  getHistory: async () => {
    const res = await api.get<TTSItem[]>('/tts/history');
    return res.data;
  },
};

export const settingsApi = {
  get: async () => {
    const res = await api.get<SystemSettings>('/settings');
    return res.data;
  },
  updateAI: async (payload: { base_url: string; api_key?: string; model_name: string; temperature: number; prompt?: string; two_pass_enabled?: boolean; chunk_strategy?: string; vision_enabled?: boolean; vision_model?: string; vision_weight?: number }) => {
    const res = await api.post('/settings/ai', payload);
    return res.data;
  },
  testAI: async (payload?: { base_url?: string; api_key?: string; model_name?: string }) => {
    const res = await api.post<{ ok: boolean; model?: string; message: string; error?: string }>('/settings/ai/test', payload || {});
    return res.data;
  },
  updateGDrive: async (payload: {
    auth_type: string;
    target_folder_id: string;
    credentials_json?: string;
    service_account_json?: string;
    client_id?: string;
    client_secret?: string;
    refresh_token?: string;
  }) => {
    const res = await api.post('/settings/gdrive', payload);
    return res.data;
  },
  getGDriveOAuthUrl: async (redirectUri?: string) => {
    const params = redirectUri ? { redirect_uri: redirectUri } : {};
    const res = await api.get<{ auth_url: string; redirect_uri: string }>('/settings/gdrive/oauth/url', { params });
    return res.data;
  },
  exchangeGDriveOAuthCode: async (code: string, redirectUri?: string) => {
    const res = await api.post<{ ok: boolean; message: string }>('/settings/gdrive/oauth/exchange', {
      code,
      redirect_uri: redirectUri
    });
    return res.data;
  },
  testGDrive: async () => {
    const res = await api.post<{ ok: boolean; folder_name?: string; error?: string }>('/settings/gdrive/test');
    return res.data;
  },
  updateGeneral: async (payload: GeneralSettingsUpdate) => {
    const res = await api.post('/settings/general', payload);
    return res.data;
  },
  updateUIPreferences: async (payload: { clip_view_mode?: string; shorts_view_mode?: string }) => {
    const res = await api.post<{ ok: boolean; clip_view_mode: string; shorts_view_mode: string }>('/settings/ui-preferences', payload);
    return res.data;
  },
  getYouTubeCookiesStatus: async () => {
    const res = await api.get<{ has_cookies: boolean; file_path?: string; file_size_bytes?: number; line_count?: number }>('/settings/youtube/cookies');
    return res.data;
  },
  saveYouTubeCookies: async (cookies_content: string) => {
    const res = await api.post<{ status: string; message: string; has_cookies: boolean }>('/settings/youtube/cookies', { cookies_content });
    return res.data;
  },
  deleteYouTubeCookies: async () => {
    const res = await api.delete<{ status: string; message: string; has_cookies: boolean }>('/settings/youtube/cookies');
    return res.data;
  },
};

export const healthApi = {
  check: async () => {
    const res = await api.get<HealthStatus>('/health');
    return res.data;
  },
};

export const presetsApi = {
  list: async () => {
    const res = await api.get<TextPreset[]>('/presets');
    return res.data;
  },
  create: async (payload: TextPresetPayload) => {
    const res = await api.post<TextPreset>('/presets', payload);
    return res.data;
  },
  update: async (presetId: string, payload: Partial<TextPresetPayload>) => {
    const res = await api.put<TextPreset>(`/presets/${presetId}`, payload);
    return res.data;
  },
  remove: async (presetId: string) => {
    await api.delete(`/presets/${presetId}`);
  },
  resetBuiltins: async () => {
    const res = await api.post<TextPreset[]>('/presets/reset-builtins');
    return res.data;
  },
  exportPreset: async (presetId: string) => {
    const res = await api.get(`/presets/${presetId}/export`);
    return res.data;
  },
  importPreset: async (payload: Record<string, unknown>) => {
    const res = await api.post<TextPreset>('/presets/import', payload);
    return res.data;
  },
  duplicate: async (presetId: string) => {
    const res = await api.post<TextPreset>(`/presets/${presetId}/duplicate`);
    return res.data;
  },
};

export const audioApi = {
  list: async () => {
    const res = await api.get<AudioTrack[]>('/audio');
    return res.data;
  },
  upload: async (
    file: File,
    title?: string,
    onProgress?: (percent: number) => void
  ) => {
    const form = new FormData();
    form.append('file', file);
    if (title) form.append('title', title);

    const res = await api.post<AudioTrack>('/audio/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    });
    return res.data;
  },
  downloadYoutube: async (url: string) => {
    const res = await api.post<AudioTrack>('/audio/download-youtube', { url });
    return res.data;
  },
  remove: async (trackId: string) => {
    await api.delete(`/audio/${trackId}`);
  },
  getStreamUrl: (track: AudioTrack) => getMediaUrl(track.stream_url),
};

export interface SFXTrack {
  id: string;
  title: string;
  duration_seconds: number;
  file_size_bytes: number;
  is_builtin: boolean;
  stream_url: string;
  created_at: string;
}

export const sfxApi = {
  list: async () => {
    const res = await api.get<SFXTrack[]>('/sfx');
    return res.data;
  },
  upload: async (file: File, title?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (title) form.append('title', title);
    const res = await api.post<SFXTrack>('/sfx/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  remove: async (sfxId: string) => {
    await api.delete(`/sfx/${sfxId}`);
  },
  getStreamUrl: (track: SFXTrack) => getMediaUrl(track.stream_url),
};

export const wahaApi = {
  getStatus: async () => {
    const res = await api.get<WahaStatus>('/waha/status');
    return res.data;
  },
  updateConfig: async (payload: WahaConfig) => {
    const res = await api.post<{ ok: boolean; message: string }>('/waha/config', payload);
    return res.data;
  },
  startSession: async () => {
    const res = await api.post<{ ok: boolean; message: string }>('/waha/session/start');
    return res.data;
  },
  logoutSession: async () => {
    const res = await api.post<{ ok: boolean; message: string }>('/waha/session/logout');
    return res.data;
  },
  regenerateToken: async () => {
    const res = await api.post<{ ok: boolean; token: string; message: string }>('/waha/token/regenerate');
    return res.data;
  },
  unpair: async () => {
    const res = await api.post<{ ok: boolean; message: string }>('/waha/unpair');
    return res.data;
  },
  sendTestMessage: async (message?: string) => {
    const res = await api.post<{ ok: boolean; message: string }>('/waha/test-message', { message });
    return res.data;
  },
};

export default api;

