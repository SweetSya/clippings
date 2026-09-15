import React, { useState, useEffect } from 'react';
import { Film, Play, Trash2, Sparkles, RefreshCw, AlertCircle, Clock, HardDrive, CheckCircle } from 'lucide-react';
import { videosApi, getMediaUrl } from '../services/api';
import { VideoItem } from '../types';

interface DashboardPageProps {
  onSelectVideo: (videoId: string) => void;
  onNavigateUpload: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onSelectVideo, onNavigateUpload }) => {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  const fetchVideos = async () => {
    try {
      const data = await videosApi.list(1, 50);
      setVideos(data.items);
    } catch (e) {
      console.error('Failed to load videos', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
    // Live polling every 3 seconds if any video is currently in progress
    const timer = setInterval(() => {
      if (videos.some((v) => ['UPLOADED', 'EXTRACTING_AUDIO', 'TRANSCRIBING', 'ANALYZING'].includes(v.status))) {
        fetchVideos();
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [videos]);

  const handleProcess = async (id: string) => {
    setActionId(id);
    try {
      await videosApi.process(id);
      await fetchVideos();
    } catch (e) {
      alert('Gagal memulai proses pipeline');
    } finally {
      setActionId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Yakin ingin menghapus video ini dan seluruh artefaknya?')) return;
    setActionId(id);
    try {
      await videosApi.deleteVideo(id);
      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (e) {
      alert('Gagal menghapus video');
    } finally {
      setActionId(null);
    }
  };

  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s < 10 ? '0' : ''}${s}`;
  };

  const formatSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle className="w-3 h-3" />
            <span>Klip Siap (Ready)</span>
          </span>
        );
      case 'EXTRACTING_AUDIO':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 animate-pulse">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Ekstraksi Audio...</span>
          </span>
        );
      case 'TRANSCRIBING':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 animate-pulse">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Transkripsi Whisper...</span>
          </span>
        );
      case 'ANALYZING':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 animate-pulse">
            <Sparkles className="w-3 h-3 animate-spin" />
            <span>Analisis AI Highlight...</span>
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">
            <AlertCircle className="w-3 h-3" />
            <span>Gagal</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-700">
            <span>Terupload</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-bold text-3xl text-[#1C1917]">Penyimpanan Video</h2>
          <p className="text-[#57534E] text-sm mt-1">
            Daftar video panjang yang tersimpan di storage lokal dan siap dikonversi menjadi klip vertikal.
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={fetchVideos}
            className="p-2.5 bg-white border border-[#D6D3D1] hover:bg-[#E7E5E4] text-[#57534E] rounded-xl transition-all shadow-xs"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onNavigateUpload}
            className="px-4 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-sm font-semibold rounded-xl shadow-md shadow-[#C2410C]/25 transition-all flex items-center space-x-2"
          >
            <Film className="w-4 h-4" />
            <span>Upload Video Baru</span>
          </button>
        </div>
      </div>

      {/* Videos Grid */}
      {loading ? (
        <div className="text-center py-20 bg-white rounded-2xl border border-[#D6D3D1]">
          <RefreshCw className="w-8 h-8 animate-spin text-[#C2410C] mx-auto mb-3" />
          <p className="text-sm text-[#78716C]">Memuat daftar video dari storage lokal...</p>
        </div>
      ) : videos.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-[#D6D3D1]">
          <Film className="w-12 h-12 text-[#78716C]/50 mx-auto mb-3" />
          <h3 className="font-display font-semibold text-lg text-[#1C1917]">Belum Ada Video</h3>
          <p className="text-sm text-[#57534E] max-w-sm mx-auto mt-1 mb-5">
            Unggah video panjang pertama Anda untuk memulai proses transkripsi Whisper dan pembuatan shorts.
          </p>
          <button
            onClick={onNavigateUpload}
            className="px-5 py-2.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-sm font-semibold rounded-xl transition-all shadow-md shadow-[#C2410C]/20"
          >
            Upload Sekarang
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => (
            <div
              key={video.id}
              className="bg-white border border-[#D6D3D1] rounded-2xl overflow-hidden hover:shadow-lg hover:border-[#C2410C]/50 transition-all duration-200 flex flex-col group"
            >
              {/* Thumbnail Container */}
              <div className="relative aspect-video bg-[#1C1917] overflow-hidden flex items-center justify-center">
                <img
                  src={getMediaUrl(video.thumbnail_url)}
                  alt={video.original_name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  onError={(e) => {
                    // Fallback to placeholder if thumbnail is still generating
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/70 backdrop-blur-xs text-white text-xs font-mono rounded-md">
                  {formatDuration(video.duration_seconds)}
                </span>
              </div>

              {/* Card Body */}
              <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    {getStatusBadge(video.status)}
                    <span className="text-xs text-[#78716C] font-mono flex items-center space-x-1">
                      <HardDrive className="w-3.5 h-3.5" />
                      <span>{formatSize(video.file_size_bytes)}</span>
                    </span>
                  </div>
                  <h4 className="font-semibold text-base text-[#1C1917] line-clamp-1" title={video.original_name}>
                    {video.original_name}
                  </h4>
                </div>

                {/* Actions */}
                <div className="pt-2 border-t border-[#F5F5F4] flex items-center justify-between">
                  <button
                    onClick={() => handleDelete(video.id)}
                    disabled={actionId === video.id}
                    className="p-2 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
                    title="Hapus Video"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>

                  <div className="flex space-x-2">
                    {video.status === 'READY' ? (
                      <button
                        onClick={() => onSelectVideo(video.id)}
                        className="px-3 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1.5"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Buka di Studio</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleProcess(video.id)}
                        disabled={actionId === video.id || ['EXTRACTING_AUDIO', 'TRANSCRIBING', 'ANALYZING'].includes(video.status)}
                        className="px-3 py-1.5 bg-[#E7E5E4] hover:bg-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-lg transition-all flex items-center space-x-1.5 disabled:opacity-50"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Proses Ulang</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
