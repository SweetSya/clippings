import { useCallback } from 'react';

/** Daftar tab valid — sinkron dengan App.tsx dan Sidebar.tsx. */
export const VALID_TABS = [
  'dashboard',
  'upload',
  'studio',
  'shorts',
  'tts',
  'audio',
  'preset',
  'settings',
  'queue',
] as const;

export type AppTab = (typeof VALID_TABS)[number];
export const DEFAULT_TAB: AppTab = 'studio';

export interface ParsedRoute {
  tab: AppTab;
  videoId: string | null;
}

/** Parse location.hash bentuk `#/tab?video=ID`. Hash tak dikenal → tab default. */
export function parseHashRoute(hash = window.location.hash): ParsedRoute {
  const clean = hash.replace(/^#\/?/, '');
  const [path, query] = clean.split('?');
  const tab: AppTab = (VALID_TABS as readonly string[]).includes(path)
    ? (path as AppTab)
    : DEFAULT_TAB;
  let videoId: string | null = null;
  try {
    videoId = new URLSearchParams(query || '').get('video');
  } catch {
    videoId = null;
  }
  return { tab, videoId: videoId || null };
}

/** Bangun string hash dari tab + param opsional. */
export function buildHash(tab: AppTab, videoId?: string | null): string {
  return `#/${tab}${videoId ? `?video=${encodeURIComponent(videoId)}` : ''}`;
}

/**
 * Hook navigasi: tulis state React SEKALIGUS hash URL.
 * - Refresh / back-forward browser → hashchange → state ikut pulih.
 * - Tanpa dep router eksternal; aman di nginx static (tanpa rewrite).
 */
export function useHashNavigate(
  setTab: (tab: AppTab) => void,
  setVideoId: (id: string | null) => void,
) {
  return useCallback(
    (tab: AppTab, videoId?: string | null) => {
      setTab(tab);
      if (videoId !== undefined) setVideoId(videoId);
      const next = buildHash(tab, videoId);
      if (window.location.hash !== next) window.location.hash = next;
    },
    [setTab, setVideoId],
  );
}
