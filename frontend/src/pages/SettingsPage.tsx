import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Cloud,
  CheckCircle2,
  AlertCircle,
  Activity,
  Save,
  Loader2,
  Key,
  FolderCheck,
  Sliders,
  Youtube,
  Clock,
  Wifi,
  WifiOff,
  RefreshCw,
  Copy,
  Check,
  ExternalLink,
  ShieldCheck,
  LogIn,
  MessageSquare,
  Smartphone,
  Mic,
  Send,
  QrCode,
  Unlink,
  Bot,
  Hash,
  Terminal,
  FileText,
  Trash2,
  Upload,
  ShieldAlert
} from 'lucide-react';
import { settingsApi, healthApi, wahaApi } from '../services/api';
import { HealthStatus, WahaStatus } from '../types';
import { useTheme } from '../hooks/useTheme';

type TabType = 'ai' | 'video' | 'gdrive' | 'youtube' | 'waha' | 'system';

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('ai');
  const { choice: themeChoice, setTheme } = useTheme();
  const [loading, setLoading] = useState(true);
  const [savingAI, setSavingAI] = useState(false);
  const [savingGDrive, setSavingGDrive] = useState(false);
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [testingGDrive, setTestingGDrive] = useState(false);
  const [testingAI, setTestingAI] = useState(false);
  const [refreshingHealth, setRefreshingHealth] = useState(false);
  const [connectingOAuth, setConnectingOAuth] = useState(false);
  const [exchangingCode, setExchangingCode] = useState(false);
  const [copiedRedirectUri, setCopiedRedirectUri] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);

  // WAHA State
  const [waha, setWaha] = useState<WahaStatus | null>(null);
  const [loadingWaha, setLoadingWaha] = useState(false);
  const [savingWaha, setSavingWaha] = useState(false);
  const [startingWaha, setStartingWaha] = useState(false);
  const [regeneratingToken, setRegeneratingToken] = useState(false);
  const [unpairingWaha, setUnpairingWaha] = useState(false);
  const [testingWahaMsg, setTestingWahaMsg] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);
  const [wahaApiUrl, setWahaApiUrl] = useState('http://localhost:3008');
  const [wahaSessionName, setWahaSessionName] = useState('default');
  const [wahaApiKey, setWahaApiKey] = useState('');
  const [wahaEnabled, setWahaEnabled] = useState(true);

  // General Form (Clip Durations & YouTube)
  const [minClipSeconds, setMinClipSeconds] = useState(10);
  const [maxClipSeconds, setMaxClipSeconds] = useState(60);
  const [ytQuality, setYtQuality] = useState('1080p');
  const [whisperLang, setWhisperLang] = useState('auto');

  // YouTube Cookies & Anti-Bot State
  const [ytClientId, setYtClientId] = useState('');
  const [ytClientSecret, setYtClientSecret] = useState('');
  const [ytConnected, setYtConnected] = useState(false);
  const [ytAutoUpload, setYtAutoUpload] = useState(false);
  const [ytDefaultPrivacy, setYtDefaultPrivacy] = useState('public');
  const [ytChannel, setYtChannel] = useState<{ channel_name?: string; subscriber_count?: string } | null>(null);
  const [savingYt, setSavingYt] = useState(false);
  const [testingYt, setTestingYt] = useState(false);
  const [connectingYt, setConnectingYt] = useState(false);
  const [ytCookiesStatus, setYtCookiesStatus] = useState<{ has_cookies: boolean; file_path?: string; file_size_bytes?: number; line_count?: number } | null>(null);
  const [ytCookiesInput, setYtCookiesInput] = useState('');
  const [savingCookies, setSavingCookies] = useState(false);
  const [deletingCookies, setDeletingCookies] = useState(false);
  const [showCookiesInput, setShowCookiesInput] = useState(false);

  // LLM Form
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('gpt-4o-mini');
  const [temperature, setTemperature] = useState(0.4);
  const [prompt, setPrompt] = useState('');
  const [twoPassEnabled, setTwoPassEnabled] = useState(false);
  const [chunkStrategy, setChunkStrategy] = useState('auto');
  const [visionEnabled, setVisionEnabled] = useState(false);
  const [visionModel, setVisionModel] = useState('');
  const [visionWeight, setVisionWeight] = useState(0.3);
  const [llmConnected, setLlmConnected] = useState(false);
  const [aiTestResult, setAiTestResult] = useState<{ ok: boolean; model?: string; message: string; error?: string } | null>(null);

  // GDrive Form
  const [authType, setAuthType] = useState<'OAUTH2' | 'SERVICE_ACCOUNT'>('OAUTH2');
  const [folderId, setFolderId] = useState('');
  const [credentialsJson, setCredentialsJson] = useState('');
  const [clientId, setClientId] = useState('');
  const [oauthConnected, setOauthConnected] = useState(false);
  const [authCode, setAuthCode] = useState('');
  const [showManualCode, setShowManualCode] = useState(false);
  const [gdriveTestResult, setGdriveTestResult] = useState<{ ok: boolean; folder_name?: string; error?: string } | null>(null);

  const [message, setMessage] = useState<string | null>(null);

  const redirectUri = "http://localhost:8000/api/settings/gdrive/oauth/callback";

  useEffect(() => {
    loadSettings();

    // Listen for OAuth success message from callback popup window
    const handleOAuthMessage = (event: MessageEvent) => {
      if (event.data?.type === 'gdrive_oauth_success') {
        setOauthConnected(true);
        setMessage('Akun Google berhasil diotorisasi via OAuth 2.0!');
        loadSettings();
        setTimeout(() => setMessage(null), 4500);
      }
      if (event.data?.type === 'youtube_oauth_success') {
        setYtConnected(true);
        setMessage('Akun YouTube berhasil diotorisasi!');
        loadSettings();
        setTimeout(() => setMessage(null), 4500);
      }
    };
    window.addEventListener('message', handleOAuthMessage);
    return () => window.removeEventListener('message', handleOAuthMessage);
  }, []);

  // Auto-polling for WhatsApp (WAHA) status & live QR code
  React.useEffect(() => {
    if (activeTab !== 'waha') return;

    const intervalTime = (waha?.session_status === 'SCAN_QR_CODE' || waha?.session_status === 'STARTING') ? 3000 : 8000;
    const timer = setInterval(async () => {
      try {
        const w = await wahaApi.getStatus();
        setWaha(w);
      } catch (e) {
        // silent catch on polling
      }
    }, intervalTime);

    return () => clearInterval(timer);
  }, [activeTab, waha?.session_status]);

  const loadSettings = async () => {
    try {
      const [s, h, w] = await Promise.all([
        settingsApi.get(),
        healthApi.check(),
        wahaApi.getStatus().catch(() => null)
      ]);
      setHealth(h);
      if (w) {
        setWaha(w);
        setWahaApiUrl(w.api_url || 'http://localhost:3008');
        setWahaSessionName(w.session_name || 'default');
        setWahaEnabled(w.enabled);
      }
      if (s.llm_base_url) setBaseUrl(s.llm_base_url);
      if (s.llm_model) setModelName(s.llm_model);
      if (s.llm_prompt) setPrompt(s.llm_prompt);
      setTwoPassEnabled(Boolean(s.llm_two_pass_enabled));
      if (s.llm_chunk_strategy) setChunkStrategy(s.llm_chunk_strategy);
      setVisionEnabled(Boolean(s.llm_vision_enabled));
      if (s.llm_vision_model) setVisionModel(s.llm_vision_model);
      if (s.llm_vision_weight !== undefined && s.llm_vision_weight !== null) setVisionWeight(Number(s.llm_vision_weight));
      setLlmConnected(Boolean(s.llm_connected));

      if (s.gdrive_auth_type === 'SERVICE_ACCOUNT') {
        setAuthType('SERVICE_ACCOUNT');
      } else {
        setAuthType('OAUTH2');
      }
      if (s.gdrive_folder_id) setFolderId(s.gdrive_folder_id);
      if (s.gdrive_client_id) setClientId(s.gdrive_client_id);
      setOauthConnected(Boolean(s.gdrive_oauth_connected));

      if (s.min_clip_seconds !== undefined) setMinClipSeconds(s.min_clip_seconds);
      if (s.max_clip_seconds !== undefined) setMaxClipSeconds(s.max_clip_seconds);
      if (s.yt_quality) setYtQuality(s.yt_quality);
      if (s.whisper_language) setWhisperLang(s.whisper_language);

      try {
        const c = await settingsApi.getYouTubeCookiesStatus();
        setYtCookiesStatus(c);
      } catch (err) {
        // silent
      }
      try {
        const ytCfg = await settingsApi.getYouTubeConfig();
        if (ytCfg.client_id) setYtClientId(ytCfg.client_id);
        setYtAutoUpload(Boolean(ytCfg.auto_upload));
        if (ytCfg.default_privacy) setYtDefaultPrivacy(ytCfg.default_privacy);
        setYtConnected(Boolean(ytCfg.connected));
        if (ytCfg.connected) {
          setYtChannel({ channel_name: ytCfg.channel_name, subscriber_count: undefined });
        }
      } catch (err) {
        try {
          const ch = await settingsApi.getYouTubeChannel();
          setYtConnected(Boolean(ch.ok));
          if (ch.ok) setYtChannel({ channel_name: ch.channel_name, subscriber_count: ch.subscriber_count });
          else setYtChannel(null);
        } catch {
          setYtConnected(false);
        }
      }
    } catch (e) {
      console.error('Failed to load settings', e);
    } finally {
      setLoading(false);
    }
  };

  const loadCookiesStatus = async () => {
    try {
      const c = await settingsApi.getYouTubeCookiesStatus();
      setYtCookiesStatus(c);
    } catch (e) {
      console.error('Failed to load cookies status', e);
    }
  };

  const handleSaveCookies = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ytCookiesInput.trim()) return;
    setSavingCookies(true);
    try {
      const res = await settingsApi.saveYouTubeCookies(ytCookiesInput);
      setMessage(res.message);
      setYtCookiesInput('');
      setShowCookiesInput(false);
      await loadCookiesStatus();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal menyimpan cookies: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingCookies(false);
    }
  };

  const handleDeleteCookies = async () => {
    if (!window.confirm('Hapus file cookies YouTube?')) return;
    setDeletingCookies(true);
    try {
      const res = await settingsApi.deleteYouTubeCookies();
      setMessage(res.message);
      await loadCookiesStatus();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal menghapus cookies: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeletingCookies(false);
    }
  };

  const refreshWaha = async () => {
    setLoadingWaha(true);
    try {
      const w = await wahaApi.getStatus();
      setWaha(w);
    } catch (e) {
      console.error('Failed to refresh WAHA status', e);
    } finally {
      setLoadingWaha(false);
    }
  };

  const handleSaveWahaConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingWaha(true);
    try {
      const res = await wahaApi.updateConfig({
        api_url: wahaApiUrl.trim(),
        session_name: wahaSessionName.trim(),
        api_key: wahaApiKey.trim() || undefined,
        enabled: wahaEnabled,
      });
      setMessage(res.message || 'Konfigurasi WhatsApp (WAHA) berhasil disimpan!');
      await refreshWaha();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal menyimpan konfigurasi WAHA: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingWaha(false);
    }
  };

  const handleStartWahaSession = async () => {
    setStartingWaha(true);
    try {
      const res = await wahaApi.startSession();
      setMessage(res.message || 'Sesi WAHA dimulai. Silakan scan QR code.');
      await refreshWaha();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal memulai sesi WAHA: ' + (err.response?.data?.detail || err.message));
    } finally {
      setStartingWaha(false);
    }
  };

  const handleLogoutWahaSession = async () => {
    if (!window.confirm('Logout dari sesi WhatsApp WAHA?')) return;
    try {
      await wahaApi.logoutSession();
      setMessage('Sesi WhatsApp berhasil di-logout.');
      await refreshWaha();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal logout sesi WAHA: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleRegenerateWahaToken = async () => {
    if (!window.confirm('Buat token pairing baru? Token lama tidak akan berlaku lagi.')) return;
    setRegeneratingToken(true);
    try {
      const res = await wahaApi.regenerateToken();
      if (waha) {
        setWaha({ ...waha, sync_token: res.token });
      }
      setMessage('Token pairing baru berhasil dibuat!');
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal meregenerasi token: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRegeneratingToken(false);
    }
  };

  const handleUnpairWaha = async () => {
    if (!window.confirm('Putuskan tautan akun/grup WhatsApp ini dari EmberShorts?')) return;
    setUnpairingWaha(true);
    try {
      await wahaApi.unpair();
      await refreshWaha();
      setMessage('Tautan WhatsApp berhasil diputuskan.');
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal memutuskan tautan: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUnpairingWaha(false);
    }
  };

  const handleSendWahaTestMessage = async () => {
    setTestingWahaMsg(true);
    try {
      const res = await wahaApi.sendTestMessage();
      setMessage(res.message || 'Pesan uji coba berhasil dikirim!');
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal mengirim pesan uji coba: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTestingWahaMsg(false);
    }
  };

  const handleCopyPairingToken = () => {
    if (!waha?.sync_token) return;
    navigator.clipboard.writeText(`connect ${waha.sync_token}`);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2500);
  };

  // Client-side JSON format detection
  const detectedJson = React.useMemo(() => {
    if (!credentialsJson.trim()) return null;
    try {
      const data = JSON.parse(credentialsJson.trim());
      if (data.web) {
        return {
          type: 'OAUTH2',
          label: 'Google OAuth 2.0 Web Client',
          clientId: data.web.client_id,
          projectId: data.web.project_id,
        };
      }
      if (data.installed) {
        return {
          type: 'OAUTH2',
          label: 'Google OAuth 2.0 Desktop Client',
          clientId: data.installed.client_id,
          projectId: data.installed.project_id,
        };
      }
      if (data.type === 'service_account') {
        return {
          type: 'SERVICE_ACCOUNT',
          label: 'Google Service Account Key',
          clientEmail: data.client_email,
          projectId: data.project_id,
        };
      }
      if (data.client_id && data.client_secret) {
        return {
          type: 'OAUTH2',
          label: 'OAuth 2.0 Client Credentials',
          clientId: data.client_id,
          projectId: data.project_id,
        };
      }
    } catch {}
    return { type: 'INVALID', label: 'Format JSON tidak valid atau belum lengkap' };
  }, [credentialsJson]);

  // Auto-switch authType when user pastes recognized JSON
  useEffect(() => {
    if (detectedJson?.type === 'OAUTH2' && authType !== 'OAUTH2') {
      setAuthType('OAUTH2');
    } else if (detectedJson?.type === 'SERVICE_ACCOUNT' && authType !== 'SERVICE_ACCOUNT') {
      setAuthType('SERVICE_ACCOUNT');
    }
  }, [detectedJson]);

  const handleRefreshHealth = async () => {
    setRefreshingHealth(true);
    try {
      const h = await healthApi.check();
      setHealth(h);
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshingHealth(false);
    }
  };

  const handleSaveGeneral = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingGeneral(true);
    try {
      await settingsApi.updateGeneral({
        min_clip_seconds: Number(minClipSeconds),
        max_clip_seconds: Number(maxClipSeconds),
        yt_quality: ytQuality,
        whisper_language: whisperLang,
      });
      setMessage('Pengaturan durasi klip & YouTube berhasil disimpan!');
      setTimeout(() => setMessage(null), 3500);
    } catch (err: any) {
      alert('Gagal menyimpan pengaturan umum.');
    } finally {
      setSavingGeneral(false);
    }
  };

  const handleSaveAI = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingAI(true);
    try {
      const res: any = await settingsApi.updateAI({
        base_url: baseUrl,
        api_key: apiKey || undefined,
        model_name: modelName,
        temperature,
        prompt: prompt || undefined,
        two_pass_enabled: twoPassEnabled,
        chunk_strategy: chunkStrategy,
        vision_enabled: visionEnabled,
        vision_model: visionModel.trim() || undefined,
        vision_weight: visionWeight,
      });
      if (res?.connected !== undefined) {
        setLlmConnected(Boolean(res.connected));
      }
      setMessage(res?.message || 'Konfigurasi AI berhasil disimpan ke database!');
      await loadSettings();
      setTimeout(() => setMessage(null), 5000);
    } catch (err: any) {
      alert('Gagal menyimpan konfigurasi AI.');
    } finally {
      setSavingAI(false);
    }
  };

  const handleTestAI = async () => {
    setTestingAI(true);
    setAiTestResult(null);
    try {
      const res = await settingsApi.testAI({
        base_url: baseUrl,
        api_key: apiKey || undefined,
        model_name: modelName,
      });
      setAiTestResult(res);
      setLlmConnected(res.ok);
      if (res.ok) {
        setMessage(`Koneksi AI berhasil! Model "${res.model}" terhubung dan fitur kurasi aktif.`);
        setTimeout(() => setMessage(null), 4000);
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Koneksi ke AI gagal';
      setAiTestResult({ ok: false, message: 'Gagal menghubungkan ke AI', error: errMsg });
      setLlmConnected(false);
    } finally {
      setTestingAI(false);
    }
  };

  const handleSaveGDrive = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingGDrive(true);
    try {
      const res = await settingsApi.updateGDrive({
        auth_type: authType,
        target_folder_id: folderId.trim(),
        credentials_json: credentialsJson.trim() || undefined,
      });
      setMessage(res.message || 'Konfigurasi Google Drive berhasil disimpan!');
      await loadSettings();
      setTimeout(() => setMessage(null), 4500);
    } catch (err: any) {
      alert('Gagal menyimpan konfigurasi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingGDrive(false);
    }
  };

  const handleConnectGoogle = async () => {
    setConnectingOAuth(true);
    try {
      // If user pasted credentials, save them first before initiating OAuth flow
      if (credentialsJson.trim()) {
        await settingsApi.updateGDrive({
          auth_type: 'OAUTH2',
          target_folder_id: folderId.trim() || 'pending',
          credentials_json: credentialsJson.trim(),
        });
      }

      const res = await settingsApi.getGDriveOAuthUrl(redirectUri);
      const popup = window.open(
        res.auth_url,
        'GoogleAuthPopup',
        'width=600,height=700,status=no,toolbar=no,menubar=no'
      );
      if (!popup) {
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      alert('Gagal memulai otorisasi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setConnectingOAuth(false);
    }
  };

  const handleExchangeManualCode = async () => {
    if (!authCode.trim()) return;
    setExchangingCode(true);
    try {
      await settingsApi.exchangeGDriveOAuthCode(authCode.trim(), redirectUri);
      setMessage('Otorisasi kode berhasil! Akun Google telah terhubung.');
      setOauthConnected(true);
      setAuthCode('');
      setShowManualCode(false);
      await loadSettings();
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal menukar kode otorisasi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setExchangingCode(false);
    }
  };

  const handleCopyRedirectUri = () => {
    navigator.clipboard.writeText(redirectUri);
    setCopiedRedirectUri(true);
    setTimeout(() => setCopiedRedirectUri(false), 2500);
  };

  const handleTestGDrive = async () => {
    setTestingGDrive(true);
    setGdriveTestResult(null);
    try {
      const res = await settingsApi.testGDrive();
      setGdriveTestResult(res);
    } catch (err: any) {
      setGdriveTestResult({ ok: false, error: err.message });
    } finally {
      setTestingGDrive(false);
    }
  };

  const handleSaveYouTube = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingYt(true);
    try {
      const res = await settingsApi.saveYouTubeConfig({
        client_id: ytClientId.trim() || undefined,
        client_secret: ytClientSecret.trim() || undefined,
        auto_upload: ytAutoUpload,
        default_privacy: ytDefaultPrivacy,
        made_for_kids: false,
      });
      setMessage(res?.message || 'Konfigurasi YouTube disimpan.');
      setYtClientSecret('');
      setTimeout(() => setMessage(null), 4000);
    } catch (err: any) {
      alert('Gagal menyimpan konfigurasi YouTube: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingYt(false);
    }
  };

  const handleConnectYouTube = async () => {
    setConnectingYt(true);
    try {
      if (ytClientId.trim() || ytClientSecret.trim()) {
        await settingsApi.saveYouTubeConfig({
          client_id: ytClientId.trim() || undefined,
          client_secret: ytClientSecret.trim() || undefined,
        });
        setYtClientSecret('');
      }
      const res = await settingsApi.getYouTubeOAuthUrl();
      const popup = window.open(res.auth_url, 'YouTubeAuthPopup', 'width=600,height=700,status=no,toolbar=no,menubar=no');
      if (!popup) window.location.href = res.auth_url;
    } catch (err: any) {
      alert('Gagal memulai otorisasi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setConnectingYt(false);
    }
  };

  const handleTestYouTube = async () => {
    setTestingYt(true);
    try {
      const res = await settingsApi.testYouTube();
      setYtConnected(res.ok);
      if (res.ok) {
        setYtChannel({ channel_name: res.channel_name, subscriber_count: res.subscriber_count });
        setMessage(`YouTube terhubung: ${res.channel_name || 'channel'}!`);
        setTimeout(() => setMessage(null), 4000);
      } else {
        alert('Tes gagal: ' + (res.error || 'unknown'));
      }
    } catch (err: any) {
      alert('Tes gagal: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTestingYt(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="font-display font-bold text-3xl text-ember-text-primary">Pengaturan Sistem</h2>
        <p className="text-ember-text-secondary text-sm mt-1">
          Kelola koneksi AI LLM, durasi klip & downloader YouTube, ekspor Google Drive, serta status engine lokal.
        </p>
      </div>

      {message && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-xl flex items-center space-x-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex border-b border-ember-border space-x-1 sm:space-x-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('ai')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'ai'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Koneksi AI (LLM)</span>
          <span
            className={`w-2 h-2 rounded-full ${
              llmConnected ? 'bg-emerald-500 ring-2 ring-emerald-200' : 'bg-red-400'
            }`}
          />
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('video')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'video'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Durasi Klip & YouTube</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('gdrive')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'gdrive'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <Cloud className="w-4 h-4" />
          <span>Google Drive Export</span>
          <span
            className={`w-2 h-2 rounded-full ${
              oauthConnected ? 'bg-emerald-500' : 'bg-[#A8A29E]'
            }`}
          />
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('youtube')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'youtube'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <Youtube className="w-4 h-4" />
          <span>YouTube Upload</span>
          <span
            className={`w-2 h-2 rounded-full ${
              ytConnected ? 'bg-emerald-500' : 'bg-[#A8A29E]'
            }`}
          />
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('waha')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'waha'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          <span>WhatsApp Bot (WAHA)</span>
          <span
            className={`w-2 h-2 rounded-full ${
              waha?.paired_chat_id ? 'bg-emerald-500 ring-2 ring-emerald-200' : (waha?.session_status === 'WORKING' ? 'bg-amber-500' : 'bg-[#A8A29E]')
            }`}
          />
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('system')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'system'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-ember-neutral hover:text-ember-text-primary hover:border-[#A8A29E]'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Status Mesin Lokal</span>
        </button>
      </div>

      {/* TAB 1: KONEKSI AI */}
      {activeTab === 'ai' && (
        <div className="space-y-6">
          <div
            className={`p-5 rounded-2xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
              llmConnected
                ? 'bg-emerald-50 border-emerald-200'
                : 'bg-amber-50 border-amber-200'
            }`}
          >
            <div className="flex items-start space-x-3">
              {llmConnected ? (
                <Wifi className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <WifiOff className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
              )}
              <div>
                <h4 className="font-semibold text-sm text-ember-text-primary flex items-center space-x-2">
                  <span>Status AI:</span>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                      llmConnected
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {llmConnected ? '🟢 AI Terhubung (Aktif)' : '🔴 Belum Terhubung'}
                  </span>
                </h4>
                <p className="text-xs text-ember-text-secondary mt-1">
                  {llmConnected
                    ? 'AI siap menganalisis Konteks Besar (transkrip penuh, judul, deskripsi) & Konteks Kecil (segmen waktu) untuk menemukan klip viral.'
                    : 'Fitur AI dinonaktifkan sementara. Klik "Uji Koneksi AI" di bawah ini untuk memverifikasi koneksi dan mengaktifkan fitur kurasi.'}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleTestAI}
              disabled={testingAI}
              className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition-all shadow-sm flex items-center space-x-2 shrink-0 ${
                llmConnected
                  ? 'bg-white border border-ember-border text-ember-text-primary hover:bg-ember-surface'
                  : 'bg-[#C2410C] hover:bg-[#9A3412] text-white'
              }`}
            >
              {testingAI ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              <span>{testingAI ? 'Menguji Koneksi...' : 'Uji Koneksi AI'}</span>
            </button>
          </div>

          {aiTestResult && (
            <div
              className={`p-4 rounded-xl text-xs border ${
                aiTestResult.ok
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-red-50 border-red-200 text-red-800'
              }`}
            >
              {aiTestResult.ok ? (
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>
                    Koneksi Berhasil! Terhubung ke model: <strong>{aiTestResult.model}</strong>. Fitur kurasi otomatis siap digunakan.
                  </span>
                </div>
              ) : (
                <div className="flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Koneksi Gagal: </span>
                    <span>{aiTestResult.error || aiTestResult.message}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* AI Settings Form */}
          <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-[#C2410C]" />
                <h3 className="font-semibold text-base text-ember-text-primary">
                  Konfigurasi LLM (OpenAI / Ollama / LM Studio)
                </h3>
              </div>
              <span className="text-[11px] text-ember-neutral">
                Mendukung OpenAI API & Penyedia Lokal Sesuai Standar OpenAI
              </span>
            </div>

            <form onSubmit={handleSaveAI} className="space-y-4 text-left">
              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  OpenAI-Compatible Base URL
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1 atau https://api.openai.com/v1"
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-ember-neutral mt-1">
                  Contoh: <code>http://localhost:11434/v1</code> (Ollama), <code>http://localhost:1234/v1</code> (LM Studio), atau <code>https://api.openai.com/v1</code>.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  API Key (Opsional untuk LLM Lokal)
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-... (Disimpan terenkripsi)"
                    className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                  />
                  <Key className="w-3.5 h-3.5 text-[#A8A29E] absolute right-3 top-3 pointer-events-none" />
                </div>
                <p className="text-[11px] text-ember-neutral mt-1">
                  Kosongkan jika menggunakan Ollama atau server lokal tanpa otentikasi.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                    Nama Model
                  </label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder="gpt-4o-mini, llama3.1, qwen2.5..."
                    className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                    Temperature ({temperature})
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-[#C2410C] cursor-pointer mt-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  System Prompt Kustom (Konteks Besar & Konteks Kecil)
                </label>
                <textarea
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Kosongkan untuk menggunakan prompt standar AutoShorts (Konteks Besar transkrip + judul + deskripsi dan Konteks Kecil segmen durasi)..."
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs text-ember-text-primary focus:border-[#C2410C] outline-none resize-none"
                />
                <p className="text-[11px] text-ember-neutral mt-1">
                  Secara default, AI memadukan <strong>Konteks Besar</strong> (seluruh transkrip, judul, & deskripsi) untuk menolak basa-basi/sponsor, serta <strong>Konteks Kecil</strong> (potongan timestamp) untuk memotong bagian paling viral.
                </p>
              </div>

              <label className="flex items-start justify-between gap-3 p-3 bg-ember-surface border border-[#E7E5E4] rounded-xl cursor-pointer">
                <span>
                  <span className="block text-xs font-bold text-ember-text-primary">Two-Pass Analysis (lebih akurat, 2x request)</span>
                  <span className="block text-[11px] text-ember-neutral mt-0.5">
                    Pass 1 pahami tema & saring noise (sponsor/basa-basi) jadi editorial brief; Pass 2 pilih klip berdasar brief. Disarankan untuk model kecil/Ollama lokal.
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={twoPassEnabled}
                  onChange={(e) => setTwoPassEnabled(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0"
                />
              </label>

              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  Strategi Transkrip (video panjang)
                </label>
                <select
                  value={chunkStrategy}
                  onChange={(e) => setChunkStrategy(e.target.value)}
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs text-ember-text-primary focus:border-[#C2410C] outline-none"
                >
                  <option value="auto">Auto (single &lt; 30 mnt, chunked di atasnya)</option>
                  <option value="single_pass">Single-pass selalu</option>
                  <option value="chunked">Chunked selalu</option>
                </select>
                <p className="text-[11px] text-ember-neutral mt-1">
                  Mode chunked memecah transkrip per ±20 menit agar bagian tengah video panjang tak terbuang.
                </p>
              </div>

              <label className="flex items-start justify-between gap-3 p-3 bg-ember-surface border border-ember-border rounded-xl cursor-pointer">
                <span>
                  <span className="block text-xs font-bold text-ember-text-primary">Vision-aware clipping (eksperimental)</span>
                  <span className="block text-[11px] text-ember-neutral mt-0.5">
                    Analisis frame visual (ekspresi, gestur, slide) untuk menaikkan skor momen visual. Butuh model vision. Gagal → otomatis text-only.
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={visionEnabled}
                  onChange={(e) => setVisionEnabled(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-[#C2410C] cursor-pointer shrink-0"
                />
              </label>
              {visionEnabled && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                      Model Vision (kosongkan = ikut model teks)
                    </label>
                    <input
                      type="text"
                      value={visionModel}
                      onChange={(e) => setVisionModel(e.target.value)}
                      placeholder="gpt-4o, qwen2-vl..."
                      className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                      Bobot Visual ({visionWeight.toFixed(2)})
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={visionWeight}
                      onChange={(e) => setVisionWeight(parseFloat(e.target.value))}
                      className="w-full accent-[#C2410C] cursor-pointer mt-2"
                    />
                  </div>
                </>
              )}

              <div className="pt-2 flex items-center justify-between">
                <p className="text-[11px] text-amber-700">
                  ⚠️ Perubahan konfigurasi akan menuntut pengujian koneksi ulang.
                </p>
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={handleTestAI}
                    disabled={testingAI}
                    className="px-4 py-2 bg-white hover:bg-ember-surface border border-ember-border text-ember-text-primary text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5"
                  >
                    {testingAI ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />}
                    <span>Uji Koneksi AI</span>
                  </button>

                  <button
                    type="submit"
                    disabled={savingAI}
                    className="px-5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all shadow-sm flex items-center space-x-1.5"
                  >
                    {savingAI ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>Simpan Pengaturan AI</span>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TAB 2: DURASI & YOUTUBE */}
      {activeTab === 'video' && (
        <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center space-x-2 pb-3 border-b border-[#F5F5F4]">
            <Sliders className="w-5 h-5 text-[#C2410C]" />
            <h3 className="font-semibold text-base text-ember-text-primary">
              Pengaturan Durasi Klip & YouTube Downloader
            </h3>
          </div>

          <form onSubmit={handleSaveGeneral} className="space-y-4 text-left">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Durasi Klip Minimal (Detik)</span>
                </label>
                <input
                  type="number"
                  min="5"
                  max="180"
                  value={minClipSeconds}
                  onChange={(e) => setMinClipSeconds(parseInt(e.target.value) || 5)}
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-sm font-semibold text-ember-text-primary focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-ember-neutral mt-1">
                  Batas durasi minimal untuk klip yang diidentifikasi oleh AI (default: 10 detik).
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Durasi Klip Maksimal (Detik)</span>
                </label>
                <input
                  type="number"
                  min="10"
                  max="300"
                  value={maxClipSeconds}
                  onChange={(e) => setMaxClipSeconds(parseInt(e.target.value) || 60)}
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-sm font-semibold text-ember-text-primary focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-ember-neutral mt-1">
                  Batas durasi maksimal klip untuk YouTube Shorts / TikTok (default: 60 detik).
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                <Youtube className="w-3.5 h-3.5 text-red-600" />
                <span>Kualitas Unduhan YouTube Default</span>
              </label>
              <select
                value={ytQuality}
                onChange={(e) => setYtQuality(e.target.value)}
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-sm font-semibold text-ember-text-primary focus:border-[#C2410C] outline-none"
              >
                <option value="1080p">1080p Full HD (Disarankan jika tersedia)</option>
                <option value="720p">720p HD (Unduh lebih cepat)</option>
                <option value="best">Kualitas Maksimal Tersedia (Best Available)</option>
              </select>
              <p className="text-[11px] text-ember-neutral mt-1">
                Kualitas video standar saat menempelkan link YouTube ke dalam sistem.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                <Mic className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Bahasa Transkripsi (Whisper)</span>
              </label>
              <select
                value={whisperLang}
                onChange={(e) => setWhisperLang(e.target.value)}
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-sm font-semibold text-ember-text-primary focus:border-[#C2410C] outline-none"
              >
                <option value="auto">🌐 Otomatis (deteksi per file)</option>
                <option value="id">🇮🇩 Indonesia</option>
                <option value="en">🇬🇧 Inggris</option>
                <option value="ms">🇲🇾 Melayu</option>
                <option value="zh">🇨🇳 Mandarin</option>
                <option value="ja">🇯🇵 Jepang</option>
                <option value="ko">🇰🇷 Korea</option>
                <option value="ar">🇸🇦 Arab</option>
                <option value="hi">🇮🇳 Hindi</option>
                <option value="es">🇪🇸 Spanyol</option>
              </select>
              <p className="text-[11px] text-ember-neutral mt-1">
                Paksa bahasa bila auto-detect salah (mis. konten campur ID–EN). Berlaku untuk transkripsi berikutnya; terlihat di badge bahasa pada editor subtitle.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                disabled={savingGeneral}
                className="px-5 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all shadow-sm flex items-center space-x-1.5"
              >
                {savingGeneral ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Simpan Durasi & YouTube</span>
              </button>
            </div>
          </form>

          {/* YouTube Anti-Bot Protection & Cookies */}
          <div className="pt-6 border-t border-[#F5F5F4] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <h4 className="text-sm font-bold text-ember-text-primary">Proteksi Anti-Bot YouTube & Cookies</h4>
              </div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                ytCookiesStatus?.has_cookies ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {ytCookiesStatus?.has_cookies ? '🍪 Cookies Aktif' : '🤖 Anti-Bot Player Spoofing Aktif'}
              </span>
            </div>

            <div className="p-4 bg-ember-background border border-[#E7E5E4] rounded-xl space-y-3">
              <div className="flex items-start space-x-3">
                <div className="p-2 bg-white rounded-lg border border-ember-border shrink-0">
                  <Youtube className="w-5 h-5 text-red-600" />
                </div>
                <div className="text-xs text-ember-text-secondary space-y-1">
                  <p className="font-semibold text-ember-text-primary">
                    Bypass Otomatis "Sign in to confirm you're not a bot"
                  </p>
                  <p>
                    Sistem otomatis menggunakan multi-client spoofing (Android, iOS, Mobile Web) saat mengekstrak video YouTube tanpa perlu login.
                  </p>
                  <p className="text-[11px] text-ember-neutral">
                    Jika video YouTube memiliki batasan umur (Age-Restricted) atau akun pribadi, Anda dapat menempelkan file <code className="bg-ember-surface-raised px-1 py-0.5 rounded text-ember-text-primary">cookies.txt</code> Netscape di bawah ini.
                  </p>
                </div>
              </div>

              {ytCookiesStatus?.has_cookies ? (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span className="text-xs font-semibold text-emerald-900">
                      File cookies terpasang ({ytCookiesStatus.line_count || 0} baris cookie terdeteksi)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleDeleteCookies}
                    disabled={deletingCookies}
                    className="px-3 py-1.5 bg-white border border-red-200 text-red-600 hover:bg-red-50 text-xs font-semibold rounded-lg transition-all flex items-center space-x-1"
                  >
                    {deletingCookies ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                    <span>Hapus Cookies</span>
                  </button>
                </div>
              ) : null}

              <div>
                <button
                  type="button"
                  onClick={() => setShowCookiesInput(!showCookiesInput)}
                  className="text-xs font-semibold text-[#C2410C] hover:underline flex items-center space-x-1"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>{showCookiesInput ? 'Sembunyikan Form Cookies' : '+ Tempel / Perbarui cookies.txt YouTube'}</span>
                </button>

                {showCookiesInput && (
                  <form onSubmit={handleSaveCookies} className="mt-3 space-y-3">
                    <textarea
                      value={ytCookiesInput}
                      onChange={(e) => setYtCookiesInput(e.target.value)}
                      placeholder="# Netscape HTTP Cookie File&#10;.youtube.com  TRUE  /  TRUE  1799999999  VISITOR_INFO1_LIVE  ..."
                      rows={5}
                      className="w-full px-3 py-2 bg-white border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                    />
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-ember-neutral">
                        Gunakan ekstensi browser seperti "Get cookies.txt LOCALLY" untuk mengekspor cookie YouTube Anda.
                      </span>
                      <button
                        type="submit"
                        disabled={savingCookies || !ytCookiesInput.trim()}
                        className="px-4 py-2 bg-[#1C1917] hover:bg-[#292524] disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5"
                      >
                        {savingCookies ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        <span>Simpan Cookies</span>
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: GDRIVE EXPORT */}
      {activeTab === 'gdrive' && (
        <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
            <div className="flex items-center space-x-2">
              <Cloud className="w-5 h-5 text-[#C2410C]" />
              <h3 className="font-semibold text-base text-ember-text-primary">Google Drive Export Configuration</h3>
            </div>
            <span className="text-[11px] text-ember-neutral">
              Mendukung OAuth 2.0 Web Client & Service Account
            </span>
          </div>

          {/* Auth Method Selector */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              onClick={() => setAuthType('OAUTH2')}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                authType === 'OAUTH2'
                  ? 'bg-orange-50/60 border-[#C2410C] ring-1 ring-[#C2410C]'
                  : 'bg-ember-surface border-[#E7E5E4] hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ember-text-primary flex items-center space-x-1.5">
                  <LogIn className="w-4 h-4 text-[#C2410C]" />
                  <span>OAuth 2.0 Web Client (Disarankan)</span>
                </span>
                <input
                  type="radio"
                  name="authType"
                  checked={authType === 'OAUTH2'}
                  onChange={() => setAuthType('OAUTH2')}
                  className="accent-[#C2410C]"
                />
              </div>
              <p className="text-[11px] text-ember-neutral mt-1.5">
                Sesuai berkas JSON dari Google Cloud Console Anda. Cukup simpan JSON lalu hubungkan akun dengan sekali klik.
              </p>
            </div>

            <div
              onClick={() => setAuthType('SERVICE_ACCOUNT')}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                authType === 'SERVICE_ACCOUNT'
                  ? 'bg-orange-50/60 border-[#C2410C] ring-1 ring-[#C2410C]'
                  : 'bg-ember-surface border-[#E7E5E4] hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ember-text-primary flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#C2410C]" />
                  <span>Service Account Key</span>
                </span>
                <input
                  type="radio"
                  name="authType"
                  checked={authType === 'SERVICE_ACCOUNT'}
                  onChange={() => setAuthType('SERVICE_ACCOUNT')}
                  className="accent-[#C2410C]"
                />
              </div>
              <p className="text-[11px] text-ember-neutral mt-1.5">
                Menggunakan email Service Account robot. Folder Drive harus di-share ke email robot tersebut sebagai Editor.
              </p>
            </div>
          </div>

          {/* OAuth 2.0 Status Banner */}
          {authType === 'OAUTH2' && (
            <div
              className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
                oauthConnected
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-amber-50 border-amber-200 text-amber-900'
              }`}
            >
              <div className="flex items-start space-x-2.5">
                {oauthConnected ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <h4 className="font-bold text-xs">
                    {oauthConnected
                      ? '🟢 Akun Google Terhubung (OAuth 2.0 Aktif)'
                      : '🔴 Akun Google Belum Diotorisasi'}
                  </h4>
                  <p className="text-[11px] text-ember-text-secondary mt-0.5">
                    {oauthConnected
                      ? 'Token akses Google Drive aktif. Video shorts siap di-export langsung ke folder Drive Anda.'
                      : 'Simpan JSON kredensial Anda di bawah ini, lalu klik tombol "Hubungkan Akun Google" untuk login.'}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleConnectGoogle}
                disabled={connectingOAuth}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm flex items-center space-x-1.5 shrink-0 ${
                  oauthConnected
                    ? 'bg-white border border-ember-border text-ember-text-primary hover:bg-ember-surface'
                    : 'bg-[#C2410C] hover:bg-[#9A3412] text-white'
                }`}
              >
                {connectingOAuth ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <LogIn className="w-3.5 h-3.5" />
                )}
                <span>{oauthConnected ? 'Hubungkan Ulang Akun' : 'Hubungkan Akun Google'}</span>
              </button>
            </div>
          )}

          {/* Redirect URI Info Box (Important for Google Cloud Console setup) */}
          {authType === 'OAUTH2' && (
            <div className="p-4 bg-[#FAF8F5] border border-[#E7E5E4] rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ember-text-primary flex items-center space-x-1.5">
                  <ExternalLink className="w-3.5 h-3.5 text-[#C2410C]" />
                  <span>Authorized Redirect URI untuk Google Cloud Console</span>
                </span>
                <button
                  type="button"
                  onClick={handleCopyRedirectUri}
                  className="px-2.5 py-1 bg-white hover:bg-ember-surface-raised border border-ember-border text-ember-text-primary rounded-lg text-[11px] font-semibold flex items-center space-x-1 transition-all"
                >
                  {copiedRedirectUri ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-600" />
                      <span className="text-emerald-700">Tersalin!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 text-ember-neutral" />
                      <span>Salin URI</span>
                    </>
                  )}
                </button>
              </div>
              <div className="p-2 bg-white rounded-lg border border-[#E7E5E4] font-mono text-xs text-ember-text-primary break-all select-all">
                {redirectUri}
              </div>
              <p className="text-[11px] text-ember-neutral">
                Pastikan URI di atas telah ditambahkan ke bagian <strong>Authorized redirect URIs</strong> pada konfigurasi OAuth Client ID di{' '}
                <a
                  href="https://console.cloud.google.com/apis/credentials"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#C2410C] font-semibold hover:underline"
                >
                  Google Cloud Console
                </a>.
              </p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSaveGDrive} className="space-y-4 text-left">
            <div>
              <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                Target Folder ID Google Drive
              </label>
              <input
                type="text"
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="1BxiMVs0XR_FAVT_9xD1G8x86XYZ..."
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                required
              />
              <p className="text-[11px] text-ember-neutral mt-1">
                Ambil dari tautan folder Google Drive: <code>drive.google.com/drive/folders/<strong>[ID_FOLDER]</strong></code>
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider">
                  Kredensial JSON Google (OAuth 2.0 Web Client atau Service Account)
                </label>
                {detectedJson && detectedJson.type !== 'INVALID' && (
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Terdeteksi: {detectedJson.label}</span>
                  </span>
                )}
              </div>
              <textarea
                rows={6}
                value={credentialsJson}
                onChange={(e) => setCredentialsJson(e.target.value)}
                placeholder='{"web":{"client_id":"1001207721542-...apps.googleusercontent.com","project_id":"clipping-508702","client_secret":"GOCSPX-..."}}'
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none resize-none"
              />
              <p className="text-[11px] text-ember-neutral mt-1">
                Cukup salin dan tempel seluruh isi berkas JSON yang Anda unduh dari Google Cloud Console di sini. Sistem akan otomatis mengekstrak parameter yang dibutuhkan.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2">
              <button
                type="submit"
                disabled={savingGDrive}
                className="py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all shadow-sm flex items-center justify-center space-x-1.5"
              >
                {savingGDrive ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Simpan Kredensial</span>
              </button>

              {authType === 'OAUTH2' && (
                <button
                  type="button"
                  onClick={handleConnectGoogle}
                  disabled={connectingOAuth}
                  className="py-2.5 bg-white hover:bg-ember-surface border border-ember-border text-ember-text-primary text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5"
                >
                  {connectingOAuth ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogIn className="w-3.5 h-3.5 text-[#C2410C]" />}
                  <span>{oauthConnected ? 'Hubungkan Ulang' : 'Hubungkan Akun Google'}</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleTestGDrive}
                disabled={testingGDrive || !folderId}
                className="py-2.5 bg-white hover:bg-ember-surface border border-ember-border text-ember-text-primary text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-40"
              >
                {testingGDrive ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FolderCheck className="w-3.5 h-3.5 text-emerald-600" />}
                <span>Uji Akses Folder</span>
              </button>
            </div>

            {/* Optional Manual Code Entry */}
            {authType === 'OAUTH2' && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowManualCode(!showManualCode)}
                  className="text-[11px] text-ember-neutral hover:text-[#C2410C] underline font-medium"
                >
                  {showManualCode ? 'Sembunyikan Otorisasi Manual' : 'Punya Kode Otorisasi Manual? (Klik di sini)'}
                </button>

                {showManualCode && (
                  <div className="mt-2 p-3 bg-ember-surface rounded-xl border border-[#E7E5E4] space-y-2">
                    <label className="block text-xs font-semibold text-ember-neutral">
                      Kode Verifikasi Google (Authorization Code)
                    </label>
                    <div className="flex space-x-2">
                      <input
                        type="text"
                        value={authCode}
                        onChange={(e) => setAuthCode(e.target.value)}
                        placeholder="4/0A... (kode yang disalin dari browser setelah login)"
                        className="flex-1 px-3 py-1.5 bg-white border border-ember-border rounded-lg text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                      />
                      <button
                        type="button"
                        onClick={handleExchangeManualCode}
                        disabled={exchangingCode || !authCode.trim()}
                        className="px-3 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-lg transition-all disabled:opacity-50"
                      >
                        {exchangingCode ? 'Memproses...' : 'Tukar Kode'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Test Result Card */}
            {gdriveTestResult && (
              <div
                className={`p-3.5 rounded-xl text-xs border ${
                  gdriveTestResult.ok
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-red-50 border-red-200 text-red-800'
                }`}
              >
                {gdriveTestResult.ok ? (
                  <span className="flex items-center space-x-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>
                      Folder Google Drive Valid: <strong>"{gdriveTestResult.folder_name}"</strong>. Siap melakukan upload video shorts!
                    </span>
                  </span>
                ) : (
                  <div className="flex items-start space-x-1.5">
                    <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold">Akses Gagal: </span>
                      <span>{gdriveTestResult.error}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB: YOUTUBE UPLOAD */}
      {activeTab === 'youtube' && (
        <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-ember-border">
            <div className="flex items-center space-x-2">
              <Youtube className="w-5 h-5 text-red-600" />
              <h3 className="font-semibold text-base text-ember-text-primary">YouTube Upload Configuration</h3>
            </div>
            <span
              className={`px-2.5 py-1 text-[11px] font-bold rounded-full ${
                ytConnected ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-200 text-stone-600'
              }`}
            >
              {ytConnected ? `Terhubung${ytChannel?.channel_name ? `: ${ytChannel.channel_name}` : ''}` : 'Belum terhubung'}
            </span>
          </div>

          <p className="text-xs text-ember-neutral">
            Buat OAuth 2.0 Web Client di Google Cloud Console (aktifkan <strong>YouTube Data API v3</strong>),
            tambahkan redirect URI <code className="bg-ember-surface px-1 py-0.5 rounded font-mono text-[#C2410C]">http://localhost:8000/api/youtube/callback</code>,
            lalu masukkan Client ID & Secret di bawah.
          </p>

          <form onSubmit={handleSaveYouTube} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                OAuth Client ID
              </label>
              <input
                type="text"
                value={ytClientId}
                onChange={(e) => setYtClientId(e.target.value)}
                placeholder="xxx.apps.googleusercontent.com"
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                OAuth Client Secret
              </label>
              <input
                type="password"
                value={ytClientSecret}
                onChange={(e) => setYtClientSecret(e.target.value)}
                placeholder="Kosongkan bila tak diganti"
                className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
              />
            </div>
            <div className="sm:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="submit"
                disabled={savingYt}
                className="py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50"
              >
                {savingYt ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Simpan Pengaturan YouTube</span>
              </button>
              <button
                type="button"
                onClick={handleConnectYouTube}
                disabled={connectingYt}
                className="py-2.5 bg-white hover:bg-ember-surface border border-ember-border text-ember-text-primary text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50"
              >
                {connectingYt ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogIn className="w-3.5 h-3.5 text-[#C2410C]" />}
                <span>{ytConnected ? 'Hubungkan Ulang' : 'Hubungkan YouTube'}</span>
              </button>
              <button
                type="button"
                onClick={handleTestYouTube}
                disabled={testingYt}
                className="py-2.5 bg-white hover:bg-ember-surface border border-ember-border text-ember-text-primary text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50"
              >
                {testingYt ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                <span>Uji Koneksi</span>
              </button>
            </div>
          </form>

          {/* Auto Upload & Default Publishing Settings */}
          <div className="pt-4 border-t border-ember-border space-y-4">
            <h4 className="font-semibold text-sm text-ember-text-primary flex items-center space-x-2">
              <span>🚀</span>
              <span>Otomatisasi & Default Penerbitan Shorts</span>
            </h4>

            {/* Toggle Auto Upload */}
            <div className="bg-ember-surface border border-ember-border rounded-xl p-4 flex items-center justify-between gap-4">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-ember-text-primary">Auto Upload ke YouTube saat Render Selesai</span>
                  {ytAutoUpload ? (
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800">Aktif</span>
                  ) : (
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-stone-200 text-stone-600">Nonaktif</span>
                  )}
                </div>
                <p className="text-[11px] text-ember-neutral">
                  Ketika sebuah short selesai dirender, worker otomatis menjadwalkan ke antrean upload YouTube dengan judul kontekstual, deskripsi, hashtags, dan thumbnail.
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={ytAutoUpload}
                  onChange={(e) => setYtAutoUpload(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-stone-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-stone-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C2410C]"></div>
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Default Privacy */}
              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  Default Privasi Upload
                </label>
                <select
                  value={ytDefaultPrivacy}
                  onChange={(e) => setYtDefaultPrivacy(e.target.value)}
                  className="w-full px-3 py-2 bg-ember-surface border border-ember-border rounded-xl text-xs font-semibold text-ember-text-primary focus:border-[#C2410C] outline-none"
                >
                  <option value="public">🌍 Public (Langsung Tayang ke Publik)</option>
                  <option value="unlisted">🔗 Unlisted (Hanya yang Punya Link)</option>
                  <option value="private">🔒 Private (Hanya Pemilik Channel)</option>
                </select>
                <p className="text-[10px] text-ember-neutral mt-1">
                  Pilihan status visibilitas saat upload otomatis dijalankan.
                </p>
              </div>

              {/* Default Audience / Age */}
              <div>
                <label className="block text-xs font-semibold text-ember-neutral uppercase tracking-wider mb-1">
                  Kategori Usia / Audiens (Age)
                </label>
                <div className="px-3 py-2 bg-ember-surface border border-ember-border rounded-xl flex items-center justify-between">
                  <div className="text-xs">
                    <span className="font-semibold text-ember-text-primary">Semua Kalangan Umur</span>
                    <span className="text-[10px] text-ember-neutral block">selfDeclaredMadeForKids: false</span>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                    Otomatis Aktif
                  </span>
                </div>
                <p className="text-[10px] text-ember-neutral mt-1">
                  Komentar dan notifikasi subscriber tetap aktif sesuai standar YouTube.
                </p>
              </div>
            </div>

            {/* Thumbnail Auto Info Banner */}
            <div className="bg-orange-50/60 border border-orange-200 rounded-xl p-3 flex items-start gap-2.5">
              <span className="text-base leading-none">🖼️</span>
              <div className="text-xs text-orange-950">
                <span className="font-semibold">Auto Thumbnail YouTube:</span>
                <p className="text-[11px] text-orange-900 mt-0.5">
                  Setiap klip yang selesai dirender secara otomatis memiliki thumbnail resolusi tinggi dari frame wajah/fokus terbaik, dan akan otomatis disematkan saat diunggah ke YouTube.
                </p>
              </div>
            </div>
          </div>

          {ytChannel?.subscriber_count && (
            <p className="text-xs text-ember-neutral">
              Subscriber: <strong className="text-ember-text-primary">{ytChannel.subscriber_count}</strong>
            </p>
          )}
        </div>
      )}

      {/* TAB: WHATSAPP BOT (WAHA) */}
      {activeTab === 'waha' && (
        <div className="space-y-6">
          {/* Card 1: WAHA Live Connection & QR Code */}
          <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F5F5F4]">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-emerald-50 text-emerald-700 rounded-xl">
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base text-ember-text-primary flex items-center space-x-2">
                    <span>Sesi WhatsApp (WAHA)</span>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        waha?.session_status === 'WORKING'
                          ? 'bg-emerald-100 text-emerald-800'
                          : waha?.session_status === 'SCAN_QR_CODE' || waha?.session_status === 'STARTING'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-stone-100 text-stone-600'
                      }`}
                    >
                      {waha?.session_status === 'WORKING'
                        ? '🟢 Online / Siap'
                        : waha?.session_status === 'SCAN_QR_CODE' || waha?.session_status === 'STARTING'
                        ? '🟡 Scan QR Code'
                        : '⚪ Sesi Offline / Berhenti'}
                    </span>
                  </h3>
                  <p className="text-xs text-ember-text-secondary mt-0.5">
                    WAHA (WhatsApp HTTP API) menghubungkan sistem otomatisasi EmberShorts ke WhatsApp Anda.
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={refreshWaha}
                  disabled={loadingWaha}
                  className="px-3 py-1.5 bg-ember-surface hover:bg-ember-surface-raised rounded-lg text-xs font-medium text-ember-text-secondary flex items-center space-x-1.5 transition-all"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingWaha ? 'animate-spin' : ''}`} />
                  <span>Segarkan</span>
                </button>

                {waha?.session_status !== 'WORKING' && (
                  <button
                    type="button"
                    onClick={handleStartWahaSession}
                    disabled={startingWaha}
                    className="px-3 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-lg flex items-center space-x-1.5 shadow-sm transition-all"
                  >
                    {startingWaha ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <QrCode className="w-3.5 h-3.5" />}
                    <span>Mulai Sesi / Scan QR</span>
                  </button>
                )}

                {waha?.session_status === 'WORKING' && (
                  <button
                    type="button"
                    onClick={handleLogoutWahaSession}
                    className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-all"
                  >
                    <Unlink className="w-3.5 h-3.5" />
                    <span>Logout Sesi</span>
                  </button>
                )}
              </div>
            </div>

            {/* Offline / Stopped Session Banner with big Start CTA */}
            {waha?.session_status !== 'WORKING' && waha?.session_status !== 'SCAN_QR_CODE' && waha?.session_status !== 'STARTING' && !waha?.qr_code && (
              <div className="p-6 bg-stone-50 border border-[#E7E5E4] rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
                <div>
                  <h4 className="font-semibold text-sm text-ember-text-primary flex items-center justify-center sm:justify-start space-x-1.5">
                    <span className="inline-block w-2 h-2 rounded-full bg-stone-400"></span>
                    <span>Sesi WhatsApp Sedang Offline / Berhenti</span>
                  </h4>
                  <p className="text-xs text-ember-text-secondary mt-1 max-w-lg">
                    Sesi bot WhatsApp belum dimulai. Klik tombol di samping untuk mengaktifkan sesi WAHA dan menampilkan QR Code untuk di-scan lewat HP Anda.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleStartWahaSession}
                  disabled={startingWaha}
                  className="px-5 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl flex items-center space-x-2 shadow-sm transition-all whitespace-nowrap"
                >
                  {startingWaha ? <Loader2 className="w-4 h-4 animate-spin" /> : <QrCode className="w-4 h-4" />}
                  <span>Mulai Sesi &amp; Tampilkan QR Code</span>
                </button>
              </div>
            )}

            {/* QR Code Container if Scan is required */}
            {(waha?.session_status === 'SCAN_QR_CODE' || waha?.session_status === 'STARTING' || waha?.qr_code) && (
              <div className="p-6 bg-amber-50 border border-amber-200 rounded-xl flex flex-col items-center text-center space-y-4">
                <h4 className="font-semibold text-sm text-amber-900">Scan QR Code dengan WhatsApp</h4>
                <p className="text-xs text-amber-800 max-w-md">
                  1. Buka aplikasi WhatsApp di HP Anda.<br />
                  2. Pilih menu <strong>Perangkat Tertaut (Linked Devices) &gt; Tautkan Perangkat</strong>.<br />
                  3. Arahkan kamera HP ke kode QR di bawah ini:
                </p>

                {waha?.qr_code ? (
                  <div className="bg-white p-4 rounded-xl border border-amber-300 shadow-sm">
                    {waha.qr_code.startsWith('data:') ? (
                      <img src={waha.qr_code} alt="WAHA WhatsApp QR Code" className="w-64 h-64 mx-auto" />
                    ) : (
                      <div className="font-mono text-xs p-3 bg-stone-100 rounded break-all max-w-xs overflow-auto">
                        {waha.qr_code}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-8 flex flex-col items-center space-y-2">
                    <Loader2 className="w-8 h-8 animate-spin text-amber-700" />
                    <span className="text-xs text-amber-800">Menghubungkan ke WAHA engine...</span>
                  </div>
                )}

                <button
                  type="button"
                  onClick={refreshWaha}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-2"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Cek Status Setelah Scan</span>
                </button>
              </div>
            )}

            {/* Card 2: Pairing Token & First-Time Sync */}
            <div className="p-5 bg-[#FBFBFA] border border-[#E7E5E4] rounded-xl space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-sm text-ember-text-primary flex items-center space-x-1.5">
                    <Key className="w-4 h-4 text-[#C2410C]" />
                    <span>Kata Kunci Sinkronisasi (Pairing Token)</span>
                  </h4>
                  <p className="text-xs text-ember-neutral mt-0.5">
                    Kirim pesan kata kunci ini dari WhatsApp pribadi atau WhatsApp Group untuk menautkannya ke EmberShorts.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleRegenerateWahaToken}
                  disabled={regeneratingToken}
                  className="px-3 py-1 bg-white border border-ember-border hover:bg-ember-surface text-xs font-medium text-ember-text-secondary rounded-lg transition-all flex items-center space-x-1.5 self-start sm:self-auto"
                >
                  <RefreshCw className={`w-3 h-3 ${regeneratingToken ? 'animate-spin' : ''}`} />
                  <span>Regenerasi Token</span>
                </button>
              </div>

              {/* Prominent Copy Box */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center space-y-2 sm:space-y-0 sm:space-x-2">
                <div className="flex-1 bg-stone-900 text-stone-100 font-mono text-sm px-4 py-3 rounded-xl flex items-center justify-between border border-stone-800">
                  <span className="select-all tracking-wider text-amber-400 font-bold">
                    connect {waha?.sync_token || 'embershorts-564721'}
                  </span>
                  <span className="text-[10px] text-stone-400 uppercase tracking-widest px-2 py-0.5 bg-stone-800 rounded">
                    Pairing Token
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyPairingToken}
                  className="px-4 py-3 bg-[#C2410C] hover:bg-[#9A3412] text-white rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all shrink-0"
                >
                  {copiedToken ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  <span>{copiedToken ? 'Disalin!' : 'Salin Kata Kunci'}</span>
                </button>
              </div>

              <div className="text-xs text-ember-neutral bg-white p-3.5 rounded-lg border border-[#E7E5E4] space-y-1.5">
                <p className="font-semibold text-ember-text-primary">💡 Cara Kerja Penautan (Pairing):</p>
                <ol className="list-decimal list-inside space-y-1 text-ember-text-secondary">
                  <li>Salin teks di atas (contoh: <code className="bg-ember-surface px-1 py-0.5 rounded text-[#C2410C] font-mono">connect {waha?.sync_token || 'embershorts-564721'}</code>).</li>
                  <li>Buka WhatsApp dan kirim pesan tersebut ke nomor WA bot yang terhubung, atau kirim di dalam Group WhatsApp yang ingin ditautkan.</li>
                  <li>Sistem akan mendeteksi pengirim dan membalas pesan konfirmasi. Obrolan tersebut langsung aktif sebagai pengontrol bot!</li>
                </ol>
              </div>
            </div>

            {/* Card 3: Paired Target Status */}
            <div className="p-5 bg-white border border-[#E7E5E4] rounded-xl space-y-3">
              <h4 className="font-semibold text-sm text-ember-text-primary flex items-center space-x-2">
                <Bot className="w-4 h-4 text-emerald-600" />
                <span>Akun / Grup WhatsApp Tertaut</span>
              </h4>

              {waha?.paired_chat_id ? (
                <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-xl space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                        <span className="font-bold text-sm text-emerald-950">
                          {waha.paired_chat_name || 'Obrolan WhatsApp'}
                        </span>
                        <span className="px-2 py-0.5 bg-emerald-200/60 text-emerald-800 text-[10px] font-bold rounded-full uppercase">
                          {waha.paired_chat_type === 'group' ? 'Grup WhatsApp' : 'Kontak Pribadi'}
                        </span>
                      </div>
                      <p className="text-xs font-mono text-emerald-800 mt-1">
                        ID: {waha.paired_chat_id}
                      </p>
                      {waha.paired_at && (
                        <p className="text-[10px] text-emerald-700 mt-0.5">
                          Tautan aktif sejak: {new Date(waha.paired_at).toLocaleString('id-ID')}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <button
                        type="button"
                        onClick={handleSendWahaTestMessage}
                        disabled={testingWahaMsg}
                        className="px-3 py-1.5 bg-white border border-emerald-300 hover:bg-emerald-100/50 text-emerald-900 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-all shadow-sm"
                      >
                        {testingWahaMsg ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        <span>Kirim Pesan Uji</span>
                      </button>

                      <button
                        type="button"
                        onClick={handleUnpairWaha}
                        disabled={unpairingWaha}
                        className="px-3 py-1.5 bg-white border border-red-200 hover:bg-red-50 text-red-600 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-all"
                      >
                        {unpairingWaha ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Unlink className="w-3.5 h-3.5" />}
                        <span>Putuskan</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-stone-50 border border-stone-200 rounded-xl text-xs text-ember-text-secondary flex items-center space-x-3">
                  <AlertCircle className="w-5 h-5 text-amber-500 shrink-0" />
                  <span>
                    Belum ada nomor atau grup WhatsApp yang terhubung. Kirim pesan kata kunci pairing di atas untuk menautkan.
                  </span>
                </div>
              )}
            </div>

            {/* Card 4: Command Cheat Sheet */}
            <div className="p-5 bg-white border border-[#E7E5E4] rounded-xl space-y-4">
              <div className="flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-[#C2410C]" />
                <h4 className="font-semibold text-sm text-ember-text-primary">Daftar Perintah Bot WhatsApp</h4>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 bg-[#FBFBFA] border border-[#E7E5E4] rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[#C2410C]">#shorts help / #help</span>
                    <span className="text-[10px] text-ember-neutral bg-white px-2 py-0.5 rounded border border-[#E7E5E4]">Bantuan</span>
                  </div>
                  <p className="text-ember-text-secondary">
                    Menampilkan seluruh daftar perintah dan petunjuk penggunaan bot.
                  </p>
                </div>

                <div className="p-3.5 bg-[#FBFBFA] border border-[#E7E5E4] rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[#C2410C]">#shorts process &lt;link_yt&gt;</span>
                    <span className="text-[10px] text-ember-neutral bg-white px-2 py-0.5 rounded border border-[#E7E5E4]">Clip Studio</span>
                  </div>
                  <p className="text-ember-text-secondary">
                    Download video YouTube, transcribe audio, & ekstrak highlight AI ke Clip Studio (tanpa auto-render).
                  </p>
                </div>

                <div className="p-3.5 bg-[#FBFBFA] border border-[#E7E5E4] rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[#C2410C]">#shorts process all &lt;link_yt&gt;</span>
                    <span className="text-[10px] text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">Auto Shorts</span>
                  </div>
                  <p className="text-ember-text-secondary">
                    Download video, transcribe, ekstrak AI, & otomatis merender seluruh kandidat menjadi Shorts (9:16) vertikal dengan preset genre otomatis.
                  </p>
                </div>

                <div className="p-3.5 bg-[#FBFBFA] border border-[#E7E5E4] rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-[#C2410C]">#shorts status / #status</span>
                    <span className="text-[10px] text-ember-neutral bg-white px-2 py-0.5 rounded border border-[#E7E5E4]">Antrean</span>
                  </div>
                  <p className="text-ember-text-secondary">
                    Menampilkan status pemrosesan dan progres dari 10 video terakhir di background worker antrean sistem.
                  </p>
                </div>
              </div>

              <p className="text-[11px] text-ember-neutral italic">
                * Khusus di dalam Group WhatsApp, gunakan awalan <code className="bg-ember-surface px-1 py-0.5 rounded font-mono text-[#C2410C]">#shorts</code> (misal: <code className="bg-ember-surface px-1 py-0.5 rounded font-mono">#shorts process all https://...</code> atau tag bot @bot).
              </p>
            </div>

            {/* Card 5: WAHA API Settings Form */}
            <form onSubmit={handleSaveWahaConfig} className="p-5 bg-white border border-[#E7E5E4] rounded-xl space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-[#F5F5F4]">
                <h4 className="font-semibold text-sm text-ember-text-primary flex items-center space-x-1.5">
                  <Sliders className="w-4 h-4 text-ember-neutral" />
                  <span>Konfigurasi Server WAHA</span>
                </h4>
                <label className="flex items-center space-x-2 cursor-pointer text-xs font-medium text-ember-text-primary">
                  <input
                    type="checkbox"
                    checked={wahaEnabled}
                    onChange={(e) => setWahaEnabled(e.target.checked)}
                    className="w-4 h-4 text-[#C2410C] rounded border-ember-border focus:ring-[#C2410C]"
                  />
                  <span>Aktifkan Bot WhatsApp</span>
                </label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-ember-neutral mb-1">
                    WAHA API Endpoint URL
                  </label>
                  <input
                    type="text"
                    value={wahaApiUrl}
                    onChange={(e) => setWahaApiUrl(e.target.value)}
                    placeholder="http://localhost:3008 atau http://waha:3000"
                    className="w-full px-3 py-2 bg-[#FBFBFA] border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                    required
                  />
                  <p className="text-[10px] text-ember-neutral mt-1">
                    Port default container WAHA adalah 3008 (atau 3000 di dalam docker network).
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ember-neutral mb-1">
                    Session Name
                  </label>
                  <input
                    type="text"
                    value={wahaSessionName}
                    onChange={(e) => setWahaSessionName(e.target.value)}
                    placeholder="default"
                    className="w-full px-3 py-2 bg-[#FBFBFA] border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                    required
                  />
                  <p className="text-[10px] text-ember-neutral mt-1">
                    Nama sesi WAHA (default: 'default').
                  </p>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-ember-neutral mb-1">
                    API Key WAHA (Opsional)
                  </label>
                  <input
                    type="password"
                    value={wahaApiKey}
                    onChange={(e) => setWahaApiKey(e.target.value)}
                    placeholder="Kosongkan jika WAHA tidak dikonfigurasi dengan API key"
                    className="w-full px-3 py-2 bg-[#FBFBFA] border border-ember-border rounded-xl text-xs font-mono text-ember-text-primary focus:border-[#C2410C] outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={savingWaha}
                  className="px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl flex items-center space-x-1.5 shadow-sm transition-all disabled:opacity-50"
                >
                  {savingWaha ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>Simpan Konfigurasi WAHA</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TAB 4: STATUS MESIN LOKAL */}
      {activeTab === 'system' && (
        <div className="space-y-4">
        <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-base text-ember-text-primary">Tema Tampilan</h3>
              <p className="text-xs text-ember-neutral mt-0.5">Sistem mengikuti preferensi OS bila dipilih. Pratinjau video (SubtitleFrame) selalu terang agar WYSIWYG.</p>
            </div>
            <div className="flex gap-1.5 p-1 bg-ember-surface rounded-xl border border-ember-border">
              {(['light', 'dark', 'system'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTheme(t)}
                  className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    themeChoice === t ? 'bg-[#C2410C] text-white shadow-sm' : 'text-ember-text-secondary hover:text-ember-text-primary'
                  }`}
                >
                  {t === 'light' ? '☀️ Terang' : t === 'dark' ? '🌙 Gelap' : '🖥️ Sistem'}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="bg-white border border-ember-border rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
            <div className="flex items-center space-x-2">
              <Activity className="w-5 h-5 text-[#C2410C]" />
              <h3 className="font-semibold text-base text-ember-text-primary">Status Engine & Subsistem Lokal</h3>
            </div>
            <button
              type="button"
              onClick={handleRefreshHealth}
              disabled={refreshingHealth}
              className="px-3 py-1.5 bg-ember-surface hover:bg-ember-surface-raised rounded-lg text-xs font-medium text-ember-text-secondary flex items-center space-x-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshingHealth ? 'animate-spin' : ''}`} />
              <span>Segarkan Status</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 bg-ember-surface rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-ember-neutral">Database State (SQLite)</p>
                <p className="font-semibold text-sm text-ember-text-primary mt-0.5">
                  {health?.db ? 'Connected (Normal)' : 'Disconnected'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">storage/autoshorts.db</p>
              </div>
              <span className={`w-3.5 h-3.5 rounded-full ${health?.db ? 'bg-emerald-500 shadow-sm shadow-emerald-400' : 'bg-red-500'}`} />
            </div>

            <div className="p-4 bg-ember-surface rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-ember-neutral">Local Storage</p>
                <p className="font-semibold text-sm text-ember-text-primary mt-0.5">
                  {health?.storage_writable ? 'Writable (Aktif)' : 'Read-Only'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">Berkas video & klip tersimpan lokal</p>
              </div>
              <span className={`w-3.5 h-3.5 rounded-full ${health?.storage_writable ? 'bg-emerald-500 shadow-sm shadow-emerald-400' : 'bg-red-500'}`} />
            </div>

            <div className="p-4 bg-ember-surface rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-ember-neutral">FFmpeg Engine</p>
                <p className="font-semibold text-sm text-ember-text-primary mt-0.5 truncate max-w-[150px]">
                  {health?.ffmpeg || 'Ready'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">libass subtitle & 9:16 crop</p>
              </div>
              <span className="w-3.5 h-3.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-400" />
            </div>
          </div>
        </div>
        </div>
      )}
    </div>
  );
};
