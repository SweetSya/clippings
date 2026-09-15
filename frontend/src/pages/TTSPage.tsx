import React, { useState, useEffect } from 'react';
import { Mic, Play, Pause, Download, Volume2, Sparkles, Clock, Loader2, CheckCircle } from 'lucide-react';
import { ttsApi, getMediaUrl } from '../services/api';
import { TTSItem, VoiceItem } from '../types';

export const TTSPage: React.FC = () => {
  const [text, setText] = useState('');
  const [voices, setVoices] = useState<VoiceItem[]>([]);
  const [selectedVoice, setSelectedVoice] = useState('id-ID-ArdiNeural');
  const [rate, setRate] = useState('+0%');
  const [generating, setGenerating] = useState(false);
  const [history, setHistory] = useState<TTSItem[]>([]);
  const [activeAudio, setActiveAudio] = useState<string | null>(null);

  useEffect(() => {
    // Load voices & history
    ttsApi.getVoices().then(setVoices).catch(console.error);
    ttsApi.getHistory().then(setHistory).catch(console.error);
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;

    setGenerating(true);
    try {
      const item = await ttsApi.generate(text.trim(), selectedVoice, rate);
      setHistory((prev) => [item, ...prev]);
      setActiveAudio(item.audio_url);
    } catch (err: any) {
      alert('Gagal membuat audio Text-to-Speech: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="font-display font-bold text-3xl text-[#1C1917]">Text-to-Speech Studio</h2>
        <p className="text-[#57534E] text-sm mt-1">
          Hasilkan narasi suara alami secara instan menggunakan AI Text-to-Speech lokal untuk mengisi suara klip video Anda.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Input Form (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-[#D6D3D1] rounded-2xl p-6 shadow-sm space-y-5">
          <form onSubmit={handleGenerate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5">
                Teks Narasi / Script
              </label>
              <textarea
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Ketik atau tempel teks yang ingin diubah menjadi suara narasi di sini..."
                className="w-full p-3.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm text-[#1C1917] focus:border-[#C2410C] focus:bg-white outline-none resize-none transition-all"
                required
              />
              <div className="flex justify-between items-center text-xs text-[#78716C] mt-1 font-mono">
                <span>{text.length} karakter</span>
                <span>{text.split(/\s+/).filter(Boolean).length} kata</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5">
                  Pilihan Suara (Voice)
                </label>
                <select
                  value={selectedVoice}
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1.5">
                  Kecepatan Bicara
                </label>
                <select
                  value={rate}
                  onChange={(e) => setRate(e.target.value)}
                  className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
                >
                  <option value="-20%">Lambat (-20%)</option>
                  <option value="-10%">Agak Lambat (-10%)</option>
                  <option value="+0%">Normal (Default)</option>
                  <option value="+10%">Agak Cepat (+10%)</option>
                  <option value="+20%">Cepat (+20%)</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={generating || !text.trim()}
              className="w-full py-3 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold rounded-xl shadow-md shadow-[#C2410C]/25 transition-all disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Membuat Audio Narasi...</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-4 h-4" />
                  <span>Generate Audio Narasi</span>
                </>
              )}
            </button>
          </form>

          {/* Player for recently generated */}
          {activeAudio && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-800">
                <span className="flex items-center space-x-1">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Audio Berhasil Dibuat:</span>
                </span>
                <a
                  href={getMediaUrl(activeAudio)}
                  download="narasi.mp3"
                  className="flex items-center space-x-1 text-emerald-700 hover:underline font-mono"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download MP3</span>
                </a>
              </div>
              <audio controls src={getMediaUrl(activeAudio)} autoPlay className="w-full" />
            </div>
          )}
        </div>

        {/* Right: History List (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-[#D6D3D1] rounded-2xl p-5 shadow-sm space-y-4">
          <h3 className="font-semibold text-sm text-[#1C1917] flex items-center space-x-2">
            <Clock className="w-4 h-4 text-[#C2410C]" />
            <span>Riwayat Narasi ({history.length})</span>
          </h3>

          {history.length === 0 ? (
            <div className="text-center py-12 text-[#78716C] text-xs">
              Belum ada riwayat narasi suara.
            </div>
          ) : (
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="p-3 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl space-y-2 text-left hover:border-[#D6D3D1] transition-all"
                >
                  <p className="text-xs text-[#1C1917] font-medium line-clamp-2">
                    "{item.text}"
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-[#78716C] font-mono">
                    <span>{item.voice.split('-')[2] || item.voice}</span>
                    <span>{item.duration_seconds.toFixed(1)}s</span>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <button
                      onClick={() => setActiveAudio(item.audio_url)}
                      className="px-2.5 py-1 bg-white hover:bg-[#E7E5E4] border border-[#D6D3D1] text-[11px] font-semibold text-[#1C1917] rounded-lg transition-colors flex items-center space-x-1"
                    >
                      <Play className="w-3 h-3 fill-current" />
                      <span>Dengarkan</span>
                    </button>
                    <a
                      href={getMediaUrl(item.audio_url)}
                      download={`narasi_${item.id}.mp3`}
                      className="p-1 text-[#78716C] hover:text-[#C2410C] transition-colors"
                      title="Unduh MP3"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
