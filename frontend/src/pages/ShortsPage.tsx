import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Download,
  UploadCloud,
  Youtube,
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
  AlertCircle,
  Image as ImageIcon,
  Users,
  Upload
} from 'lucide-react';
import { shortsApi, settingsApi, clipsApi, getMediaUrl } from '../services/api';
import { RenderedShort } from '../types';

const YouTubeUploadModal: React.FC<{
  short: RenderedShort;
  onClose: () => void;
  onUploaded: () => void;
}> = ({ short, onClose, onUploaded }) => {
  const [titles, setTitles] = useState<string[]>([(short.title || short.output_filename).slice(0, 100)]);
  const [title, setTitle] = useState((short.title || short.output_filename).slice(0, 100));
  const [description, setDescription] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [hashtagsText, setHashtagsText] = useState('#shorts');
  const [privacy, setPrivacy] = useState('public');
  const [madeForKids, setMadeForKids] = useState<boolean>(false);
  const [thumbPreviewUrl, setThumbPreviewUrl] = useState<string>(
    getMediaUrl(short.thumbnail_url || `/api/shorts/${short.id}/thumbnail`)
  );
  const [customThumbPath, setCustomThumbPath] = useState<string | null>(null);
  const [uploadingThumb, setUploadingThumb] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const [generating, setGenerating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [doneUrl, setDoneUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // Kredit video asli — selalu di bagian ATAS deskripsi saat upload.
  const creditBlock = short.source_url
    ? `🎬 Video asli: ${short.source_title || short.title || 'YouTube'}\n🔗 ${short.source_url}`
    : '';

  React.useEffect(() => () => {
    if (pollTimer.current) clearInterval(pollTimer.current);
  }, []);

  const handleThumbUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingThumb(true);
    setError(null);
    try {
      const res = await shortsApi.uploadThumbnail(short.id, file);
      setThumbPreviewUrl(getMediaUrl(res.thumbnail_url) + `?t=${Date.now()}`);
      setCustomThumbPath(res.custom_thumbnail_path);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Gagal mengunggah thumbnail.');
    } finally {
      setUploadingThumb(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const seo = await clipsApi.generateSeo(short.clip_id, { platform: 'youtube_shorts', language: 'id' });
      if (seo.titles?.length) {
        setTitles(seo.titles);
        setTitle(seo.titles[0]);
      }
      if (seo.description) setDescription(seo.description);
      if (seo.tags?.length) setTagsText(seo.tags.join(', '));
      if (seo.hashtags?.length) setHashtagsText(seo.hashtags.join(' '));
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Gagal generate SEO.');
    } finally {
      setGenerating(false);
    }
  };

  // Auto-fill metadata SEO + kredit langsung saat modal dibuka.
  const autoFilled = React.useRef(false);
  React.useEffect(() => {
    if (!autoFilled.current) {
      autoFilled.current = true;
      handleGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpload = async () => {
    if (!title.trim()) {
      setError('Judul wajib diisi.');
      return;
    }
    setUploading(true);
    setError(null);
    setProgress(5);
    try {
      const finalDescription = creditBlock ? `${creditBlock}\n\n${description}` : description;
      await shortsApi.uploadYoutube(short.id, {
        title: title.trim().slice(0, 100),
        description: finalDescription,
        tags: tagsText.split(',').map((t) => t.trim()).filter(Boolean),
        hashtags: hashtagsText.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean),
        privacy_status: privacy,
        category_id: '22',
        made_for_kids: madeForKids,
        custom_thumbnail_path: customThumbPath,
      });
      pollTimer.current = setInterval(async () => {
        try {
          const st = await shortsApi.getYoutubeStatus(short.id);
          setProgress(Math.max(10, st.upload_progress || 10));
          if (st.upload_status === 'SUCCESS') {
            if (pollTimer.current) clearInterval(pollTimer.current);
            setDoneUrl(st.youtube_url || null);
            setUploading(false);
            onUploaded();
          } else if (st.upload_status === 'FAILED') {
            if (pollTimer.current) clearInterval(pollTimer.current);
            setError(st.error_message || 'Upload gagal di worker.');
            setUploading(false);
          }
        } catch {
          /* polling berikutnya */
        }
      }, 3000);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Gagal memulai upload.');
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !uploading && onClose()}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-[#1C1917] flex items-center gap-2">
            <Youtube className="w-5 h-5 text-red-600" />
            Upload ke YouTube
          </h3>
          {!uploading && (
            <button type="button" onClick={onClose} className="p-1 rounded-lg hover:bg-[#F5F5F4] text-[#78716C]">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Judul</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
          />
          {titles.length > 1 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {titles.map((t, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setTitle(t)}
                  className={`px-2.5 py-1 text-[11px] rounded-full border transition-all ${
                    title === t ? 'bg-[#C2410C] text-white border-[#C2410C]' : 'bg-[#F5F5F4] text-[#57534E] border-[#E7E5E4] hover:border-[#C2410C]'
                  }`}
                >
                  Opsi {i + 1}
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Deskripsi</label>
          {generating && !description ? (
            <div className="w-full px-3 py-6 bg-[#F5F5F4] border border-dashed border-[#D6D3D1] rounded-xl text-xs text-[#78716C] text-center">
              ✨ Menyusun judul, deskripsi & tags otomatis...
            </div>
          ) : (
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm text-[#1C1917] focus:border-[#C2410C] outline-none resize-none"
            />
          )}
          {creditBlock ? (
            <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-[10px] font-bold uppercase tracking-wider text-blue-700 mb-0.5">Otomatis di bagian atas deskripsi:</p>
              <p className="text-[11px] text-blue-900 whitespace-pre-line break-all">{creditBlock}</p>
            </div>
          ) : (
            <p className="text-[10px] text-[#A8A29E] mt-1">Video ini diunggah manual (bukan dari YouTube) — tanpa blok kredit.</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Tags (koma)</label>
            <input
              type="text"
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
              placeholder="tips, tutorial, indonesia"
              className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm text-[#1C1917] focus:border-[#C2410C] outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Hashtags</label>
            <input
              type="text"
              value={hashtagsText}
              onChange={(e) => setHashtagsText(e.target.value)}
              placeholder="#shorts #viral"
              className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm text-[#1C1917] focus:border-[#C2410C] outline-none"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-[#78716C] uppercase tracking-wider mb-1">Privasi</label>
          <select
            value={privacy}
            onChange={(e) => setPrivacy(e.target.value)}
            className="w-full px-3 py-2 bg-[#F5F5F4] border border-[#D6D3D1] rounded-xl text-sm font-semibold text-[#1C1917] focus:border-[#C2410C] outline-none"
          >
            <option value="public">🌍 Public</option>
            <option value="unlisted">🔗 Unlisted</option>
            <option value="private">🔒 Private</option>
          </select>
        </div>

        {/* Thumbnail Preview & Custom Upload */}
        <div className="bg-[#F5F5F4] p-3 rounded-xl border border-[#E7E5E4] flex items-center gap-3">
          <div className="w-16 h-24 bg-black rounded-lg overflow-hidden shrink-0 border border-[#D6D3D1] relative">
            <img
              src={thumbPreviewUrl}
              alt="Thumbnail Short"
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <div className="absolute bottom-1 right-1 bg-black/75 px-1 py-0.2 text-[9px] text-white rounded font-mono">
              HD
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1">
              <ImageIcon className="w-3.5 h-3.5 text-[#C2410C]" />
              <span className="text-xs font-semibold text-[#1C1917]">Thumbnail Otomatis</span>
              <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-bold">Auto</span>
            </div>
            <p className="text-[11px] text-[#78716C] leading-snug mb-2">
              {customThumbPath ? 'Thumbnail kustom digunakan.' : 'Diekstrak dari frame visual terbaik secara otomatis.'}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleThumbUpload}
              className="hidden"
            />
            <button
              type="button"
              disabled={uploadingThumb || uploading}
              onClick={() => fileInputRef.current?.click()}
              className="px-2.5 py-1 bg-white hover:bg-stone-100 border border-[#D6D3D1] text-[#1C1917] rounded-lg text-xs font-semibold transition-all inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {uploadingThumb ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              <span>{customThumbPath ? 'Ganti Gambar' : 'Upload Kustom (.jpg/.png)'}</span>
            </button>
          </div>
        </div>

        {/* Audiens & Batasan Usia (Age) */}
        <div className="bg-[#F5F5F4] p-3 rounded-xl border border-[#E7E5E4] space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-[#78716C] uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-[#C2410C]" />
              Kategori Audiens / Usia (Age)
            </label>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
              {!madeForKids ? 'Semua Umur' : 'Khusus Anak'}
            </span>
          </div>

          <div className="space-y-1.5">
            <label
              className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer transition-all ${
                !madeForKids ? 'bg-white border-[#C2410C] shadow-xs' : 'bg-transparent border-[#E7E5E4] hover:bg-white/60'
              }`}
            >
              <input
                type="radio"
                name="madeForKids"
                checked={!madeForKids}
                onChange={() => setMadeForKids(false)}
                className="mt-0.5 accent-[#C2410C]"
              />
              <div className="text-xs">
                <div className="font-semibold text-[#1C1917] flex items-center gap-1.5">
                  <span>Untuk Semua Kalangan Umur (Bukan Khusus Anak-Anak)</span>
                  <span className="text-[10px] text-[#C2410C] font-bold">★ Standar</span>
                </div>
                <p className="text-[11px] text-[#78716C] mt-0.5">
                  Video aman untuk segala usia. Kolom komentar, notifikasi pelanggan, dan interaksi YouTube tetap aktif normal.
                </p>
              </div>
            </label>

            <label
              className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer transition-all ${
                madeForKids ? 'bg-white border-[#C2410C] shadow-xs' : 'bg-transparent border-[#E7E5E4] hover:bg-white/60'
              }`}
            >
              <input
                type="radio"
                name="madeForKids"
                checked={madeForKids}
                onChange={() => setMadeForKids(true)}
                className="mt-0.5 accent-[#C2410C]"
              />
              <div className="text-xs">
                <span className="font-semibold text-[#1C1917]">Khusus Anak-Anak (Made for Kids)</span>
                <p className="text-[11px] text-[#78716C] mt-0.5">
                  Sesuai aturan COPPA YouTube: fitur komentar, notifikasi, dan rekomendasi interaktif dinonaktifkan.
                </p>
              </div>
            </label>
          </div>
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={generating || uploading}
          className="w-full py-2 bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-800 text-xs font-bold rounded-xl transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50"
        >
          {generating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span>✨</span>}
          <span>{generating ? 'Membuat...' : 'Generate Title & Description (AI)'}</span>
        </button>

        {error && (
          <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2 flex items-start gap-1.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </p>
        )}

        {uploading && (
          <div className="space-y-1.5">
            <div className="w-full h-2 bg-[#F5F5F4] rounded-full overflow-hidden">
              <div className="h-full bg-red-600 rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-[11px] text-[#78716C] font-mono">Mengunggah... {progress}%</p>
          </div>
        )}

        {doneUrl ? (
          <a href={doneUrl} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl transition-all">
            <CheckCircle2 className="w-4 h-4" />
            <span>Video Live — Buka di YouTube</span>
          </a>
        ) : (
          <div className="flex justify-end gap-2">
            <button
              type="button"
              disabled={uploading}
              onClick={onClose}
              className="px-4 py-2 text-sm font-semibold text-[#57534E] bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-xl disabled:opacity-50"
            >
              Batal
            </button>
            <button
              type="button"
              disabled={uploading}
              onClick={handleUpload}
              className="px-4 py-2 text-sm font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl disabled:opacity-50 flex items-center gap-2"
            >
              {uploading && <RefreshCw className="w-4 h-4 animate-spin" />}
              {uploading ? 'Mengunggah...' : '📤 Upload Sekarang'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export const ShortsPage: React.FC = () => {
  const [shorts, setShorts] = useState<RenderedShort[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [ytModalShort, setYtModalShort] = useState<RenderedShort | null>(null);
  const [selectedVideoUrl, setSelectedVideoUrl] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // Layout mode & persistence
  const [layoutMode, setLayoutMode] = useState<'grid' | 'list'>('grid');

  // Filters & Search (Default to 'pending': show un-uploaded shorts first, hide uploaded by default)
  const [driveFilter, setDriveFilter] = useState<'all' | 'uploaded' | 'pending' | 'uploading'>('pending');
  const [ytFilter, setYtFilter] = useState<'all' | 'uploaded' | 'pending'>('all');
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

  const handleUploadYoutube = (short: RenderedShort) => {
    if (short.is_youtube_uploaded) {
      setInfoMessage('Klip ini sudah pernah diunggah ke YouTube. Double-upload dicegah.');
      setTimeout(() => setInfoMessage(null), 4000);
      return;
    }
    setYtModalShort(short);
  };

  const handleBatchUploadYoutube = async () => {
    if (selectedShortIds.length === 0) return;
    setBatchProcessing(true);
    try {
      const res = await shortsApi.batchUploadYoutube(selectedShortIds);
      setInfoMessage(res.message || `${res.success_count} shorts dijadwalkan untuk upload ke YouTube (metadata default).`);
      setSelectedShortIds([]);
      await fetchShorts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Gagal memulai upload batch ke YouTube.');
    } finally {
      setBatchProcessing(false);
      setTimeout(() => setInfoMessage(null), 5000);
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
  const ytUploadedCount = shorts.filter((s) => s.is_youtube_uploaded).length;
  const ytPendingCount = shorts.filter((s) => !s.is_youtube_uploaded).length;

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

    if (ytFilter === 'uploaded' && !short.is_youtube_uploaded) return false;
    if (ytFilter === 'pending' && short.is_youtube_uploaded) return false;
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
        {/* Drive + YouTube Filter Tabs */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#A8A29E]">Drive</span>
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

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#A8A29E]">YouTube</span>
            {(
              [
                ['all', `Semua (${shorts.length})`],
                ['uploaded', `Live (${ytUploadedCount})`],
                ['pending', `Belum (${ytPendingCount})`],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setYtFilter(id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                  ytFilter === id
                    ? 'bg-red-600 text-white shadow-xs'
                    : 'bg-[#F5F5F4] text-[#78716C] hover:text-[#1C1917]'
                }`}
              >
                {id === 'uploaded' && <span className="w-2 h-2 rounded-full bg-emerald-400" />}
                {id === 'pending' && <span className="w-2 h-2 rounded-full bg-[#A8A29E]" />}
                <span>{label}</span>
              </button>
            ))}
          </div>
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
            {searchQuery || driveFilter !== 'all' || ytFilter !== 'all' ? 'Tidak Ada Shorts yang Cocok' : 'Belum Ada Video Shorts'}
          </h3>
          <p className="text-sm text-[#57534E] max-w-sm mx-auto mt-1">
            {searchQuery || driveFilter !== 'all' || ytFilter !== 'all'
              ? 'Coba ganti kata kunci pencarian atau tab filter Drive / YouTube.'
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

                  {/* Google Drive + YouTube Status pills */}
                  <div className="flex flex-wrap gap-2">
                    {isUploaded ? (
                      <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800 flex-1 min-w-[140px]">
                        <span className="flex items-center space-x-1 font-semibold truncate">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span className="truncate">Tersimpan di Drive</span>
                        </span>
                        {driveLink && (
                          <a
                            href={driveLink}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center space-x-0.5 text-emerald-700 hover:underline font-mono shrink-0 ml-1"
                          >
                            <span>Buka</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    ) : short.gdrive?.upload_status === 'UPLOADING' ? (
                      <div className="p-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center space-x-1.5 animate-pulse flex-1 min-w-[140px]">
                        <RefreshCw className="w-3 h-3 animate-spin text-amber-600 shrink-0" />
                        <span className="truncate">Sedang Mengunggah ke Drive...</span>
                      </div>
                    ) : (
                      <div className="p-2 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl text-xs text-[#78716C] flex items-center space-x-1 flex-1 min-w-[140px]">
                        <Clock className="w-3.5 h-3.5 shrink-0" />
                        <span className="truncate">Menunggu upload ke Drive</span>
                      </div>
                    )}
                    {short.is_youtube_uploaded ? (
                      <div className="p-2 bg-red-50 border border-red-200 rounded-xl flex items-center space-x-1 text-xs text-red-800 font-semibold shrink-0">
                        <Youtube className="w-3.5 h-3.5" />
                        <span>Live di YouTube</span>
                      </div>
                    ) : (
                      <div className="p-2 bg-[#F5F5F4] border border-[#E7E5E4] rounded-xl text-xs text-[#78716C] flex items-center space-x-1 shrink-0">
                        <Youtube className="w-3.5 h-3.5" />
                        <span>Belum di YouTube</span>
                      </div>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-[#F5F5F4] flex items-center justify-between gap-2 flex-wrap">
                    <button
                      onClick={() => handleDelete(short.id)}
                      className="p-2 text-[#78716C] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors shrink-0"
                      title="Hapus Shorts"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    <div className="flex flex-wrap justify-end gap-1.5 sm:gap-2 min-w-0">
                      <a
                        href={getMediaUrl(short.download_url)}
                        download={short.output_filename}
                        className="px-2 sm:px-3 py-1.5 bg-[#E7E5E4] hover:bg-[#D6D3D1] text-[#1C1917] text-xs font-semibold rounded-lg transition-all flex items-center space-x-1 min-w-0"
                        title="Unduh MP4 ke Komputer"
                      >
                        <Download className="w-3.5 h-3.5 shrink-0" />
                        <span className="hidden min-[400px]:inline">Unduh</span>
                      </a>

                      <button
                        onClick={() => handleUploadDrive(short)}
                        disabled={isUploaded || actionId === short.id || short.render_status !== 'COMPLETED'}
                        className={`px-2 sm:px-3 py-1.5 text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1 min-w-0 ${
                          isUploaded
                            ? 'bg-emerald-100 text-emerald-800 cursor-not-allowed border border-emerald-200'
                            : 'bg-[#C2410C] hover:bg-[#9A3412] text-white'
                        }`}
                        title={isUploaded ? 'Sudah diunggah ke Google Drive (Double-upload dicegah)' : 'Upload ke Google Drive'}
                      >
                        {isUploaded ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                            <span className="hidden min-[400px]:inline">Diunggah</span>
                          </>
                        ) : (
                          <>
                            <UploadCloud className="w-3.5 h-3.5 shrink-0" />
                            <span className="hidden min-[400px]:inline">Ke Drive</span>
                          </>
                        )}
                      </button>

                      <button
                        onClick={() => handleUploadYoutube(short)}
                        disabled={short.is_youtube_uploaded || actionId === short.id || short.render_status !== 'COMPLETED'}
                        className={`px-2 sm:px-3 py-1.5 text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1 min-w-0 ${
                          short.is_youtube_uploaded
                            ? 'bg-emerald-100 text-emerald-800 cursor-not-allowed border border-emerald-200'
                            : 'bg-red-600 hover:bg-red-700 text-white'
                        }`}
                        title={short.is_youtube_uploaded ? 'Sudah diunggah ke YouTube' : 'Upload ke YouTube (metadata default)'}
                      >
                        <Youtube className="w-3.5 h-3.5 shrink-0" />
                        <span className="hidden min-[400px]:inline">{short.is_youtube_uploaded ? 'Live' : 'YouTube'}</span>
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

                {/* Right: Drive + YouTube Status & Actions */}
                <div className="flex items-center justify-end gap-2 sm:gap-3 shrink-0 flex-wrap max-w-[60%]">
                  {/* Google Drive Status badge */}
                  {isUploaded ? (
                    <div className="flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-semibold whitespace-nowrap">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="hidden md:inline">Drive OK</span>
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
                    <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 whitespace-nowrap">
                      <RefreshCw className="w-3 h-3 animate-spin text-amber-600" />
                      <span className="hidden md:inline">Mengunggah...</span>
                    </div>
                  ) : (
                    <span className="text-xs text-[#A8A29E] hidden lg:inline">Menunggu upload</span>
                  )}

                  {/* YouTube Status badge */}
                  {short.is_youtube_uploaded ? (
                    <div className="flex items-center space-x-1 px-2.5 py-1 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 font-semibold whitespace-nowrap">
                      <Youtube className="w-3.5 h-3.5" />
                      <span className="hidden md:inline">Live</span>
                    </div>
                  ) : (
                    <span className="hidden lg:inline-flex items-center space-x-1 text-xs text-[#A8A29E]">
                      <Youtube className="w-3.5 h-3.5" />
                    </span>
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
                    onClick={() => handleUploadYoutube(short)}
                    disabled={short.is_youtube_uploaded || actionId === short.id || short.render_status !== 'COMPLETED'}
                    title={short.is_youtube_uploaded ? 'Sudah diunggah ke YouTube' : 'Upload ke YouTube'}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-xl shadow-xs transition-all flex items-center space-x-1.5 ${
                      short.is_youtube_uploaded
                        ? 'bg-emerald-100 text-emerald-800 cursor-not-allowed border border-emerald-200'
                        : 'bg-red-600 hover:bg-red-700 text-white'
                    }`}
                  >
                    <Youtube className="w-3.5 h-3.5" />
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
            onClick={handleBatchUploadYoutube}
            disabled={batchProcessing}
            title="Upload batch dengan metadata default (judul klip, public, #shorts)"
            className="px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
          >
            <Youtube className="w-3.5 h-3.5" />
            <span>Ke YouTube</span>
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

      {ytModalShort && (
        <YouTubeUploadModal
          short={ytModalShort}
          onClose={() => setYtModalShort(null)}
          onUploaded={() => fetchShorts()}
        />
      )}
    </div>
  );
};
