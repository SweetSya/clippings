import { useCallback, useEffect, useState } from 'react';

export type ThemeChoice = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'embershorts-theme';

function resolveDark(choice: ThemeChoice): boolean {
  if (choice === 'dark') return true;
  if (choice === 'light') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

/** Terapkan tema ke <html> seawal mungkin (dipanggil dari main.tsx cegah FOUC). */
export function initTheme(): void {
  try {
    const stored = (localStorage.getItem(STORAGE_KEY) as ThemeChoice | null) ?? 'system';
    document.documentElement.classList.toggle('dark', resolveDark(stored));
  } catch {
    /* abaikan (SSR/storage diblokir) */
  }
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as ThemeChoice | null) ?? 'system';
    } catch {
      return 'system';
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolveDark(choice));
    try {
      localStorage.setItem(STORAGE_KEY, choice);
    } catch {
      /* abaikan */
    }
  }, [choice]);

  useEffect(() => {
    if (choice !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => document.documentElement.classList.toggle('dark', mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, [choice]);

  const set = useCallback((c: ThemeChoice) => setChoice(c), []);
  return { choice, setTheme: set };
}
