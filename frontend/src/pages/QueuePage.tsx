import React, { useEffect, useRef, useState } from 'react';
import {
  ListOrdered,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  X,
} from 'lucide-react';
import { jobsApi, QueueJob } from '../services/api';

const TYPE_LABELS: Record<string, string> = {
  YOUTUBE_DOWNLOAD: 'Unduh YouTube',
  AUDIO_EXTRACT: 'Ekstrak Audio',
  TRANSCRIBE: 'Transkripsi',
  LLM_ANALYZE: 'Analisis AI',
  RENDER: 'Render 9:16',
  GDRIVE_UPLOAD: 'Upload Drive',
  YOUTUBE_UPLOAD: 'Upload YouTube',
};

const STATUS_STYLE: Record<string, string> = {
  QUEUED: 'bg-amber-100 text-amber-800 border-amber-200',
  RUNNING: 'bg-blue-100 text-blue-800 border-blue-200',
  COMPLETED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  FAILED: 'bg-red-100 text-red-800 border-red-200',
  CANCELLED: 'bg-stone-200 text-stone-600 border-stone-300',
};

function timeAgo(iso: string): string {
  // Server kirim datetime naive = UTC tanpa penanda zona. Tanpa 'Z'/offset,
  // browser menebaknya sebagai waktu lokal (selisih jam!) — paksa sebagai UTC.
  const normalized = /[Zz+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const t = new Date(normalized).getTime();
  if (Number.isNaN(t)) return '-';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s} dtk lalu`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} mnt lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  return `${Math.floor(h / 24)} hari lalu`;
}

export const QueuePage: React.FC = () => {
  const [jobs, setJobs] = useState<QueueJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'semua' | 'aktif' | 'selesai' | 'gagal'>('semua');
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      setJobs(await jobsApi.list({ limit: 100 }));
    } catch (e) {
      if (!silent) {
        setNotification({ type: 'error', message: 'Gagal memuat antrean.' });
        setTimeout(() => setNotification(null), 3000);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    timer.current = setInterval(() => fetchJobs(true), 3000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  const active = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'RUNNING');
  const history = jobs.filter((j) => j.status !== 'QUEUED' && j.status !== 'RUNNING');
  const visible = filter === 'semua' ? jobs : filter === 'aktif' ? active : filter === 'selesai'
    ? history.filter((j) => j.status === 'COMPLETED')
    : history.filter((j) => j.status === 'FAILED' || j.status === 'CANCELLED');

  const renderRow = (job: QueueJob) => (
    <div key={job.id} className="bg-white border border-[#D6D3D1] rounded-2xl p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-sm text-[#1C1917]">
              {TYPE_LABELS[job.job_type] || job.job_type}
            </span>
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${STATUS_STYLE[job.status] || STATUS_STYLE.CANCELLED}`}>
              {job.status}
            </span>
          </div>
          <p className="text-xs text-[#57534E] truncate mt-1" title={job.ref_id}>{job.ref_label}</p>
        </div>
        <span className="text-[11px] font-mono text-[#A8A29E] shrink-0 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {timeAgo(job.started_at || job.created_at)}
        </span>
      </div>

      {(job.status === 'RUNNING' || job.status === 'QUEUED') && (
        <div className="w-full h-1.5 bg-[#F5F5F4] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${job.status === 'RUNNING' ? 'bg-blue-500' : 'bg-amber-400'}`}
            style={{ width: `${Math.min(100, Math.max(job.status === 'QUEUED' ? 4 : 8, job.progress))}%` }}
          />
        </div>
      )}

      <div className="flex items-center gap-3 text-[11px] font-mono text-[#78716C]">
        <span>progres {job.progress}%</span>
        <span>•</span>
        <span>percobaan {job.attempts}/{job.max_attempts}</span>
        {job.finished_at && (
          <>
            <span>•</span>
            <span>selesai {timeAgo(job.finished_at)}</span>
          </>
        )}
      </div>

      {job.status === 'FAILED' && job.error_message && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2 break-words">
          {job.error_message}
        </p>
      )}
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {notification && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 max-w-xl w-auto">
          <div className="flex items-center space-x-3 px-5 py-3 rounded-2xl shadow-2xl border bg-[#1C1917]/95 text-white border-rose-500/40">
            <AlertCircle className="w-4 h-4 text-rose-400" />
            <span className="text-sm font-medium">{notification.message}</span>
            <button type="button" onClick={() => setNotification(null)} className="ml-2 shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-display font-bold text-2xl text-[#1C1917] flex items-center space-x-2">
            <ListOrdered className="w-6 h-6 text-[#C2410C]" />
            <span>Antrean Worker</span>
          </h2>
          <p className="text-sm text-[#57534E] mt-1">
            Semua data yang sedang diproses worker + riwayatnya. Otomatis segar tiap 3 detik.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="px-3 py-1.5 bg-blue-50 border border-blue-200 text-blue-800 text-xs font-bold rounded-xl">
            {active.length} aktif
          </span>
          <button
            type="button"
            onClick={() => fetchJobs()}
            disabled={loading}
            className="p-2 bg-[#F5F5F4] hover:bg-[#E7E5E4] rounded-xl text-[#57534E] transition-colors"
            title="Muat ulang"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="flex gap-1.5">
        {([
          ['semua', 'Semua'],
          ['aktif', `Aktif (${active.length})`],
          ['selesai', 'Selesai'],
          ['gagal', 'Gagal'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setFilter(id)}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-full transition-all ${
              filter === id ? 'bg-[#C2410C] text-white' : 'bg-white border border-[#D6D3D1] text-[#57534E] hover:bg-[#F5F5F4]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="bg-white border border-[#D6D3D1] rounded-2xl p-12 text-center">
          <Loader2 className="w-6 h-6 animate-spin text-[#C2410C] mx-auto" />
        </div>
      ) : visible.length === 0 ? (
        <div className="bg-white border border-dashed border-[#D6D3D1] rounded-2xl p-12 text-center space-y-2">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
          <p className="text-sm text-[#78716C]">Antrean kosong — worker menganggur.</p>
        </div>
      ) : (
        <div className="space-y-3">{visible.map(renderRow)}</div>
      )}
    </div>
  );
};

export default QueuePage;
