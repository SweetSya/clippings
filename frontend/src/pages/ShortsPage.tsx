import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Download,
  UploadCloud,
  CheckCircle2,
  Trash2,
  Play,
  ExternalLink,
  RefreshCw,
  Clock,
  ShieldCheck,
  LayoutGrid,
  List,
  Search,
  CheckSquare,
  Square,
  X,
  AlertCircle
} from 'lucide-react';
import { shortsApi, settingsApi, getMediaUrl } from '../services/api';
import { RenderedShort } from '../types';

export const ShortsPage: React.FC = () => {
  const [shorts, setShorts] = useState<RenderedShort[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [selectedVideoUrl, setSelectedVideoUrl] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // Layout mode & persistence
  const [layoutMode, setLayoutMode] = useState<'grid' | 'list'>('grid');

  // Filters & Search (Default to 'pending': show un-uploaded shorts first, hide uploaded by default)
  const [driveFilter, setDriveFilter] = useState<'all' | 'uploaded' | 'pending' | 'uploading'>('pending');
  const [searchQuery, setSearchQuery] = useState('');

  // Multi-select & Batch
  const [selectedShortIds, setSelectedShortIds] = useState<string[]>([]);
  const [batchProcessing, setBatchProcessing] = useState(false);

  const fetchShorts = async () => {
    try {
      const data = await shortsApi.list(1, 100);
      setShorts(data.items);
    } catch (e) {
      console.error('Failed to fetch shorts', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchShorts();
    // Load UI layout preference
    settingsApi.get().then((s) => {
      if (s.shorts_view_mode === 'grid' || s.shorts_view_mode === 'list') {
        setLayoutMode(s.shorts_view_mode);
      }
    }).catch(console.error);
  }, []);

  const handleToggleLayout = async (mode: 'grid' | 'list') => {
    setLayoutMode(mode);
    try {
      await settingsApi.updateUIPreferences({ shorts_view_mode: mode });
    } catch (e) {
      console.error('Failed to save shorts_view_mode preference', e);
    }
  };

  const handleUploadDrive = async (short: RenderedShort) => {
    if (short.is_drive_uploaded) {
      setInfoMessage('Klip ini sudah pernah diunggah ke Google Drive. Double-upload dicegah.');
      setTimeout(() => setInfoMessage(null), 4000);
      return;
    }

    setActionId(short.id);
    try {
      const res = await shortsApi.uploadDrive(short.id);
      if (res.status === 'ALREADY_UPLOADED') {
        setInfoMessage('Klip ini sudah pernah diunggah ke Google Drive. Double-upload dicegah.');
      } else {
        setInfoMessage('Proses upload Google Drive telah dimasukkan ke antrean worker.');
      }
      await fetchShorts();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Gagal memulai upload ke Google Drive.';
      alert(msg);
    } finally {
      setActionId(null);
      setTimeout(() => setInfoMessage(null), 4000);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Hapus video shorts ini dari storage lokal?')) return;
    try {
      await shortsApi.deleteShort(id);
      setShorts((prev) => prev.filter((s) => s.id !== id));
      setSelectedShortIds((prev) => prev.filter((i) => i !== id));
      if (selectedVideoUrl?.includes(id)) {
        setSelectedVideoUrl(null);
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal menghapus shorts.';
      alert(msg);
    }
  };

  const toggleSelect = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSelectedShortIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedShortIds.length === filteredShorts.length) {
      setSelectedShortIds([]);
    } else {
      setSelectedShortIds(filteredShorts.map((s) => s.id));
    }
  };

  const handleBatchUploadDrive = async () => {
    if (selectedShortIds.length === 0) return;
    setBatchProcessing(true);
    try {
      const res = await shortsApi.batchUploadDrive(selectedShortIds);
      setInfoMessage(res.message || `${res.success_count} shorts dijadwalkan untuk upload ke Drive.`);
      setSelectedShortIds([]);
      await fetchShorts();
    } catch (err: any) {
      alert(err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal memulai upload batch ke Google Drive.');
    } finally {
      setBatchProcessing(false);
      setTimeout(() => setInfoMessage(null), 5000);
    }
  };

  const handleBatchDeleteShorts = async () => {
    if (selectedShortIds.length === 0) return;
    if (!window.confirm(`Hapus ${selectedShortIds.length} video shorts terpilih dari storage lokal?`)) return;
    setBatchProcessing(true);
    try {
      const res = await shortsApi.batchDelete(selectedShortIds);
      setInfoMessage(res.message || `${res.success_count} shorts berhasil dihapus.`);
      setSelectedShortIds([]);
      await fetchShorts();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || 'Gagal menghapus batch shorts.';
      alert(msg);
    } finally {
      setBatchProcessing(false);
      setTimeout(() => setInfoMessage(null), 5000);
    }
  };

  const formatSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  // Filter calculations
  const uploadedCount = shorts.filter((s) => s.is_drive_uploaded || s.gdrive?.upload_status === 'SUCCESS').length;
  const uploadingCount = shorts.filter((s) => s.gdrive?.upload_status === 'UPLOADING').length;
  const pendingCount = shorts.filter((s) => !s.is_drive_uploaded && s.gdrive?.upload_status !== 'SUCCESS' && s.gdrive?.upload_status !== 'UPLOADING').length;

  const filteredShorts = shorts.filter((short) => {
    const isUploaded = short.is_drive_uploaded || short.gdrive?.upload_status === 'SUCCESS';
    const isUploading = short.gdrive?.upload_status === 'UPLOADING';

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (short.title || short.output_filename).toLowerCase().includes(q);
      if (!matchName) return false;
    }

    if (driveFilter === 'uploaded') return isUploaded;
    if (driveFilter === 'uploading') return isUploading;
    if (driveFilter === 'pending') return !isUploaded && !isUploading;
    return true;
  });

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-3xl text-[#1C1917]">Hasil Render Shorts (9:16)</h2>
          <p className="text-[#57534E] text-sm mt-1">
            Klip vertikal siap posting lengkap dengan subtitle karaoke burn-in dan opsi ekspor ke Google Drive.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {/* View Mode Toggle */}
          <div className="flex bg-[#F5F5F4] p-1 rounded-xl border border-[#D6D3D1]">
            <button
              onClick={() => handleToggleLayout('grid')}
              className={`p-1.5 rounded-lg transition-all ${
                layoutMode === 'grid'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
              title="Tampilan Grid"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleToggleLayout('list')}
              className={`p-1.5 rounded-lg transition-all ${
                layoutMode === 'list'
                  ? 'bg-white text-[#C2410C] shadow-xs'
                  : 'text-[#78716C] hover:text-[#1C1917]'
              }`}
              title="Tampilan List"
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          <button
            onClick={fetchShorts}
            className="p-2.5 bg-white border border-[#D6D3D1] hover:bg-[#E7E5E4] text-[#57534E] rounded-xl transition-all shadow-xs"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {infoMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-xl flex items-center space-x-2.5 shadow-sm animate-in fade-in duration-200">
          <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{infoMessage}</span>
        </div>
      )}

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#E7E5E4]">
        {/* Drive Filter Tabs */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDriveFilter('all')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              driveFilter === 'all'
                ? 'bg-[#C2410C] text-white shadow-xs'
                : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
            }`}
          >
            Semua Shorts ({shorts.length})
          </button>

          <button
            type="button"
            onClick={() => setDriveFilter('uploaded')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
              driveFilter === 'uploaded'
                ? 'bg-[#C2410C] text-white shadow-xs'
                : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Sudah di Drive ({uploadedCount})</span>
          </button>

          <button
            type="button"
            onClick={() => setDriveFilter('pending')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
              driveFilter === 'pending'
                ? 'bg-[#C2410C] text-white shadow-xs'
                : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#A8A29E]" />
            <span>Belum di Drive ({pendingCount})</span>
          </button>

          {uploadingCount > 0 && (
            <button
              type="button"
              onClick={() => setDriveFilter('uploading')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                driveFilter === 'uploading'
                  ? 'bg-[#C2410C] text-white shadow-xs'
                  : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
              }`}
            >
              <RefreshCw className="w-3 h-3 animate-spin text-amber-500" />
              <span>Sedang Upload ({uploadingCount})</span>
            </button>
          )}
        </div>

        {/* Search & Select All */}
        <div className="flex items-center space-x-3">
          {filteredShorts.length > 0 && (
            <button
              type="button"
              onClick={toggleSelectAll}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#57534E] text-xs font-semibold rounded-xl transition-all"
            >
              {selectedShortIds.length === filteredShorts.length && filteredShorts.length > 0 ? (
                <>
                  <CheckSquare className="w-3.5 h-3.5 text-[#C2410C]" />
                  <span>Batal Pilih</span>
                </>
              ) : (
                <>
                  <Square className="w-3.5 h-3.5" />
                  <span>Pilih Semua</span>
                </>
              )}
            </button>
          )}

          <div className="relative w-full sm:w-56">
            <Search className="w-4 h-4 text-[#A8A29E] absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari shorts..."
              className="w-full pl-9 pr-3 py-1.5 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-xs text-[#1C1917] focus:border-[#C2410C] outline-none"
            />
          </div>
        </div>
      </div>

      {/* Video Modal Player if selected */}
      {selectedVideoUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelectedVideoUrl(null)}
        >
          <div
            className="bg-[#1C1917] rounded-3xl p-3 max-w-sm w-full shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <video
              src={selectedVideoUrl}
              controls
              autoPlay
              className="w-full aspect-[9/16] rounded-2xl bg-black object-cover"
            />
            <button
              onClick={() => setSelectedVideoUrl(null)}
              className="w-full mt-3 py-2 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-xl transition-colors"
            >
              Tutup Pemutar
            </button>
          </div>
        </div>
      )}

      {/* Shorts Gallery */}
      {loading ? (
        <div className="text-center py-20 bg-white rounded-2xl border border-[#D6D3D1]">
          <RefreshCw className="w-8 h-8 animate-spin text-[#C2410C] mx-auto mb-3" />
          <p className="text-sm text-[#78716C]">Memuat galeri shorts...</p>
        </div>
      ) : filteredShorts.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-[#D6D3D1]">
          <Smartphone className="w-12 h-12 text-[#78716C]/50 mx-auto mb-3" />
          <h3 className="font-display font-semibold text-lg text-[#1C1917]">
            {searchQuery || driveFilter !== 'all' ? 'Tidak Ada Shorts yang Cocok' : 'Belum Ada Video Shorts'}
          </h3>
          <p className="text-sm text-[#57534E] max-w-sm mx-auto mt-1">
            {searchQuery || driveFilter !== 'all'
              ? 'Coba ganti kata kunci pencarian atau tab filter Google Drive.'
              : 'Gunakan Clip Studio untuk memilih momen menarik dan merender video vertikal 9:16 pertama Anda.'}
          </p>
        </div>
      ) : layoutMode === 'grid' ? (
        /* =========================================================================
           GRID VIEW (DEAD-CENTER PLAY BUTTON FIX)
           ========================================================================= */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredShorts.map((short) => {
            const isUploaded = short.is_drive_uploaded || short.gdrive?.upload_status === 'SUCCESS';
            const isSelected = selectedShortIds.includes(short.id);
            const driveLink = short.gdrive?.gdrive_web_view_link;

            return (
              <div
                key={short.id}
                className={`bg-white border rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-all flex flex-col justify-between relative ${
                  isSelected ? 'border-[#C2410C] ring-2 ring-[#C2410C]/20' : 'border-[#D6D3D1]'
                }`}
              >
                {/* 9:16 Aspect ratio video card header */}
                <div
                  onClick={() => {
                    if (short.render_status === 'COMPLETED') {
                      setSelectedVideoUrl(getMediaUrl(short.download_url));
                    }
                  }}
                  className="relative aspect-[9/16] bg-[#1C1917] cursor-pointer group overflow-hidden select-none"
                >
                  {short.render_status === 'COMPLETED' ? (
                    <>
                      <video
                        src={getMediaUrl(short.download_url)}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        muted
                      />
                      <div className="absolute inset-0 bg-black/30 group-hover:bg-black/10 transition-colors" />

                      {/* Dead-Center Play Button Overlay */}
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-12 h-12 rounded-full bg-white/80 text-[#1C1917] group-hover:bg-[#C2410C] group-hover:text-white flex items-center justify-center shadow-lg transition-all transform group-hover:scale-110 pointer-events-auto">
                          <Play className="w-5 h-5 ml-0.5 fill-current" />
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-center p-4">
                      <div className="space-y-2">
                        <RefreshCw className="w-8 h-8 text-[#C2410C] animate-spin mx-auto" />
                        <p className="text-xs font-semibold text-white">Sedang Merender ({short.render_progress || 0}%)</p>
                      </div>
                    </div>
                  )}

                  {/* Multi-Select Checkbox overlay */}
                  <div
                    onClick={(e) => toggleSelect(short.id, e)}
                    className="absolute top-3 right-3 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 backdrop-blur-xs text-white cursor-pointer z-10 transition-transform active:scale-95"
                  >
                    {isSelected ? (
                      <CheckSquare className="w-5 h-5 text-[#C2410C] fill-[#C2410C] bg-white rounded-xs" />
                    ) : (
                      <Square className="w-5 h-5 text-white/80" />
                    )}
                  </div>

                  {/* Anti-Double Upload Badge on thumbnail */}
                  {isUploaded && (
                    <div className="absolute top-3 left-3 px-2.5 py-1 bg-emerald-600/90 backdrop-blur-xs text-white text-[11px] font-semibold rounded-lg flex items-center space-x-1 shadow-sm">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Drive OK</span>
                    </div>
                  )}

                  <span className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/70 text-white text-[11px] font-mono rounded-md">
                    {formatSize(short.file_size_bytes)}
                  </span>
                </div>

                {/* Card Content */}
                <div className="p-4 space-y-3">
                  <h4 className="font-semibold text-sm text-[#1C1917] line-clamp-1">
                    {short.title || short.output_filename}
                  </h4>

                  {/* Google Drive Status pill */}
                  {isUploaded ? (
                    <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800">
                      <span className="flex items-center space-x-1 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Tersimpan di Drive</span>
                      </span>
                      {driveLink && (
                        <a
                          href={driveLink}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center space-x-0.5 text-emerald-700 hover:underline font-mono"
                        >
                          <span>Buka</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ) : short.gdrive?.upload_status === 'UPLOADING' ? (
                    <div className="p-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center space-x-1.5 animate-pulse">
                      <RefreshCw className="w-3 h-3 animate-spin text-amber-600" />
                      <span>Sedang Mengunggah ke Drive...</span>
                    </div>
                  ) : (
                    <div className="p-2 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl text-xs text-[#78716C] flex items-center space-x-1">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Menunggu upload ke Drive</span>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-[#F5F5F4] flex items-center justify-between gap-2">
                    <button
                      onClick={() => handleDelete(short.id)}
                      className="p-2 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
                      title="Hapus Shorts"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    <div className="flex space-x-2">
                      <a
                        href={getMediaUrl(short.download_url)}
                        download={short.output_filename}
                        className="px-3 py-1.5 bg-[#E7E5E4] hover:bg-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-lg transition-all flex items-center space-x-1"
                        title="Unduh MP4 ke Komputer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Unduh</span>
                      </a>

                      <button
                        onClick={() => handleUploadDrive(short)}
                        disabled={isUploaded || actionId === short.id || short.render_status !== 'COMPLETED'}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1 ${
                          isUploaded
                            ? 'bg-emerald-100 text-emerald-800 cursor-not-allowed border border-emerald-200'
                            : 'bg-[#C2410C] hover:bg-[#9A3412] text-white'
                        }`}
                        title={isUploaded ? 'Sudah diunggah ke Google Drive (Double-upload dicegah)' : 'Upload ke Google Drive'}
                      >
                        {isUploaded ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Diunggah</span>
                          </>
                        ) : (
                          <>
                            <UploadCloud className="w-3.5 h-3.5" />
                            <span>Ke Drive</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* =========================================================================
           LIST VIEW
           ========================================================================= */
        <div className="space-y-3">
          {filteredShorts.map((short) => {
            const isUploaded = short.is_drive_uploaded || short.gdrive?.upload_status === 'SUCCESS';
            const isSelected = selectedShortIds.includes(short.id);
            const driveLink = short.gdrive?.gdrive_web_view_link;

            return (
              <div
                key={short.id}
                className={`bg-white border rounded-2xl p-3 shadow-xs hover:shadow-md transition-all flex items-center justify-between gap-4 ${
                  isSelected ? 'border-[#C2410C] ring-2 ring-[#C2410C]/20' : 'border-[#D6D3D1]'
                }`}
              >
                {/* Left: Checkbox + Small 9:16 Video Thumbnail */}
                <div className="flex items-center space-x-3.5 min-w-0">
                  <div
                    onClick={(e) => toggleSelect(short.id, e)}
                    className="p-1 cursor-pointer text-[#78716C] hover:text-[#C2410C]"
                  >
                    {isSelected ? (
                      <CheckSquare className="w-5 h-5 text-[#C2410C]" />
                    ) : (
                      <Square className="w-5 h-5" />
                    )}
                  </div>

                  <div
                    onClick={() => {
                      if (short.render_status === 'COMPLETED') {
                        setSelectedVideoUrl(getMediaUrl(short.download_url));
                      }
                    }}
                    className="relative w-14 h-24 aspect-[9/16] bg-black rounded-xl overflow-hidden shrink-0 cursor-pointer group select-none shadow-xs"
                  >
                    {short.render_status === 'COMPLETED' ? (
                      <>
                        <video
                          src={getMediaUrl(short.download_url)}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          muted
                        />
                        <div className="absolute inset-0 bg-black/30 group-hover:bg-black/10 transition-colors" />
                        {/* Dead center play icon */}
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                          <div className="w-8 h-8 rounded-full bg-white/90 text-[#1C1917] group-hover:bg-[#C2410C] group-hover:text-white flex items-center justify-center shadow-md">
                            <Play className="w-3.5 h-3.5 ml-0.5 fill-current" />
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <RefreshCw className="w-4 h-4 text-[#C2410C] animate-spin" />
                      </div>
                    )}
                  </div>

                  {/* Title & Metadata */}
                  <div className="space-y-1 min-w-0">
                    <h4 className="font-semibold text-sm text-[#1C1917] truncate">
                      {short.title || short.output_filename}
                    </h4>
                    <div className="flex items-center space-x-3 text-xs text-[#78716C]">
                      <span>{formatSize(short.file_size_bytes)}</span>
                      <span>•</span>
                      <span>{new Date(short.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>

                {/* Right: Drive Status & Actions */}
                <div className="flex items-center space-x-3 shrink-0">
                  {/* Google Drive Status badge */}
                  {isUploaded ? (
                    <div className="flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Drive OK</span>
                      {driveLink && (
                        <a
                          href={driveLink}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-1 text-emerald-700 hover:underline"
                        >
                          <ExternalLink className="w-3 h-3 inline" />
                        </a>
                      )}
                    </div>
                  ) : short.gdrive?.upload_status === 'UPLOADING' ? (
                    <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                      <RefreshCw className="w-3 h-3 animate-spin text-amber-600" />
                      <span>Mengunggah...</span>
                    </div>
                  ) : (
                    <span className="text-xs text-[#A8A29E] hidden md:inline">Menunggu upload</span>
                  )}

                  <a
                    href={getMediaUrl(short.download_url)}
                    download={short.output_filename}
                    className="p-2 bg-[#F5F5F4] hover:bg-[#E7E5E4] text-[#1C1917] rounded-xl transition-all"
                    title="Unduh MP4"
                  >
                    <Download className="w-4 h-4" />
                  </a>

                  <button
                    onClick={() => handleUploadDrive(short)}
                    disabled={isUploaded || actionId === short.id || short.render_status !== 'COMPLETED'}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-xl shadow-xs transition-all flex items-center space-x-1.5 ${
                      isUploaded
                        ? 'bg-emerald-100 text-emerald-800 cursor-not-allowed border border-emerald-200'
                        : 'bg-[#C2410C] hover:bg-[#9A3412] text-white'
                    }`}
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Ke Drive</span>
                  </button>

                  <button
                    onClick={() => handleDelete(short.id)}
                    className="p-2 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-xl transition-colors"
                    title="Hapus Shorts"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* =========================================================================
          FLOATING ACTION BAR (BOTTOM-CENTER)
          Appears when >= 1 item is selected
          ========================================================================= */}
      {selectedShortIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-[#1C1917] text-white px-5 py-3 rounded-2xl shadow-2xl border border-stone-700 flex items-center space-x-4 animate-in fade-in slide-in-from-bottom-4 duration-200">
          <span className="text-xs font-semibold whitespace-nowrap">
            {selectedShortIds.length} shorts dipilih
          </span>

          <div className="h-4 w-px bg-white/20" />

          <button
            onClick={handleBatchUploadDrive}
            disabled={batchProcessing}
            className="px-3.5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
          >
            {batchProcessing ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <UploadCloud className="w-3.5 h-3.5" />
            )}
            <span>Upload ke Drive</span>
          </button>

          <button
            onClick={handleBatchDeleteShorts}
            disabled={batchProcessing}
            className="px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Hapus Terpilih</span>
          </button>

          <button
            onClick={() => setSelectedShortIds([])}
            className="p-1.5 text-white/70 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            title="Batalkan Pilihan"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
