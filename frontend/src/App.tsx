import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { AuthModal } from './components/AuthModal';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { ClipStudioPage } from './pages/ClipStudioPage';
import { ShortsPage } from './pages/ShortsPage';
import { TTSPage } from './pages/TTSPage';
import { SettingsPage } from './pages/SettingsPage';
import { AudioLibraryPage } from './pages/AudioLibraryPage';
import { PresetPage } from './pages/PresetPage';
import { QueuePage } from './pages/QueuePage';
import { authApi, healthApi } from './services/api';
import { parseHashRoute, buildHash, useHashNavigate, AppTab, VALID_TABS } from './hooks/useHashRoute';

export const App: React.FC = () => {
  const initialRoute = parseHashRoute();
  const [currentTab, setCurrentTab] = useState<string>(initialRoute.tab);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isConfigured, setIsConfigured] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [healthOk, setHealthOk] = useState(true);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(initialRoute.videoId);
  const [selectedAudioTrackId, setSelectedAudioTrackId] = useState<string | null>(null);

  const navigateBase = useHashNavigate(setCurrentTab as (t: AppTab) => void, setSelectedVideoId);
  // Pindah tab + tulis hash URL. Tab studio tanpa video eksplisit mempertahankan video aktif.
  const navigate = (tab: AppTab, videoId?: string | null) => {
    if (videoId === undefined && tab === 'studio') {
      const current = parseHashRoute().videoId ?? selectedVideoIdRef.current;
      navigateBase(tab, current);
    } else {
      navigateBase(tab, videoId);
    }
  };
  const selectedVideoIdRef = React.useRef<string | null>(initialRoute.videoId);
  selectedVideoIdRef.current = selectedVideoId;

  const checkAuth = async () => {
    try {
      const status = await authApi.getStatus();
      setIsConfigured(status.is_configured);
      const token = authApi.getToken();
      if (!status.is_configured) {
        setIsAuthenticated(false);
        setShowAuthModal(true);
      } else if (!token || !status.has_session) {
        setIsAuthenticated(false);
        setShowAuthModal(true);
      } else {
        setIsAuthenticated(true);
        setShowAuthModal(false);
      }
    } catch (e) {
      console.error('Failed to check auth status', e);
    }
  };

  const checkHealth = async () => {
    try {
      const h = await healthApi.check();
      setHealthOk(h.status === 'ok');
    } catch {
      setHealthOk(false);
    }
  };

  useEffect(() => {
    checkAuth();
    checkHealth();

    // Pulihkan tab dari URL (refresh / back-forward browser).
    const syncFromHash = () => {
      const r = parseHashRoute();
      setCurrentTab(r.tab);
      setSelectedVideoId(r.videoId);
    };
    if (!window.location.hash) {
      window.location.hash = buildHash(initialRoute.tab, initialRoute.videoId);
    }
    window.addEventListener('hashchange', syncFromHash);

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setShowAuthModal(true);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    const healthInterval = setInterval(checkHealth, 15000);

    return () => {
      window.removeEventListener('hashchange', syncFromHash);
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
      clearInterval(healthInterval);
    };
  }, []);

  const handleAuthSuccess = (token: string) => {
    authApi.setToken(token);
    setIsAuthenticated(true);
    setIsConfigured(true);
    setShowAuthModal(false);
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch (e) {}
    setIsAuthenticated(false);
    setShowAuthModal(true);
  };

  const handleOpenStudio = (videoId: string) => {
    navigate('studio', videoId);
  };

  const handleUseAsBgm = (trackId: string) => {
    setSelectedAudioTrackId(trackId);
    navigate('studio');
  };

  return (
    <div className="min-h-screen bg-[#FAFAF9] flex">
      {/* Auth Modal Overlay */}
      {showAuthModal && (
        <AuthModal
          isConfigured={isConfigured}
          onSuccess={handleAuthSuccess}
        />
      )}

      {/* Persistent Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={(tab: string) => navigate(
          (VALID_TABS as readonly string[]).includes(tab) ? (tab as AppTab) : 'studio'
        )}
        onLogout={handleLogout}
        healthOk={healthOk}
      />

      {/* Main Content Area */}
      <main className="flex-1 ml-64 p-8 min-h-screen">
        {currentTab === 'dashboard' && (
          <DashboardPage
            onSelectVideo={handleOpenStudio}
            onNavigateUpload={() => navigate('upload')}
          />
        )}
        {currentTab === 'upload' && (
          <UploadPage
            onUploadSuccess={handleOpenStudio}
            onNavigateDashboard={() => navigate('dashboard')}
          />
        )}
        {currentTab === 'studio' && (
          <ClipStudioPage
            selectedVideoId={selectedVideoId}
            selectedAudioTrackId={selectedAudioTrackId}
            onNavigateShorts={() => navigate('shorts')}
            onNavigateSettings={() => navigate('settings')}
            onNavigateAudioLibrary={() => navigate('audio')}
            onNavigatePresets={() => navigate('preset')}
          />
        )}
        {currentTab === 'shorts' && <ShortsPage />}
        {currentTab === 'tts' && <TTSPage />}
        {currentTab === 'audio' && <AudioLibraryPage onUseAsBgm={handleUseAsBgm} />}
        {currentTab === 'preset' && <PresetPage />}
        {currentTab === 'queue' && <QueuePage />}
        {currentTab === 'settings' && <SettingsPage />}
      </main>
    </div>
  );
};

export default App;
