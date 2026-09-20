export interface VideoItem {
  id: string;
  original_name: string;
  status: 'DOWNLOADING' | 'UPLOADED' | 'EXTRACTING_AUDIO' | 'TRANSCRIBING' | 'ANALYZING' | 'READY' | 'FAILED';
  duration_seconds: number;
  file_size_bytes: number;
  language?: string;
  thumbnail_url: string;
  description?: string;
  video_type?: string;
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
    download?: number;
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
  composite_score?: number;
  speech_rate?: number;
  keyword_density?: number;
  face_coverage?: number;
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
  is_youtube_uploaded?: boolean;
  source_url?: string | null;
  source_title?: string | null;
  download_url: string;
  thumbnail_url?: string;
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
  description?: string;
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
  whisper_language?: string;
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
  llm_two_pass_enabled?: boolean;
  llm_chunk_strategy?: string;
  llm_vision_enabled?: boolean;
  llm_vision_model?: string;
  llm_vision_weight?: number;
  gdrive_auth_type?: string;
  gdrive_folder_id?: string;
  gdrive_configured: boolean;
  gdrive_client_id?: string;
  gdrive_oauth_connected?: boolean;
  gdrive_redirect_uri?: string;
  min_clip_seconds?: number;
  max_clip_seconds?: number;
  yt_quality?: string;
  whisper_language?: string;
  clip_view_mode?: 'grid' | 'list';
  shorts_view_mode?: 'grid' | 'list';
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface HealthStatus {
  status: string;
  db: boolean;
  storage_writable: boolean;
  ffmpeg: string;
}

export type SubtitleMotionType = 'single_word_pop' | 'karaoke' | 'background_box' | 'typewriter' | 'slide_up' | 'bounce_in' | 'zoom_flash' | 'glitch_reveal';
export type VideoFilter = 'none' | 'cinematic' | 'vivid' | 'warm' | 'cool' | 'drama' | 'vintage';
export type FramingLayout = 'single' | 'pip_full' | 'pip_center' | 'split_top_bottom' | 'split_bottom_top' | 'fit_16_9_center' | 'overlay_pip' | 'streamer_face_top' | 'streamer_face_bottom';
export type PersonShape = 'circle' | 'rounded' | 'rectangle';
export type ScreenMode = 'full' | 'center';

export interface TextPreset {
  id: string;
  name: string;
  description?: string | null;
  crop_mode?: 'smart' | 'center' | 'manual';
  crop_offset_x?: number;
  smart_deadzone?: number;
  smart_pan_seconds?: number;
  framing_layout?: FramingLayout;
  screen_mode?: ScreenMode;
  person_shape?: PersonShape;
  person_scale?: number;
  person_offset_x?: number;
  person_offset_y?: number;
  screen_offset_x?: number;
  screen_offset_y?: number;
  screen_scale?: number;
  screen_aspect?: '16:9' | '9:16' | string;
  video_filter?: VideoFilter | string;
  enable_intro_title?: boolean;
  intro_title_duration?: number;
  intro_title_style?: string;
  intro_title_tts?: boolean;
  intro_title_voice?: string;
  intro_title_pause?: boolean;
  enable_outro_cta?: boolean;
  outro_cta_text?: string;
  outro_cta_duration?: number;
  enable_lower_third?: boolean;
  lower_third_text?: string | null;
  sticker_path?: string | null;
  sticker_position?: string;
  sticker_scale?: number;
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
  enable_vocal_dynamics?: boolean;
  audio_track_id?: string | null;
  bgm_volume?: number;
  audio_mode?: AudioMode;
  use_voiceover?: boolean;
  narration_voice?: string;
  narration_style?: NarrationStyle;
  category?: string;
  thumbnail_preview?: string | null;
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
  framing_layout?: FramingLayout;
  screen_mode?: ScreenMode;
  person_shape?: PersonShape;
  person_scale?: number;
  person_offset_x?: number;
  person_offset_y?: number;
  screen_offset_x?: number;
  screen_offset_y?: number;
  screen_scale?: number;
  screen_aspect?: '16:9' | '9:16' | string;
  video_filter?: VideoFilter | string;
  enable_intro_title?: boolean;
  intro_title_duration?: number;
  intro_title_style?: string;
  intro_title_tts?: boolean;
  intro_title_voice?: string;
  intro_title_pause?: boolean;
  enable_outro_cta?: boolean;
  outro_cta_text?: string;
  outro_cta_duration?: number;
  enable_lower_third?: boolean;
  lower_third_text?: string | null;
  sticker_path?: string | null;
  sticker_position?: string;
  sticker_scale?: number;
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
  enable_vocal_dynamics?: boolean;
  audio_track_id?: string | null;
  bgm_volume?: number;
  audio_mode?: AudioMode;
  use_voiceover?: boolean;
  narration_voice?: string;
  narration_style?: NarrationStyle;
  category?: string;
  thumbnail_preview?: string | null;
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

export interface WahaStatus {
  enabled: boolean;
  api_url: string;
  session_name: string;
  session_status: 'STOPPED' | 'STARTING' | 'SCAN_QR_CODE' | 'SCAN_QR' | 'WORKING' | 'FAILED';
  qr_code?: string | null;
  sync_token: string;
  paired_chat_id?: string | null;
  paired_chat_name?: string | null;
  paired_chat_type?: 'direct' | 'group' | null;
  paired_at?: string | null;
}

export interface WahaConfig {
  api_url?: string;
  api_key?: string;
  session_name?: string;
  enabled?: boolean;
}

export interface PipelineRule {
  id: string;
  name?: string;
  context: string;
  preset_id: string;
}

export interface PipelineConfig {
  auto_clip_enabled: boolean;
  min_score: number;
  context_rules: PipelineRule[];
  default_preset_id?: string | null;
  auto_upload_youtube: boolean;
  auto_upload_gdrive: boolean;
  auto_notify_whatsapp: boolean;
  whatsapp_target_chat?: string | null;
  whatsapp_paired?: boolean;
  whatsapp_paired_chat_name?: string | null;
  youtube_connected?: boolean;
  gdrive_connected?: boolean;
}

export interface PipelineMatchTestRequest {
  title?: string;
  video_type?: string;
  description?: string;
  clip_title?: string;
}

export interface PipelineMatchTestResponse {
  matched: boolean;
  selected_preset_id?: string | null;
  selected_preset_name?: string | null;
  matched_rule?: PipelineRule | null;
  match_reason: string;
}

