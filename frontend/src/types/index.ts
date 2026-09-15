export interface VideoItem {
  id: string;
  original_name: string;
  status: 'UPLOADED' | 'EXTRACTING_AUDIO' | 'TRANSCRIBING' | 'ANALYZING' | 'READY' | 'FAILED';
  duration_seconds: number;
  file_size_bytes: number;
  language?: string;
  thumbnail_url: string;
  description?: string;
  auto_generate_shorts?: boolean;
  clips_count?: number;
  rendered_count?: number;
  created_at: string;
}

export interface VideoStatus {
  video_id: string;
  status: string;
  error_message?: string;
  job_progress: {
    audio_extract?: number;
    transcribe?: number;
    analyze?: number;
  };
}

export interface ClipItem {
  id: string;
  video_id: string;
  title: string;
  start_time_seconds: number;
  end_time_seconds: number;
  duration_seconds: number;
  hook_score: number;
  virality_reason?: string;
  is_selected: boolean;
  narration_text?: string;
  narration_voice?: string;
  narration_audio_path?: string;
  created_at: string;
}

export interface RenderedShort {
  id: string;
  clip_id: string;
  video_id?: string;
  title?: string;
  output_filename: string;
  file_size_bytes: number;
  render_status: 'PENDING' | 'RENDERING' | 'COMPLETED' | 'FAILED';
  render_progress: number;
  is_drive_uploaded: boolean;
  download_url: string;
  created_at: string;
  gdrive?: {
    upload_status: 'QUEUED' | 'UPLOADING' | 'SUCCESS' | 'FAILED';
    gdrive_file_id?: string;
    gdrive_web_view_link?: string;
  };
}

export interface HeadSample {
  t: number;
  cx: number;
}

export interface CropKeyframe {
  t: number;
  x: number;
  head_cx?: number | null;
}

export interface ReframePreview {
  clip_start: number;
  clip_end: number;
  duration: number;
  src_width: number;
  src_height: number;
  crop_width: number;
  max_offset_x: number;
  deadzone: number;
  snap: boolean;
  detected: boolean;
  coverage: number;
  head_samples: HeadSample[];
  keyframes: CropKeyframe[];
}

export interface TTSItem {
  id: string;
  text: string;
  voice: string;
  audio_url: string;
  file_size_bytes: number;
  duration_seconds: number;
  created_at: string;
}

export interface VoiceItem {
  id: string;
  name: string;
  lang: string;
  gender: string;
}

export interface YouTubeInfo {
  id?: string;
  title: string;
  duration_seconds: number;
  thumbnail_url?: string;
  channel?: string;
  webpage_url: string;
  description?: string;
}

export interface GeneralSettingsUpdate {
  min_clip_seconds: number;
  max_clip_seconds: number;
  yt_quality: string;
}

export interface AITestResponse {
  ok: boolean;
  model?: string;
  message: string;
  error?: string;
}

export interface GDriveOAuthUrlResponse {
  auth_url: string;
  redirect_uri: string;
}

export interface BatchActionResponse {
  success_count: number;
  failed_count: number;
  message: string;
}

export interface SystemSettings {
  llm_base_url?: string;
  llm_model?: string;
  llm_configured: boolean;
  llm_connected?: boolean;
  llm_prompt?: string;
  gdrive_auth_type?: string;
  gdrive_folder_id?: string;
  gdrive_configured: boolean;
  gdrive_client_id?: string;
  gdrive_oauth_connected?: boolean;
  gdrive_redirect_uri?: string;
  min_clip_seconds?: number;
  max_clip_seconds?: number;
  yt_quality?: string;
  clip_view_mode?: 'grid' | 'list';
  shorts_view_mode?: 'grid' | 'list';
}

export interface HealthStatus {
  status: string;
  db: boolean;
  storage_writable: boolean;
  ffmpeg: string;
}

export type SubtitleMotionType = 'single_word_pop' | 'karaoke' | 'background_box' | 'typewriter' | 'slide_up';

export interface TextPreset {
  id: string;
  name: string;
  description?: string | null;
  crop_mode?: 'smart' | 'center' | 'manual';
  crop_offset_x?: number;
  smart_deadzone?: number;
  smart_pan_seconds?: number;
  font: string;
  font_size: number;
  primary_color: string;
  active_color: string;
  subtitle_position: 'bottom' | 'middle' | 'top' | 'custom' | string;
  margin_v?: number | null;
  outline_width: number;
  shadow_depth: number;
  is_uppercase: boolean;
  motion_type?: SubtitleMotionType;
  highlight_bg_color?: string;
  enable_keyword_color?: boolean;
  keyword_color?: string;
  enable_dynamic_scaling?: boolean;
  enable_emoji_injection?: boolean;
  glow_effect?: boolean;
  audio_track_id?: string | null;
  bgm_volume?: number;
  audio_mode?: AudioMode;
  use_voiceover?: boolean;
  narration_voice?: string;
  narration_style?: NarrationStyle;
  is_builtin: boolean;
  created_at: string;
}

export interface TextPresetPayload {
  name: string;
  description?: string | null;
  crop_mode?: 'smart' | 'center' | 'manual';
  crop_offset_x?: number;
  smart_deadzone?: number;
  smart_pan_seconds?: number;
  font: string;
  font_size: number;
  primary_color: string;
  active_color: string;
  subtitle_position: string;
  margin_v?: number | null;
  outline_width: number;
  shadow_depth: number;
  is_uppercase: boolean;
  motion_type?: SubtitleMotionType;
  highlight_bg_color?: string;
  enable_keyword_color?: boolean;
  keyword_color?: string;
  enable_dynamic_scaling?: boolean;
  enable_emoji_injection?: boolean;
  glow_effect?: boolean;
  audio_track_id?: string | null;
  bgm_volume?: number;
  audio_mode?: AudioMode;
  use_voiceover?: boolean;
  narration_voice?: string;
  narration_style?: NarrationStyle;
}

export interface AudioTrack {
  id: string;
  title: string;
  source_type: string;
  source_url?: string | null;
  duration_seconds: number;
  file_size_bytes: number;
  stream_url: string;
  created_at: string;
}

export interface NarrationResult {
  clip_id: string;
  narration_text: string;
  estimated_duration_seconds: number;
}

export interface SynthesizeResult {
  clip_id: string;
  audio_url: string;
  duration_seconds: number;
}

export type AudioMode = 'mix' | 'replace' | 'original';

export type NarrationStyle = 'hook_story' | 'summary' | 'educational';

