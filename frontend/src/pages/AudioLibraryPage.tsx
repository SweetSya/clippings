import React, { useEffect, useRef, useState } from 'react';
import {
  Music,
  UploadCloud,
  Youtube,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  HardDrive,
  Play,
  RefreshCw,
  Check,
  X,
} from 'lucide-react';
import { audioApi, sfxApi, SFXTrack } from '../services/api';
import { AudioTrack } from '../types';

interface AudioLibraryPageProps {
  onUseAsBgm: (trackId: string) => void;
}

const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg'];

const formatDuration = (seconds: number) => {
  if (!seconds) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const formatSize = (bytes: number) => {
  if (!bytes) return '0 MB';
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const AudioLibraryPage: React.FC<AudioLibraryPageProps> = ({ onUseAsBgm }) => {
  const [tracks, setTracks] = useState<AudioTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [ytUrl, setYtUrl] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [libTab, setLibTab] = useState<'bgm' | 'sfx'>('bgm');
  const [sfxList, setSfxList] = useState<SFXTrack[]>([]);
  const [sfxLoading, setSfxLoading] = useState(false);
  const [sfxUploading, setSfxUploading] = useState(false);
  const sfxInputRef = useRef<HTMLInputElement | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchTracks = async () => {
    setLoading(true);
    try {
      const data = await audioApi.list();
      setTracks(data);
      if (data.length > 0 && !data.some((t) => t.id === selectedTrackId)) {
        setSelectedTrackId(data[0].id);
      }
    } catch (err) {
      console.error('Gagal memuat pustaka audio', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTracks();
    fetchSfx();
  }, []);

  const fetchSfx = async () => {
    setSfxLoading(true);
    try {
      setSfxList(await sfxApi.list());
    } catch (err) {
      console.error('Gagal memuat SFX', err);
    } finally {
      setSfxLoading(false);
    }
  };

  const handleSfxPicked = async (file: File) => {
    const ext = `.${file.name.split('.').pop()?.toLowerCase() || ''}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showNotification('error', `Format ${ext} tidak didukung.`);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showNotification('error', 'Ukuran SFX melebihi 5MB.');
      return;
    }
    setSfxUploading(true);
    try {
      const track = await sfxApi.upload(file);
      showNotification('success', `"${track.title}" ditambahkan ke library SFX.`);
      await fetchSfx();
    } catch (err: any) {
      showNotification('error', err.response?.data?.detail || 'Gagal mengunggah SFX.');
    } finally {
      setSfxUploading(false);
      if (sfxInputRef.current) sfxInputRef.current.value = '';
    }
  };

  const handleDeleteSfx = async (track: SFXTrack) => {
    if (!window.confirm(`Hapus SFX "${track.title}"?`)) return;
    try {
      await sfxApi.remove(track.id);
      showNotification('success', `"${track.title}" dihapus.`);
      await fetchSfx();
    } catch (err: any) {
      showNotification('error', 'Gagal menghapus SFX.');
    }
  };

  const handleFilePicked = async (file: File) => {
    const ext = `.${file.name.split('.').pop()?.toLowerCase() || ''}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showNotification('error', `Format ${ext} tidak didukung. Gunakan ${ALLOWED_EXTENSIONS.join(', ')}.`);
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    try {
      const track = await audioApi.upload(file, undefined, setUploadProgress);
      showNotification('success', `"${track.title}" berhasil ditambahkan ke pustaka audio.`);
      await fetchTracks();
      setSelectedTrackId(track.id);
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal mengunggah audio.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleYoutubeDownload = async () => {
    const url = ytUrl.trim();
    if (!url) return;

    setDownloading(true);
    try {
      const track = await audioApi.downloadYoutube(url);
      showNotification('success', `"${track.title}" berhasil diunduh dari YouTube.`);
      setYtUrl('');
      await fetchTracks();
      setSelectedTrackId(track.id);
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal mengunduh audio YouTube.');
    } finally {
      setDownloading(false);
    }
  };

  const handleDelete = async (track: AudioTrack) => {
    try {
      await audioApi.remove(track.id);
      showNotification('success', `"${track.title}" dihapus dari pustaka.`);
      await fetchTracks();
    } catch (err: any) {
      showNotification('error', err.response?.data?.error?.message || 'Gagal menghapus trek audio.');
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Notification Banner (Floating Top Overlay) */}
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
            <span className="text-sm font-medium tracking-tight text-white/95">{notification.message}</span>
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

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display font-bold text-2xl text-[#1C1917] flex items-center space-x-2">
            <Music className="w-6 h-6 text-[#C2410C]" />
            <span>Audio Library</span>
          </h2>
          <p className="text-sm text-[#57534E] mt-1">
            Kelola musik latar (BGM) untuk klip Anda. Unggah berkas sendiri atau ambil audionya langsung dari YouTube.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchTracks}
          className="p-2 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-xl text-[#57534E] transition-colors"
          title="Muat ulang daftar"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Tab switcher */}
      <div className="flex space-x-2">
        {[
          { id: 'bgm', label: '🎵 Musik Latar (BGM)' },
          { id: 'sfx', label: '🔔 Sound Effects' },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setLibTab(t.id as any)}
            className={`px-4 py-2 text-xs font-bold rounded-xl transition-all ${
              libTab === t.id ? 'bg-[#C2410C] text-white shadow-sm' : 'bg-white text-[#57534E] border border-[#D6D3D1] hover:bg-[#F5F5F4]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {libTab === 'sfx' ? (
        <div className="space-y-4">
          <div className="bg-white border border-[#D6D3D1] rounded-2xl p-5 space-y-3">
            <h3 className="font-semibold text-sm text-[#1C1917]">Unggah Sound Effect (maks 5MB)</h3>
            <input ref={sfxInputRef} type="file" accept={ALLOWED_EXTENSIONS.join(',')} className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleSfxPicked(f); }} />
            <button type="button" onClick={() => sfxInputRef.current?.click()} disabled={sfxUploading} className="w-full py-6 border-2 border-dashed border-[#D6D3D1] hover:border-[#C2410C] rounded-xl text-center transition-colors disabled:opacity-50">
              {sfxUploading ? (
                <span className="flex items-center justify-center space-x-2 text-sm text-[#C2410C] font-semibold">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Mengunggah...</span>
                </span>
              ) : (
                <span className="text-xs text-[#78716C]">Klik untuk memilih berkas<br /><span className="font-mono text-[11px]">{ALLOWED_EXTENSIONS.join('  ')}</span></span>
              )}
            </button>
            <p className="text-[11px] text-[#78716C]">SFX dipakai sebagai penanda momen di Clip Studio (tab Audio) atau otomatis saat skor hook tinggi.</p>
          </div>

          <div className="space-y-3">
            <h3 className="font-semibold text-base text-[#1C1917]">Sound Effects ({sfxList.length})</h3>
            {sfxLoading ? (
              <div className="bg-white border border-[#D6D3D1] rounded-2xl p-12 text-center">
                <Loader2 className="w-6 h-6 animate-spin text-[#C2410C] mx-auto" />
              </div>
            ) : sfxList.length === 0 ? (
              <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-12 text-center space-y-2">
                <p className="text-sm text-[#78716C]">Belum ada SFX. Unggah whoosh, ding, applause favoritmu.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {sfxList.map((sfx) => (
                  <div key={sfx.id} className="bg-white border border-[#D6D3D1] rounded-2xl p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <h4 className="font-semibold text-sm text-[#1C1917] truncate">🔔 {sfx.title}</h4>
                        <div className="flex items-center space-x-3 mt-1.5 text-[11px] text-[#78716C] font-mono">
                          <span className="flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>{formatDuration(sfx.duration_seconds)}</span>
                          </span>
                          <span>•</span>
                          <span>{formatSize(sfx.file_size_bytes)}</span>
                        </div>
                        <audio controls preload="none" src={sfxApi.getStreamUrl(sfx)} className="w-full mt-3 h-8" />
                      </div>
                      <button type="button" onClick={() => handleDeleteSfx(sfx)} className="p-1.5 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors shrink-0" title="Hapus SFX">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
      <>
      {/* Add methods */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Upload file */}
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-5 space-y-3">
          <div className="flex items-center space-x-2">
            <UploadCloud className="w-4 h-4 text-[#C2410C]" />
            <h3 className="font-semibold text-sm text-[#1C1917]">Unggah Berkas Audio</h3>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(',')}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFilePicked(file);
            }}
          />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full py-6 border-2 border-dashed border-[#D6D3D1] hover:border-[#C2410C] rounded-xl text-center transition-colors disabled:opacity-50"
          >
            {uploading ? (
              <span className="flex items-center justify-center space-x-2 text-sm text-[#C2410C] font-semibold">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Mengunggah... {uploadProgress}%</span>
              </span>
            ) : (
              <span className="text-xs text-[#78716C]">
                Klik untuk memilih berkas
                <br />
                <span className="font-mono text-[11px]">{ALLOWED_EXTENSIONS.join('  ')}</span>
              </span>
            )}
          </button>

          {uploading && (
            <div className="w-full h-1.5 bg-[#E7E5E4] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#C2410C] transition-all duration-300 rounded-full"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}
        </div>

        {/* YouTube */}
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-5 space-y-3">
          <div className="flex items-center space-x-2">
            <Youtube className="w-4 h-4 text-[#C2410C]" />
            <h3 className="font-semibold text-sm text-[#1C1917]">Ambil Audio dari YouTube</h3>
          </div>

          <input
            type="text"
            value={ytUrl}
            onChange={(e) => setYtUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm text-[#1C1917] focus:border-[#C2410C] outline-none"
          />

          <button
            type="button"
            onClick={handleYoutubeDownload}
            disabled={downloading || !ytUrl.trim()}
            className="w-full py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {downloading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Mengunduh & mengonversi ke MP3...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Unduh sebagai MP3</span>
              </>
            )}
          </button>

          <p className="text-[11px] text-[#78716C]">
            Proses ini memerlukan waktu sesuai panjang video dan membutuhkan koneksi internet.
          </p>
        </div>
      </div>

      {/* Track list */}
      <div className="space-y-3">
        <h3 className="font-semibold text-base text-[#1C1917]">
          Pustaka Audio ({tracks.length})
        </h3>

        {loading ? (
          <div className="bg-white border border-[#D6D3D1] rounded-2xl p-12 text-center">
            <Loader2 className="w-6 h-6 animate-spin text-[#C2410C] mx-auto" />
          </div>
        ) : tracks.length === 0 ? (
          <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-12 text-center space-y-2">
            <Music className="w-8 h-8 text-[#D6D3D1] mx-auto" />
            <p className="text-sm text-[#78716C]">Belum ada trek audio di pustaka.</p>
            <p className="text-xs text-[#A8A29E]">Unggah berkas atau ambil dari YouTube untuk mulai menambahkan musik latar.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tracks.map((track) => {
              const isSelected = selectedTrackId === track.id;
              return (
                <div
                  key={track.id}
                  className={`bg-white border rounded-2xl p-4 transition-all ${
                    isSelected ? 'border-[#C2410C] border-l-4 shadow-sm' : 'border-[#D6D3D1] hover:border-[#78716C]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center space-x-2 flex-wrap">
                        <h4 className="font-semibold text-sm text-[#1C1917] truncate">{track.title}</h4>
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded-md uppercase tracking-wide ${
                            track.source_type === 'youtube'
                              ? 'bg-red-50 text-red-700'
                              : 'bg-[#C2410C]/10 text-[#C2410C]'
                          }`}
                        >
                          {track.source_type}
                        </span>
                      </div>

                      <div className="flex items-center space-x-3 mt-1.5 text-[11px] text-[#78716C] font-mono">
                        <span className="flex items-center space-x-1">
                          <Clock className="w-3 h-3" />
                          <span>{formatDuration(track.duration_seconds)}</span>
                        </span>
                        <span>•</span>
                        <span className="flex items-center space-x-1">
                          <HardDrive className="w-3 h-3" />
                          <span>{formatSize(track.file_size_bytes)}</span>
                        </span>
                      </div>

                      <audio
                        controls
                        preload="none"
                        src={audioApi.getStreamUrl(track)}
                        className="w-full mt-3 h-8"
                      />
                    </div>

                    <div className="flex flex-col items-end space-y-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          onUseAsBgm(track.id);
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 ${
                          isSelected
                            ? 'bg-[#C2410C] text-white'
                            : 'bg-[#C2410C]/10 text-[#C2410C] hover:bg-[#C2410C] hover:text-white'
                        }`}
                        title="Pakai trek ini sebagai musik latar di Clip Studio"
                      >
                        {isSelected ? <Check className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                        <span>Pakai sebagai BGM</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleDelete(track)}
                        className="p-1.5 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
                        title="Hapus dari pustaka"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
};

export default AudioLibraryPage;
