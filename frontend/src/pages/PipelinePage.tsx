import React, { useState, useEffect } from 'react';
import {
  Workflow,
  Sparkles,
  Sliders,
  Layers,
  Plus,
  Trash2,
  Save,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Send,
  ExternalLink,
  HelpCircle,
  ArrowRight,
  Video,
  PlaySquare,
  Cloud,
  MessageSquare,
  ShieldCheck,
  ChevronDown,
  Info
} from 'lucide-react';
import { pipelineApi, presetsApi } from '../services/api';
import { PipelineConfig, PipelineRule, TextPreset, PipelineMatchTestResponse } from '../types';

export const PipelinePage: React.FC = () => {
  const [config, setConfig] = useState<PipelineConfig>({
    auto_clip_enabled: true,
    min_score: 70,
    context_rules: [],
    default_preset_id: 'preset_tiktok_bold',
    auto_upload_youtube: false,
    auto_upload_gdrive: false,
    auto_notify_whatsapp: true,
    whatsapp_target_chat: '',
    whatsapp_paired: false,
    youtube_connected: false,
    gdrive_connected: false,
  });

  const [presets, setPresets] = useState<TextPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingWa, setTestingWa] = useState(false);
  const [testingMatch, setTestingMatch] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  // Live Match Tester State
  const [testTitle, setTestTitle] = useState("Marvel's Wolverine GAMEPLAY Walkthrough #2.mp4");
  const [testVideoType, setTestVideoType] = useState('gaming_streamer');
  const [matchResult, setMatchResult] = useState<PipelineMatchTestResponse | null>(null);

  // New Rule Modal / State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRuleName, setNewRuleName] = useState('');
  const [newRuleContext, setNewRuleContext] = useState('');
  const [newRulePresetId, setNewRulePresetId] = useState('');

  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4500);
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [cfgData, presetList] = await Promise.all([
        pipelineApi.getConfig(),
        presetsApi.list(),
      ]);
      setConfig(cfgData);
      setPresets(presetList);
      if (presetList.length > 0 && !newRulePresetId) {
        setNewRulePresetId(presetList[0].id);
      }
    } catch (err: any) {
      showToast('error', 'Gagal memuat konfigurasi pipeline: ' + (err.message || 'Error'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await pipelineApi.updateConfig({
        auto_clip_enabled: config.auto_clip_enabled,
        min_score: config.min_score,
        context_rules: config.context_rules,
        default_preset_id: config.default_preset_id,
        auto_upload_youtube: config.auto_upload_youtube,
        auto_upload_gdrive: config.auto_upload_gdrive,
        auto_notify_whatsapp: config.auto_notify_whatsapp,
        whatsapp_target_chat: config.whatsapp_target_chat,
      });
      setConfig(res.config);
      showToast('success', 'Konfigurasi pipeline otomatis berhasil disimpan!');
    } catch (err: any) {
      showToast('error', 'Gagal menyimpan konfigurasi: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleAddRule = () => {
    if (!newRuleContext.trim()) {
      showToast('error', 'Konteks / kata kunci wajib diisi');
      return;
    }
    const targetPreset = newRulePresetId || (presets.length > 0 ? presets[0].id : '');
    const newRule: PipelineRule = {
      id: 'rule_' + Math.random().toString(36).substring(2, 9),
      name: newRuleName.trim() || newRuleContext.split(',')[0].trim().toUpperCase(),
      context: newRuleContext.trim(),
      preset_id: targetPreset,
    };

    setConfig((prev) => ({
      ...prev,
      context_rules: [...prev.context_rules, newRule],
    }));

    setNewRuleName('');
    setNewRuleContext('');
    setShowAddModal(false);
    showToast('info', 'Rule baru ditambahkan. Klik "Simpan Pengaturan" untuk mempermanenkan.');
  };

  const handleDeleteRule = (id: string) => {
    setConfig((prev) => ({
      ...prev,
      context_rules: prev.context_rules.filter((r) => r.id !== id),
    }));
  };

  const handleUpdateRule = (id: string, field: keyof PipelineRule, value: string) => {
    setConfig((prev) => ({
      ...prev,
      context_rules: prev.context_rules.map((r) =>
        r.id === id ? { ...r, [field]: value } : r
      ),
    }));
  };

  const handleTestMatch = async () => {
    setTestingMatch(true);
    try {
      const res = await pipelineApi.testMatch({
        title: testTitle,
        video_type: testVideoType,
      });
      setMatchResult(res);
    } catch (err: any) {
      showToast('error', 'Gagal menguji kecocokan rule: ' + (err.message || 'Error'));
    } finally {
      setTestingMatch(false);
    }
  };

  const handleTestWhatsApp = async () => {
    setTestingWa(true);
    try {
      const res = await pipelineApi.testWhatsApp(config.whatsapp_target_chat || undefined);
      showToast('success', res.message || 'Pesan tes berhasil dikirim ke WhatsApp!');
    } catch (err: any) {
      showToast('error', err.response?.data?.detail || 'Gagal mengirim pesan tes WhatsApp.');
    } finally {
      setTestingWa(false);
    }
  };

  const getScoreBadge = (score: number) => {
    if (score >= 85) {
      return { text: 'Viral Elite (Super Ketat)', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
    }
    if (score >= 75) {
      return { text: 'Sangat Direkomendasikan', color: 'bg-orange-50 text-orange-700 border-orange-200' };
    }
    if (score >= 65) {
      return { text: 'Standar Cukup Baik', color: 'bg-blue-50 text-blue-700 border-blue-200' };
    }
    return { text: 'Rendah (Hampir Semua Klip)', color: 'bg-stone-100 text-stone-700 border-stone-200' };
  };

  const scoreBadge = getScoreBadge(config.min_score);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <RefreshCw className="w-8 h-8 text-[#C2410C] animate-spin" />
        <p className="text-sm font-medium text-stone-500">Memuat konfigurasi pipeline...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl shadow-lg border flex items-center space-x-3 text-sm font-medium transition-all ${
            toast.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
              : toast.type === 'error'
              ? 'bg-rose-50 text-rose-900 border-rose-200'
              : 'bg-blue-50 text-blue-900 border-blue-200'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-stone-200 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-[#C2410C]/10 text-[#C2410C] flex items-center justify-center">
              <Workflow className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Pipeline Otomasi & Routing</h1>
              <p className="text-sm text-stone-500 mt-0.5">
                Konfigurasi alur kerja AI: batas skor klip, pemilihan preset cerdas berdasarkan konteks video, dan aksi pasca-render.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="px-3.5 py-2 text-stone-600 bg-white border border-stone-200 hover:bg-stone-50 rounded-lg text-sm font-medium transition-all flex items-center space-x-1.5 shadow-sm"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Muat Ulang</span>
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white rounded-lg text-sm font-semibold transition-all flex items-center space-x-2 shadow-sm disabled:opacity-50"
          >
            {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>{saving ? 'Menyimpan...' : 'Simpan Pengaturan'}</span>
          </button>
        </div>
      </div>

      {/* Integration Status Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* WhatsApp Card */}
        <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${config.whatsapp_paired ? 'bg-emerald-50 text-emerald-600' : 'bg-stone-100 text-stone-400'}`}>
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-400">WhatsApp Bot (WAHA)</div>
              <div className="text-sm font-semibold text-stone-800">
                {config.whatsapp_paired ? (config.whatsapp_paired_chat_name || 'Tersambung') : 'Belum Dipasangkan'}
              </div>
            </div>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${config.whatsapp_paired ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-100 text-stone-600'}`}>
            {config.whatsapp_paired ? 'Aktif' : 'Nonaktif'}
          </span>
        </div>

        {/* YouTube Card */}
        <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${config.youtube_connected ? 'bg-rose-50 text-rose-600' : 'bg-stone-100 text-stone-400'}`}>
              <PlaySquare className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-400">YouTube Studio</div>
              <div className="text-sm font-semibold text-stone-800">
                {config.youtube_connected ? 'Akun Terhubung' : 'Belum Terhubung'}
              </div>
            </div>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${config.youtube_connected ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-100 text-stone-600'}`}>
            {config.youtube_connected ? 'Siap' : 'Perlu Setup'}
          </span>
        </div>

        {/* Google Drive Card */}
        <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${config.gdrive_connected ? 'bg-blue-50 text-blue-600' : 'bg-stone-100 text-stone-400'}`}>
              <Cloud className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-400">Google Drive</div>
              <div className="text-sm font-semibold text-stone-800">
                {config.gdrive_connected ? 'Drive Siap' : 'Belum Terkonfigurasi'}
              </div>
            </div>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${config.gdrive_connected ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-100 text-stone-600'}`}>
            {config.gdrive_connected ? 'Siap' : 'Opsional'}
          </span>
        </div>
      </div>

      {/* SECTION 1: Minimum Score Filter */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <Sliders className="w-5 h-5 text-[#C2410C]" />
              <h2 className="text-lg font-bold text-stone-900">1. Ambang Batas Skor Minimum Auto-Clip ("SKOR")</h2>
            </div>
            <p className="text-sm text-stone-500 mt-1">
              Tentukan ambang skor minimal agar sebuah klip kandidat otomatis di-render menjadi video Shorts vertikal (9:16).
            </p>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${scoreBadge.color}`}>
            {scoreBadge.text}
          </span>
        </div>

        <div className="bg-stone-50 border border-stone-200/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-stone-700">
              Skor Minimum Komposit / Hook:
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="number"
                min="0"
                max="100"
                value={config.min_score}
                onChange={(e) =>
                  setConfig({ ...config, min_score: Math.max(0, Math.min(100, parseInt(e.target.value) || 0)) })
                }
                className="w-18 px-3 py-1.5 text-center font-mono font-bold text-lg text-stone-900 bg-white border border-stone-300 rounded-lg shadow-inner focus:outline-none focus:ring-2 focus:ring-[#C2410C]"
              />
              <span className="text-sm font-semibold text-stone-400">/ 100</span>
            </div>
          </div>

          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={config.min_score}
            onChange={(e) => setConfig({ ...config, min_score: parseInt(e.target.value) })}
            className="w-full h-2.5 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-[#C2410C]"
          />

          <div className="flex justify-between text-xs text-stone-400 font-mono">
            <span>0 (Semua Klip)</span>
            <span>60 (Longgar)</span>
            <span className="text-stone-700 font-bold">75 (Rekomendasi)</span>
            <span>85 (Ketat)</span>
            <span>100 (Sempurna)</span>
          </div>
        </div>

        <div className="flex items-start space-x-3 bg-amber-50/70 border border-amber-200/60 rounded-xl p-3.5 text-xs text-amber-900">
          <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <p>
            <strong>Cara Kerja:</strong> Ketika sebuah video baru selesai dipindai oleh AI, seluruh segmen yang memiliki skor di bawah <strong>{config.min_score}</strong> akan dilewati dari proses render otomatis. Klip-klip tersebut tidak akan hilang, melainkan tetap tersimpan di Clip Studio agar Anda dapat meninjaunya secara manual kapan saja.
          </p>
        </div>
      </div>

      {/* SECTION 2: Dynamic Context-to-Preset Rules */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <Layers className="w-5 h-5 text-[#C2410C]" />
              <h2 className="text-lg font-bold text-stone-900">2. Routing Konteks ke Preset ("Jika Konteks X, Gunakan Preset Y")</h2>
            </div>
            <p className="text-sm text-stone-500 mt-1">
              Atur kecocokan otomatis antara genre / kata kunci konteks video dengan Template & Framing Preset yang diinginkan.
            </p>
          </div>

          <button
            onClick={() => setShowAddModal(true)}
            className="px-3.5 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-sm font-semibold transition-all flex items-center space-x-1.5 shadow-sm self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            <span>Tambah Rule Konteks</span>
          </button>
        </div>

        {/* Rules Table / Cards */}
        <div className="space-y-3">
          {config.context_rules.length === 0 ? (
            <div className="text-center py-8 bg-stone-50 border border-dashed border-stone-200 rounded-xl text-stone-500 text-sm">
              Belum ada aturan konteks. Klik tombol "Tambah Rule Konteks" di atas untuk menambahkan.
            </div>
          ) : (
            config.context_rules.map((rule, idx) => {
              const selectedPreset = presets.find((p) => p.id === rule.preset_id);
              return (
                <div
                  key={rule.id}
                  className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 bg-stone-50/70 hover:bg-stone-50 border border-stone-200 rounded-xl transition-all"
                >
                  <div className="flex items-center space-x-3 w-full md:w-auto">
                    <span className="w-6 h-6 rounded-md bg-stone-200 text-stone-700 font-mono text-xs font-bold flex items-center justify-center shrink-0">
                      {idx + 1}
                    </span>
                    <div className="flex-1 md:w-56">
                      <input
                        type="text"
                        value={rule.name || ''}
                        onChange={(e) => handleUpdateRule(rule.id, 'name', e.target.value)}
                        placeholder="Nama Rule (cth: Gaming Streamer)"
                        className="text-sm font-semibold text-stone-900 bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 w-full focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
                      />
                    </div>
                  </div>

                  {/* Context Input */}
                  <div className="flex-1 w-full md:w-auto">
                    <div className="text-xs font-medium text-stone-500 mb-1">Jika Konteks / Kata Kunci mengandung:</div>
                    <input
                      type="text"
                      value={rule.context}
                      onChange={(e) => handleUpdateRule(rule.id, 'context', e.target.value)}
                      placeholder="cth: gaming, streamer, gameplay, wolverine"
                      className="text-xs font-mono text-stone-800 bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 w-full focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
                    />
                  </div>

                  <ArrowRight className="hidden md:block w-4 h-4 text-stone-400 shrink-0" />

                  {/* Preset Dropdown */}
                  <div className="w-full md:w-64">
                    <div className="text-xs font-medium text-stone-500 mb-1">Gunakan Preset:</div>
                    <select
                      value={rule.preset_id}
                      onChange={(e) => handleUpdateRule(rule.id, 'preset_id', e.target.value)}
                      className="text-xs font-semibold text-stone-900 bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 w-full focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
                    >
                      {presets.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.framing_layout || 'single'})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    title="Hapus Rule"
                    className="p-2 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all self-end md:self-center"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Fallback Preset Selection */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-stone-100/70 border border-stone-200 rounded-xl">
          <div>
            <div className="text-sm font-semibold text-stone-800">Preset Default (Fallback)</div>
            <div className="text-xs text-stone-500">
              Digunakan jika tidak ada satu pun rule di atas yang cocok dengan konteks video.
            </div>
          </div>
          <select
            value={config.default_preset_id || 'preset_tiktok_bold'}
            onChange={(e) => setConfig({ ...config, default_preset_id: e.target.value })}
            className="text-xs font-semibold text-stone-900 bg-white border border-stone-300 rounded-lg px-3 py-2 sm:w-64 focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Interactive Match Tester */}
        <div className="border-t border-stone-200 pt-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-stone-500">
            <Sparkles className="w-4 h-4 text-[#C2410C]" />
            <span>Uji Coba Kecocokan Rule (Live Match Tester)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
            <div className="sm:col-span-7">
              <input
                type="text"
                value={testTitle}
                onChange={(e) => setTestTitle(e.target.value)}
                placeholder="Judul Video untuk diuji..."
                className="text-xs text-stone-800 bg-white border border-stone-200 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
              />
            </div>
            <div className="sm:col-span-3">
              <select
                value={testVideoType}
                onChange={(e) => setTestVideoType(e.target.value)}
                className="text-xs text-stone-800 bg-white border border-stone-200 rounded-lg px-2.5 py-2 w-full focus:outline-none focus:ring-1 focus:ring-[#C2410C]"
              >
                <option value="gaming_streamer">gaming_streamer</option>
                <option value="podcast_talkshow">podcast_talkshow</option>
                <option value="edukasi_tech">edukasi_tech</option>
                <option value="motivasi_quotes">motivasi_quotes</option>
                <option value="horror_misteri">horror_misteri</option>
                <option value="komedi_meme">komedi_meme</option>
                <option value="bisnis_finance">bisnis_finance</option>
                <option value="storytelling_fakta">storytelling_fakta</option>
                <option value="umum">umum</option>
              </select>
            </div>
            <div className="sm:col-span-2">
              <button
                onClick={handleTestMatch}
                disabled={testingMatch}
                className="w-full px-3 py-2 bg-stone-800 hover:bg-stone-900 text-white rounded-lg text-xs font-semibold transition-all flex items-center justify-center space-x-1 disabled:opacity-50"
              >
                {testingMatch ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <PlaySquare className="w-3.5 h-3.5" />}
                <span>Uji Rule</span>
              </button>
            </div>
          </div>

          {matchResult && (
            <div className={`p-3 rounded-xl border text-xs flex items-start space-x-2.5 ${matchResult.matched ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-blue-50 border-blue-200 text-blue-900'}`}>
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />
              <div>
                <div className="font-bold">
                  Preset Terpilih: {matchResult.selected_preset_name || matchResult.selected_preset_id}
                </div>
                <div className="mt-0.5 opacity-90">{matchResult.match_reason}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* SECTION 3: Post-Render Actions */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
        <div>
          <div className="flex items-center space-x-2">
            <Workflow className="w-5 h-5 text-[#C2410C]" />
            <h2 className="text-lg font-bold text-stone-900">3. Aksi Pasca-Render ("Jika Sudah Jadi, Apa yang Dilakukan")</h2>
          </div>
          <p className="text-sm text-stone-500 mt-1">
            Pilih tindakan otomatis yang segera dieksekusi begitu video Shorts selesai dirender oleh worker.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* YouTube Upload Toggle */}
          <div
            onClick={() => setConfig({ ...config, auto_upload_youtube: !config.auto_upload_youtube })}
            className={`cursor-pointer p-4 rounded-xl border transition-all ${
              config.auto_upload_youtube
                ? 'bg-[#C2410C]/5 border-[#C2410C]/40 shadow-sm'
                : 'bg-stone-50/60 border-stone-200 hover:border-stone-300'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <PlaySquare className={`w-5 h-5 ${config.auto_upload_youtube ? 'text-[#C2410C]' : 'text-stone-400'}`} />
                <span className="font-semibold text-sm text-stone-900">Upload to YouTube</span>
              </div>
              <input
                type="checkbox"
                checked={config.auto_upload_youtube}
                onChange={() => {}}
                className="h-4 w-4 rounded border-stone-300 text-[#C2410C] focus:ring-[#C2410C] pointer-events-none"
              />
            </div>
            <p className="text-xs text-stone-500 mt-2 leading-relaxed">
              Otomatis upload ke YouTube Shorts dengan judul SEO, deskripsi, hashtag, dan thumbnail begitu video selesai dirender.
            </p>
          </div>

          {/* Google Drive Upload Toggle */}
          <div
            onClick={() => setConfig({ ...config, auto_upload_gdrive: !config.auto_upload_gdrive })}
            className={`cursor-pointer p-4 rounded-xl border transition-all ${
              config.auto_upload_gdrive
                ? 'bg-blue-50/40 border-blue-300 shadow-sm'
                : 'bg-stone-50/60 border-stone-200 hover:border-stone-300'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Cloud className={`w-5 h-5 ${config.auto_upload_gdrive ? 'text-blue-600' : 'text-stone-400'}`} />
                <span className="font-semibold text-sm text-stone-900">Upload to Google Drive</span>
              </div>
              <input
                type="checkbox"
                checked={config.auto_upload_gdrive}
                onChange={() => {}}
                className="h-4 w-4 rounded border-stone-300 text-blue-600 focus:ring-blue-600 pointer-events-none"
              />
            </div>
            <p className="text-xs text-stone-500 mt-2 leading-relaxed">
              Otomatis cadangkan berkas MP4 vertikal hasil render ke Google Drive folder yang telah dikonfigurasi.
            </p>
          </div>

          {/* WhatsApp Notification Toggle */}
          <div
            onClick={() => setConfig({ ...config, auto_notify_whatsapp: !config.auto_notify_whatsapp })}
            className={`cursor-pointer p-4 rounded-xl border transition-all ${
              config.auto_notify_whatsapp
                ? 'bg-emerald-50/40 border-emerald-300 shadow-sm'
                : 'bg-stone-50/60 border-stone-200 hover:border-stone-300'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <MessageSquare className={`w-5 h-5 ${config.auto_notify_whatsapp ? 'text-emerald-600' : 'text-stone-400'}`} />
                <span className="font-semibold text-sm text-stone-900">Notifikasi WhatsApp</span>
              </div>
              <input
                type="checkbox"
                checked={config.auto_notify_whatsapp}
                onChange={() => {}}
                className="h-4 w-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-600 pointer-events-none"
              />
            </div>
            <p className="text-xs text-stone-500 mt-2 leading-relaxed">
              Kirim laporan pesan WhatsApp konsolidasi berisi ringkasan dan tautan YouTube Shorts setelah seluruh klip selesai.
            </p>
          </div>
        </div>
      </div>

      {/* SECTION 4: WhatsApp Pipeline Settings & Consolidated Notifications */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <MessageSquare className="w-5 h-5 text-emerald-600" />
              <h2 className="text-lg font-bold text-stone-900">4. Pengaturan Notifikasi WhatsApp (Konsolidasi per Video)</h2>
            </div>
            <p className="text-sm text-stone-500 mt-1">
              Pesan dikirim secara konsolidasi (1 chat per video asli, bukan per klip) yang melampirkan seluruh link klip YouTube Shorts.
            </p>
          </div>
        </div>

        {/* Feature Highlight Callout */}
        <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-4 space-y-2">
          <div className="flex items-center space-x-2 text-emerald-900 font-bold text-sm">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Fitur Notifikasi Konsolidasi Aktif</span>
          </div>
          <p className="text-xs text-emerald-800 leading-relaxed">
            Untuk menjaga agar WhatsApp tidak spam dan tetap rapi, notifikasi <strong>tidak dikirim per klip</strong>. Sistem secara pintar menunggu hingga seluruh klip Shorts dari 1 video selesai di-upload ke YouTube, lalu merangkum semua link YouTube Shorts (misal: 3 klip) ke dalam <strong>1 chat WhatsApp terpadu</strong>.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-stone-700 uppercase tracking-wider mb-1.5">
              Nomor WhatsApp / Chat ID Tujuan (Opsional)
            </label>
            <input
              type="text"
              value={config.whatsapp_target_chat || ''}
              onChange={(e) => setConfig({ ...config, whatsapp_target_chat: e.target.value })}
              placeholder="Kosongkan untuk otomatis menggunakan chat yang dipasangkan di WAHA (cth: 6281234567890@c.us)"
              className="text-sm font-mono text-stone-800 bg-white border border-stone-300 rounded-lg px-3.5 py-2 w-full focus:outline-none focus:ring-2 focus:ring-[#C2410C]"
            />
            <p className="text-xs text-stone-400 mt-1">
              Format: nomor dengan kode negara (contoh <code>6281234567890@c.us</code>) atau ID grup WhatsApp.
            </p>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-stone-500">
              Pastikan bot WhatsApp (WAHA) telah terhubung sebelum melakukan pengujian.
            </div>
            <button
              onClick={handleTestWhatsApp}
              disabled={testingWa}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50"
            >
              {testingWa ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>Kirim Pesan Tes WhatsApp</span>
            </button>
          </div>
        </div>
      </div>

      {/* Modal Tambah Rule Baru */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-stone-200">
            <h3 className="text-base font-bold text-stone-900">Tambah Rule Konteks Baru</h3>
            <p className="text-xs text-stone-500">
              Buat aturan pemetaan dari genre/kata kunci konteks video ke preset tampilan tertentu.
            </p>

            <div className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Nama Aturan</label>
                <input
                  type="text"
                  value={newRuleName}
                  onChange={(e) => setNewRuleName(e.target.value)}
                  placeholder="Contoh: Wolverine Action Combat"
                  className="w-full text-sm bg-stone-50 border border-stone-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#C2410C]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">
                  Kata Kunci Konteks (pisahkan dengan koma)
                </label>
                <input
                  type="text"
                  value={newRuleContext}
                  onChange={(e) => setNewRuleContext(e.target.value)}
                  placeholder="Contoh: wolverine, combat, action, marvel"
                  className="w-full text-sm font-mono bg-stone-50 border border-stone-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#C2410C]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Target Preset Tampilan</label>
                <select
                  value={newRulePresetId}
                  onChange={(e) => setNewRulePresetId(e.target.value)}
                  className="w-full text-sm bg-stone-50 border border-stone-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#C2410C]"
                >
                  {presets.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.framing_layout || 'single'})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-4 border-t border-stone-100">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-stone-600 hover:bg-stone-100 rounded-lg text-xs font-semibold"
              >
                Batal
              </button>
              <button
                onClick={handleAddRule}
                className="px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white rounded-lg text-xs font-semibold"
              >
                Tambahkan Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PipelinePage;
