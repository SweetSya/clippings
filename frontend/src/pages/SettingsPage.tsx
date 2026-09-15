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
  LogIn
} from 'lucide-react';
import { settingsApi, healthApi } from '../services/api';
import { HealthStatus } from '../types';

type TabType = 'ai' | 'video' | 'gdrive' | 'system';

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('ai');
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

  // General Form (Clip Durations & YouTube)
  const [minClipSeconds, setMinClipSeconds] = useState(10);
  const [maxClipSeconds, setMaxClipSeconds] = useState(60);
  const [ytQuality, setYtQuality] = useState('1080p');

  // LLM Form
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('gpt-4o-mini');
  const [temperature, setTemperature] = useState(0.4);
  const [prompt, setPrompt] = useState('');
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
    };
    window.addEventListener('message', handleOAuthMessage);
    return () => window.removeEventListener('message', handleOAuthMessage);
  }, []);

  const loadSettings = async () => {
    try {
      const [s, h] = await Promise.all([settingsApi.get(), healthApi.check()]);
      setHealth(h);
      if (s.llm_base_url) setBaseUrl(s.llm_base_url);
      if (s.llm_model) setModelName(s.llm_model);
      if (s.llm_prompt) setPrompt(s.llm_prompt);
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
    } catch (e) {
      console.error('Failed to load settings', e);
    } finally {
      setLoading(false);
    }
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
      await settingsApi.updateAI({
        base_url: baseUrl,
        api_key: apiKey || undefined,
        model_name: modelName,
        temperature,
        prompt: prompt || undefined,
      });
      setLlmConnected(false); // Reset to false until tested
      setAiTestResult(null);
      setMessage('Konfigurasi AI disimpan. Status di-reset ke "Belum Terhubung" sampai Anda mengklik "Uji Koneksi AI".');
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="font-display font-bold text-3xl text-[#1C1917]">Pengaturan Sistem</h2>
        <p className="text-[#57534E] text-sm mt-1">
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
      <div className="flex border-b border-[#D6D3D1] space-x-1 sm:space-x-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('ai')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'ai'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-[#78716C] hover:text-[#1C1917] hover:border-[#A8A29E]'
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
              : 'border-transparent text-[#78716C] hover:text-[#1C1917] hover:border-[#A8A29E]'
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
              : 'border-transparent text-[#78716C] hover:text-[#1C1917] hover:border-[#A8A29E]'
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
          onClick={() => setActiveTab('system')}
          className={`flex items-center space-x-2 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'system'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-[#78716C] hover:text-[#1C1917] hover:border-[#A8A29E]'
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
                <h4 className="font-semibold text-sm text-[#1C1917] flex items-center space-x-2">
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
                <p className="text-xs text-[#57534E] mt-1">
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
                  ? 'bg-white border border-[#D6D3D1] text-[#1C1917] hover:bg-[#F5F5F4]'
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
          <div className="bg-white border border-[#D6D3D1] rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-[#C2410C]" />
                <h3 className="font-semibold text-base text-[#1C1917]">
                  Konfigurasi LLM (OpenAI / Ollama / LM Studio)
                </h3>
              </div>
              <span className="text-[11px] text-[#78716C]">
                Mendukung OpenAI API & Penyedia Lokal Sesuai Standar OpenAI
              </span>
            </div>

            <form onSubmit={handleSaveAI} className="space-y-4 text-left">
              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                  OpenAI-Compatible Base URL
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1 atau https://api.openai.com/v1"
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-[#78716C] mt-1">
                  Contoh: <code>http://localhost:11434/v1</code> (Ollama), <code>http://localhost:1234/v1</code> (LM Studio), atau <code>https://api.openai.com/v1</code>.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                  API Key (Opsional untuk LLM Lokal)
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-... (Disimpan terenkripsi)"
                    className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                  />
                  <Key className="w-3.5 h-3.5 text-[#A8A29E] absolute right-3 top-3 pointer-events-none" />
                </div>
                <p className="text-[11px] text-[#78716C] mt-1">
                  Kosongkan jika menggunakan Ollama atau server lokal tanpa otentikasi.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                    Nama Model
                  </label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder="gpt-4o-mini, llama3.1, qwen2.5..."
                    className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
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
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                  System Prompt Kustom (Konteks Besar & Konteks Kecil)
                </label>
                <textarea
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Kosongkan untuk menggunakan prompt standar AutoShorts (Konteks Besar transkrip + judul + deskripsi dan Konteks Kecil segmen durasi)..."
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none resize-none"
                />
                <p className="text-[11px] text-[#78716C] mt-1">
                  Secara default, AI memadukan <strong>Konteks Besar</strong> (seluruh transkrip, judul, & deskripsi) untuk menolak basa-basi/sponsor, serta <strong>Konteks Kecil</strong> (potongan timestamp) untuk memotong bagian paling viral.
                </p>
              </div>

              <div className="pt-2 flex items-center justify-between">
                <p className="text-[11px] text-amber-700">
                  ⚠️ Perubahan konfigurasi akan menuntut pengujian koneksi ulang.
                </p>
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={handleTestAI}
                    disabled={testingAI}
                    className="px-4 py-2 bg-white hover:bg-[#F5F5F4] border border-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5"
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
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center space-x-2 pb-3 border-b border-[#F5F5F4]">
            <Sliders className="w-5 h-5 text-[#C2410C]" />
            <h3 className="font-semibold text-base text-[#1C1917]">
              Pengaturan Durasi Klip & YouTube Downloader
            </h3>
          </div>

          <form onSubmit={handleSaveGeneral} className="space-y-4 text-left">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Durasi Klip Minimal (Detik)</span>
                </label>
                <input
                  type="number"
                  min="5"
                  max="180"
                  value={minClipSeconds}
                  onChange={(e) => setMinClipSeconds(parseInt(e.target.value) || 5)}
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-[#78716C] mt-1">
                  Batas durasi minimal untuk klip yang diidentifikasi oleh AI (default: 10 detik).
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Durasi Klip Maksimal (Detik)</span>
                </label>
                <input
                  type="number"
                  min="10"
                  max="300"
                  value={maxClipSeconds}
                  onChange={(e) => setMaxClipSeconds(parseInt(e.target.value) || 60)}
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                  required
                />
                <p className="text-[11px] text-[#78716C] mt-1">
                  Batas durasi maksimal klip untuk YouTube Shorts / TikTok (default: 60 detik).
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
                <Youtube className="w-3.5 h-3.5 text-red-600" />
                <span>Kualitas Unduhan YouTube Default</span>
              </label>
              <select
                value={ytQuality}
                onChange={(e) => setYtQuality(e.target.value)}
                className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
              >
                <option value="1080p">1080p Full HD (Disarankan jika tersedia)</option>
                <option value="720p">720p HD (Unduh lebih cepat)</option>
                <option value="best">Kualitas Maksimal Tersedia (Best Available)</option>
              </select>
              <p className="text-[11px] text-[#78716C] mt-1">
                Kualitas video standar saat menempelkan link YouTube ke dalam sistem.
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
        </div>
      )}

      {/* TAB 3: GDRIVE EXPORT */}
      {activeTab === 'gdrive' && (
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
            <div className="flex items-center space-x-2">
              <Cloud className="w-5 h-5 text-[#C2410C]" />
              <h3 className="font-semibold text-base text-[#1C1917]">Google Drive Export Configuration</h3>
            </div>
            <span className="text-[11px] text-[#78716C]">
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
                  : 'bg-[#F5F5F4] border-[#E7E5E4] hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#1C1917] flex items-center space-x-1.5">
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
              <p className="text-[11px] text-[#78716C] mt-1.5">
                Sesuai berkas JSON dari Google Cloud Console Anda. Cukup simpan JSON lalu hubungkan akun dengan sekali klik.
              </p>
            </div>

            <div
              onClick={() => setAuthType('SERVICE_ACCOUNT')}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                authType === 'SERVICE_ACCOUNT'
                  ? 'bg-orange-50/60 border-[#C2410C] ring-1 ring-[#C2410C]'
                  : 'bg-[#F5F5F4] border-[#E7E5E4] hover:bg-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#1C1917] flex items-center space-x-1.5">
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
              <p className="text-[11px] text-[#78716C] mt-1.5">
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
                  <p className="text-[11px] text-[#57534E] mt-0.5">
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
                    ? 'bg-white border border-[#D6D3D1] text-[#1C1917] hover:bg-[#F5F5F4]'
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
                <span className="text-xs font-bold text-[#1C1917] flex items-center space-x-1.5">
                  <ExternalLink className="w-3.5 h-3.5 text-[#C2410C]" />
                  <span>Authorized Redirect URI untuk Google Cloud Console</span>
                </span>
                <button
                  type="button"
                  onClick={handleCopyRedirectUri}
                  className="px-2.5 py-1 bg-white hover:bg-[#E7E5E4] border border-[#D6D3D1] text-[#1C1917] rounded-lg text-[11px] font-semibold flex items-center space-x-1 transition-all"
                >
                  {copiedRedirectUri ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-600" />
                      <span className="text-emerald-700">Tersalin!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 text-[#78716C]" />
                      <span>Salin URI</span>
                    </>
                  )}
                </button>
              </div>
              <div className="p-2 bg-white rounded-lg border border-[#E7E5E4] font-mono text-xs text-[#1C1917] break-all select-all">
                {redirectUri}
              </div>
              <p className="text-[11px] text-[#78716C]">
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
              <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">
                Target Folder ID Google Drive
              </label>
              <input
                type="text"
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="1BxiMVs0XR_FAVT_9xD1G8x86XYZ..."
                className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
                required
              />
              <p className="text-[11px] text-[#78716C] mt-1">
                Ambil dari tautan folder Google Drive: <code>drive.google.com/drive/folders/<strong>[ID_FOLDER]</strong></code>
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider">
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
                className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none resize-none"
              />
              <p className="text-[11px] text-[#78716C] mt-1">
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
                  className="py-2.5 bg-white hover:bg-[#F5F5F4] border border-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5"
                >
                  {connectingOAuth ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogIn className="w-3.5 h-3.5 text-[#C2410C]" />}
                  <span>{oauthConnected ? 'Hubungkan Ulang' : 'Hubungkan Akun Google'}</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleTestGDrive}
                disabled={testingGDrive || !folderId}
                className="py-2.5 bg-white hover:bg-[#F5F5F4] border border-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-40"
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
                  className="text-[11px] text-[#78716C] hover:text-[#C2410C] underline font-medium"
                >
                  {showManualCode ? 'Sembunyikan Otorisasi Manual' : 'Punya Kode Otorisasi Manual? (Klik di sini)'}
                </button>

                {showManualCode && (
                  <div className="mt-2 p-3 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] space-y-2">
                    <label className="block text-xs font-semibold text-[#78716C]">
                      Kode Verifikasi Google (Authorization Code)
                    </label>
                    <div className="flex space-x-2">
                      <input
                        type="text"
                        value={authCode}
                        onChange={(e) => setAuthCode(e.target.value)}
                        placeholder="4/0A... (kode yang disalin dari browser setelah login)"
                        className="flex-1 px-3 py-1.5 bg-white border border-[#D6D3D1] rounded-lg text-xs font-mono text-[#1C1917] focus:border-[#C2410C] outline-none"
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

      {/* TAB 4: STATUS MESIN LOKAL */}
      {activeTab === 'system' && (
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#F5F5F4]">
            <div className="flex items-center space-x-2">
              <Activity className="w-5 h-5 text-[#C2410C]" />
              <h3 className="font-semibold text-base text-[#1C1917]">Status Engine & Subsistem Lokal</h3>
            </div>
            <button
              type="button"
              onClick={handleRefreshHealth}
              disabled={refreshingHealth}
              className="px-3 py-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-lg text-xs font-medium text-[#57534E] flex items-center space-x-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshingHealth ? 'animate-spin' : ''}`} />
              <span>Segarkan Status</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-[#78716C]">Database State (SQLite)</p>
                <p className="font-semibold text-sm text-[#1C1917] mt-0.5">
                  {health?.db ? 'Connected (Normal)' : 'Disconnected'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">storage/autoshorts.db</p>
              </div>
              <span className={`w-3.5 h-3.5 rounded-full ${health?.db ? 'bg-emerald-500 shadow-sm shadow-emerald-400' : 'bg-red-500'}`} />
            </div>

            <div className="p-4 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-[#78716C]">Local Storage</p>
                <p className="font-semibold text-sm text-[#1C1917] mt-0.5">
                  {health?.storage_writable ? 'Writable (Aktif)' : 'Read-Only'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">Berkas video & klip tersimpan lokal</p>
              </div>
              <span className={`w-3.5 h-3.5 rounded-full ${health?.storage_writable ? 'bg-emerald-500 shadow-sm shadow-emerald-400' : 'bg-red-500'}`} />
            </div>

            <div className="p-4 bg-[#F5F5F4] rounded-xl border border-[#E7E5E4] flex items-center justify-between">
              <div>
                <p className="text-xs text-[#78716C]">FFmpeg Engine</p>
                <p className="font-semibold text-sm text-[#1C1917] mt-0.5 truncate max-w-[150px]">
                  {health?.ffmpeg || 'Ready'}
                </p>
                <p className="text-[10px] text-[#A8A29E] mt-1">libass subtitle & 9:16 crop</p>
              </div>
              <span className="w-3.5 h-3.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-400" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
