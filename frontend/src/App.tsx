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
import { authApi, healthApi } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState('studio');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isConfigured, setIsConfigured] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [healthOk, setHealthOk] = useState(true);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const [selectedAudioTrackId, setSelectedAudioTrackId] = useState<string | null>(null);

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

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setShowAuthModal(true);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    const healthInterval = setInterval(checkHealth, 15000);

    return () => {
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
    setSelectedVideoId(videoId);
    setCurrentTab('studio');
  };

  const handleUseAsBgm = (trackId: string) => {
    setSelectedAudioTrackId(trackId);
    setCurrentTab('studio');
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
        onTabChange={setCurrentTab}
        onLogout={handleLogout}
        healthOk={healthOk}
      />

      {/* Main Content Area */}
      <main className="flex-1 ml-64 p-8 min-h-screen">
        {currentTab === 'dashboard' && (
          <DashboardPage
            onSelectVideo={handleOpenStudio}
            onNavigateUpload={() => setCurrentTab('upload')}
          />
        )}
        {currentTab === 'upload' && (
          <UploadPage
            onUploadSuccess={handleOpenStudio}
            onNavigateDashboard={() => setCurrentTab('dashboard')}
          />
        )}
        {currentTab === 'studio' && (
          <ClipStudioPage
            selectedVideoId={selectedVideoId}
            selectedAudioTrackId={selectedAudioTrackId}
            onNavigateShorts={() => setCurrentTab('shorts')}
            onNavigateSettings={() => setCurrentTab('settings')}
            onNavigateAudioLibrary={() => setCurrentTab('audio')}
            onNavigatePresets={() => setCurrentTab('preset')}
          />
        )}
        {currentTab === 'shorts' && <ShortsPage />}
        {currentTab === 'tts' && <TTSPage />}
        {currentTab === 'audio' && <AudioLibraryPage onUseAsBgm={handleUseAsBgm} />}
        {currentTab === 'preset' && <PresetPage />}
        {currentTab === 'settings' && <SettingsPage />}
      </main>
    </div>
  );
};

export default App;
