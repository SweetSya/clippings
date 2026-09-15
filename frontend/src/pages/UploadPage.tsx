import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  Film,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Loader2,
  Youtube,
  Download,
  Search,
  Clock,
  User,
  Sparkles
} from 'lucide-react';
import { videosApi, settingsApi } from '../services/api';
import { YouTubeInfo } from '../types';

interface UploadPageProps {
  onUploadSuccess: (videoId: string) => void;
  onNavigateDashboard: () => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({ onUploadSuccess, onNavigateDashboard }) => {
  const [activeTab, setActiveTab] = useState<'local' | 'youtube'>('local');

  // Local upload state
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [uploadedVideoId, setUploadedVideoId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto Generate shorts toggle
  const [autoGenerate, setAutoGenerate] = useState(false);

  // YouTube downloader state
  const [ytUrl, setYtUrl] = useState('');
  const [ytQuality, setYtQuality] = useState('1080p');
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [downloadingYt, setDownloadingYt] = useState(false);
  const [ytInfo, setYtInfo] = useState<YouTubeInfo | null>(null);
  const [ytError, setYtError] = useState<string | null>(null);
  const lastFetchedUrlRef = useRef<string>('');

  useEffect(() => {
    settingsApi.get().then((s) => {
      if (s.yt_quality) {
        setYtQuality(s.yt_quality);
      }
    }).catch(() => {});
  }, []);

  // Debounced auto-check YouTube URL
  useEffect(() => {
    const cleanUrl = ytUrl.trim();
    if (!cleanUrl) {
      setYtInfo(null);
      setYtError(null);
      lastFetchedUrlRef.current = '';
      return;
    }

    const isYt = cleanUrl.includes('youtube.com/') || cleanUrl.includes('youtu.be/');
    if (!isYt && !cleanUrl.startsWith('http')) {
      return;
    }

    if (cleanUrl === lastFetchedUrlRef.current) {
      return;
    }

    const timer = setTimeout(async () => {
      lastFetchedUrlRef.current = cleanUrl;
      setFetchingInfo(true);
      setYtError(null);
      try {
        const info = await videosApi.getYoutubeInfo(cleanUrl);
        setYtInfo(info);
      } catch (err: any) {
        const msg = err.response?.data?.error?.message || 'Gagal mengambil informasi video YouTube. Pastikan link dapat diakses publik.';
        setYtError(msg);
      } finally {
        setFetchingInfo(false);
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [ytUrl]);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleSelectedFile = (selectedFile: File) => {
    setError(null);
    const validExts = ['.mp4', '.mkv', '.mov', '.avi', '.webm'];
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();
    if (!validExts.includes(ext)) {
      setError(`Format berkas ${ext} tidak didukung. Gunakan MP4, MKV, MOV, atau WEBM.`);
      return;
    }
    setFile(selectedFile);
  };

  const startUpload = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      const data = await videosApi.upload(file, autoGenerate, undefined, (pct) => {
        setProgress(pct);
      });
      setUploadedVideoId(data.video_id);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Gagal mengunggah berkas video ke storage lokal.';
      setError(msg);
    } finally {
      setUploading(false);
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

  const handleFetchYtInfo = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanUrl = ytUrl.trim();
    if (!cleanUrl) {
      setYtError('Masukkan URL YouTube yang valid.');
      return;
    }
    setFetchingInfo(true);
    setYtError(null);
    setYtInfo(null);
    try {
      const info = await videosApi.getYoutubeInfo(cleanUrl);
      setYtInfo(info);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Gagal mengambil informasi video YouTube. Pastikan link dapat diakses publik.';
      setYtError(msg);
    } finally {
      setFetchingInfo(false);
    }
  };

  const handleDownloadYt = async () => {
    const cleanUrl = ytUrl.trim();
    if (!cleanUrl) {
      setYtError('Masukkan URL YouTube terlebih dahulu.');
      return;
    }
    setDownloadingYt(true);
    setYtError(null);
    try {
      const res = await videosApi.downloadYoutube(cleanUrl, ytQuality, autoGenerate);
      setUploadedVideoId(res.video_id);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Gagal mengunduh video dari YouTube. Pastikan yt-dlp berjalan normal.';
      setYtError(msg);
    } finally {
      setDownloadingYt(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="font-display font-bold text-3xl text-[#1C1917]">Tambah Video Sumber</h2>
        <p className="text-[#57534E] text-sm mt-1">
          Pindahkan video podcast, webinar, atau rekaman panjang ke storage lokal untuk dianalisis dan dipotong menjadi video Shorts.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E7E5E4] bg-white rounded-t-2xl px-2 pt-2 shadow-sm">
        <button
          type="button"
          onClick={() => {
            setActiveTab('local');
            setError(null);
          }}
          className={`flex items-center space-x-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'local'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-[#78716C] hover:text-[#1C1917]'
          }`}
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Berkas Lokal</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('youtube');
            setYtError(null);
          }}
          className={`flex items-center space-x-2 px-5 py-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'youtube'
              ? 'border-[#C2410C] text-[#C2410C]'
              : 'border-transparent text-[#78716C] hover:text-[#1C1917]'
          }`}
        >
          <Youtube className="w-4 h-4 text-red-600" />
          <span>Download dari YouTube</span>
        </button>
      </div>

      {uploadedVideoId ? (
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-8 text-center space-y-5 shadow-sm">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-9 h-9" />
          </div>
          <div>
            <h3 className="font-display font-bold text-2xl text-[#1C1917]">
              {activeTab === 'youtube' ? 'Download Berhasil!' : 'Upload Berhasil!'}
            </h3>
            <p className="text-sm text-[#57534E] max-w-md mx-auto mt-1">
              Video telah tersimpan di folder <code className="font-mono text-xs bg-[#F5F5F4] px-1.5 py-0.5 rounded">storage/uploads/</code>. Pipeline ekstraksi audio & Whisper lokal otomatis berjalan di antrean.
            </p>
          </div>

          <div className="flex justify-center space-x-3 pt-2">
            <button
              onClick={onNavigateDashboard}
              className="px-5 py-2.5 bg-[#E7E5E4] hover:bg-[#D6D3D1] text-[#1C1917] font-semibold text-sm rounded-xl transition-all"
            >
              Lihat di Daftar Video
            </button>
            <button
              onClick={() => onUploadSuccess(uploadedVideoId)}
              className="px-6 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold text-sm rounded-xl shadow-md shadow-[#C2410C]/25 transition-all flex items-center space-x-2"
            >
              <span>Buka Clip Studio</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : activeTab === 'local' ? (
        /* Local Upload Tab */
        <div className="bg-white border border-[#D6D3D1] rounded-b-2xl p-6 shadow-sm space-y-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 ${
              dragOver
                ? 'border-[#C2410C] bg-[#C2410C]/5 scale-[1.01]'
                : file
                ? 'border-emerald-400 bg-emerald-50/40'
                : 'border-[#D6D3D1] hover:border-[#C2410C]/60 hover:bg-[#F5F5F4]/60'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/x-matroska,video/quicktime,video/webm,video/avi"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleSelectedFile(e.target.files[0]);
                }
              }}
            />

            <div className="w-14 h-14 bg-[#F5F5F4] text-[#C2410C] rounded-2xl flex items-center justify-center mx-auto mb-3 border border-[#D6D3D1]">
              {file ? <Film className="w-7 h-7 text-emerald-600" /> : <UploadCloud className="w-7 h-7" />}
            </div>

            {file ? (
              <div>
                <p className="font-semibold text-base text-[#1C1917]">{file.name}</p>
                <p className="text-xs text-[#78716C] font-mono mt-0.5">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Siap diupload
                </p>
              </div>
            ) : (
              <div>
                <p className="font-semibold text-base text-[#1C1917]">
                  Tarik dan letakkan berkas video di sini
                </p>
                <p className="text-xs text-[#78716C] mt-1">atau klik untuk memilih dari komputer</p>
                <p className="text-[11px] text-[#A8A29E] font-mono mt-3">
                  Mendukung MP4, MKV, MOV, WEBM (Maks 2048 MB)
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {uploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold text-[#57534E]">
                <span className="flex items-center space-x-1.5">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C2410C]" />
                  <span>Mengunggah berkas ke storage...</span>
                </span>
                <span className="font-mono">{progress}%</span>
              </div>
              <div className="w-full bg-[#E7E5E4] h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-[#C2410C] h-full transition-all duration-200 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Auto Generate Toggle */}
          <div className="p-3.5 bg-orange-50/70 border border-orange-200/80 rounded-xl flex items-start space-x-3">
            <input
              type="checkbox"
              id="localAutoGenerate"
              checked={autoGenerate}
              onChange={(e) => setAutoGenerate(e.target.checked)}
              className="mt-1 w-4 h-4 rounded text-[#C2410C] focus:ring-[#C2410C] accent-[#C2410C] cursor-pointer"
            />
            <label htmlFor="localAutoGenerate" className="cursor-pointer text-left">
              <span className="text-xs font-bold text-[#1C1917] flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Otomatis Render Semua Video Singkat (Auto-Generate Shorts)</span>
              </span>
              <p className="text-[11px] text-[#57534E] mt-0.5">
                Secara otomatis menghasilkan semua video singkat (format 9:16 dengan subtitle) setelah proses transkripsi & kurasi AI selesai.
              </p>
            </label>
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <button
              onClick={() => {
                setFile(null);
                setError(null);
              }}
              disabled={uploading || !file}
              className="px-4 py-2.5 text-sm font-semibold text-[#57534E] hover:text-[#1C1917] hover:bg-[#E7E5E4] rounded-xl transition-colors disabled:opacity-40"
            >
              Batal
            </button>
            <button
              onClick={startUpload}
              disabled={!file || uploading}
              className="px-6 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold text-sm rounded-xl shadow-md shadow-[#C2410C]/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Mengunggah...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Mulai Upload & Proses</span>
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* YouTube Downloader Tab */
        <div className="bg-white border border-[#D6D3D1] rounded-b-2xl p-6 shadow-sm space-y-6">
          <form onSubmit={handleFetchYtInfo} className="space-y-3">
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C]">
              URL Video YouTube
            </label>
            <div className="flex space-x-2">
              <div className="relative flex-1">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-red-500">
                  <Youtube className="w-5 h-5" />
                </div>
                <input
                  type="url"
                  value={ytUrl}
                  onChange={(e) => setYtUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... atau https://youtu.be/..."
                  className="w-full pl-10 pr-10 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm focus:outline-none focus:border-[#C2410C] text-[#1C1917]"
                  disabled={downloadingYt}
                />
                {fetchingInfo && (
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-[#C2410C]">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                )}
              </div>
              <button
                type="submit"
                disabled={fetchingInfo || downloadingYt || !ytUrl.trim()}
                className="px-4 py-2.5 bg-[#E7E5E4] hover:bg-[#D6D3D1] text-[#1C1917] text-sm font-semibold rounded-xl transition-all disabled:opacity-50 flex items-center space-x-2"
              >
                {fetchingInfo ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Cek...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    <span>Ambil Info</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-[11px] text-[#A8A29E]">
              Masukkan link video YouTube publik. Video akan diunduh dengan yt-dlp secara lokal dan langsung dimasukkan ke pipeline Shorts.
            </p>
          </form>

          {/* Quality Selector */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C]">
              Kualitas Video
            </label>
            <select
              value={ytQuality}
              onChange={(e) => setYtQuality(e.target.value)}
              disabled={downloadingYt}
              className="w-full px-3 py-2.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm focus:outline-none focus:border-[#C2410C] text-[#1C1917]"
            >
              <option value="1080p">1080p Full HD (Disarankan, jika tersedia)</option>
              <option value="720p">720p HD (Unduhan lebih cepat)</option>
              <option value="best">Kualitas Tertinggi (Best Available)</option>
            </select>
          </div>

          {/* YouTube Info Preview Card */}
          {ytInfo && (
            <div className="bg-[#FAF8F5] border border-[#E7E5E4] rounded-2xl p-4 flex flex-col sm:flex-row gap-4 items-start shadow-inner">
              {ytInfo.thumbnail_url && (
                <img
                  src={ytInfo.thumbnail_url}
                  alt={ytInfo.title}
                  className="w-full sm:w-44 h-28 object-cover rounded-xl border border-[#D6D3D1] shrink-0"
                />
              )}
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center space-x-1 text-xs text-[#C2410C] font-semibold">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Siap Diproses</span>
                </div>
                <h4 className="text-sm font-bold text-[#1C1917] line-clamp-2 leading-tight">
                  {ytInfo.title}
                </h4>
                <div className="flex flex-wrap items-center gap-3 text-xs text-[#78716C]">
                  {ytInfo.channel && (
                    <span className="flex items-center space-x-1">
                      <User className="w-3 h-3" />
                      <span>{ytInfo.channel}</span>
                    </span>
                  )}
                  {ytInfo.duration_seconds > 0 && (
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{formatDuration(ytInfo.duration_seconds)}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {ytError && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{ytError}</span>
            </div>
          )}

          {downloadingYt && (
            <div className="space-y-2 p-4 bg-orange-50/60 border border-orange-200 rounded-xl">
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#C2410C]">
                <Loader2 className="w-4 h-4 animate-spin text-[#C2410C]" />
                <span>Sedang mengunduh video dari YouTube secara lokal (yt-dlp)...</span>
              </div>
              <p className="text-[11px] text-[#78716C]">
                Proses unduh dan penggabungan audio Full HD memerlukan waktu tergantung durasi video dan kecepatan koneksi Anda.
              </p>
            </div>
          )}

          {/* Auto Generate Toggle */}
          <div className="p-3.5 bg-orange-50/70 border border-orange-200/80 rounded-xl flex items-start space-x-3">
            <input
              type="checkbox"
              id="ytAutoGenerate"
              checked={autoGenerate}
              onChange={(e) => setAutoGenerate(e.target.checked)}
              disabled={downloadingYt}
              className="mt-1 w-4 h-4 rounded text-[#C2410C] focus:ring-[#C2410C] accent-[#C2410C] cursor-pointer"
            />
            <label htmlFor="ytAutoGenerate" className="cursor-pointer text-left">
              <span className="text-xs font-bold text-[#1C1917] flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Otomatis Render Semua Video Singkat (Auto-Generate Shorts)</span>
              </span>
              <p className="text-[11px] text-[#57534E] mt-0.5">
                Setelah YouTube selesai diunduh & dianalisis oleh AI, sistem akan otomatis merender semua klip menjadi shorts 9:16 di antrean.
              </p>
            </label>
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={() => {
                setYtUrl('');
                setYtInfo(null);
                setYtError(null);
              }}
              disabled={downloadingYt || (!ytUrl && !ytInfo)}
              className="px-4 py-2.5 text-sm font-semibold text-[#57534E] hover:text-[#1C1917] hover:bg-[#E7E5E4] rounded-xl transition-colors disabled:opacity-40"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={handleDownloadYt}
              disabled={downloadingYt || !ytUrl.trim()}
              className="px-6 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold text-sm rounded-xl shadow-md shadow-[#C2410C]/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {downloadingYt ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Mengunduh Video...</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>Download & Proses Video</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
