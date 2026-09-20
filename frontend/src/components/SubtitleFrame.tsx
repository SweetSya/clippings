import React, { useEffect, useRef, useState } from 'react';
import { SubtitleMotionType, FramingLayout, ScreenMode, PersonShape } from '../types';

export type SubtitlePosition = 'bottom' | 'middle' | 'top' | 'custom' | string;

/**
 * Resolusi skrip ASS. Nilai-nilai di bawah ini harus tetap sinkron dengan
 * `generate_karaoke_ass` di backend/app/services/ass_service.py.
 */
const SCRIPT_WIDTH = 1080;
const SCRIPT_HEIGHT = 1920;
const SIDE_MARGIN = 60; // MarginL / MarginR pada baris Style

/** MarginV bawaan per posisi, sama persis dengan ass_service.py. */
export const DEFAULT_MARGIN_V: Record<string, number> = {
  top: 1540,
  middle: 920,
  bottom: 340,
  custom: 340,
};

interface SubtitleFrameProps {
  font: string;
  fontSize: number;
  primaryColor: string;
  activeColor: string;
  outlineWidth: number;
  shadowDepth: number;
  isUppercase: boolean;
  position: SubtitlePosition;
  /** Override MarginV (mis. dari preset). Bila null, dipakai nilai bawaan posisi. */
  marginV?: number | null;
  sampleText?: string;
  highlightWord?: string;
  /** Subtitle motion type and visual effects */
  motionType?: SubtitleMotionType;
  highlightBgColor?: string;
  enableKeywordColor?: boolean;
  keywordColor?: string;
  enableDynamicScaling?: boolean;
  enableEmojiInjection?: boolean;
  glowEffect?: boolean;
  /** Multi-Layer Framing & Vocal Dynamics props */
  framingLayout?: FramingLayout;
  screenMode?: ScreenMode;
  personShape?: PersonShape;
  personScale?: number;
  personOffsetX?: number;
  personOffsetY?: number;
  screenOffsetX?: number;
  screenOffsetY?: number;
  screenScale?: number;
  screenAspect?: string;
  enableVocalDynamics?: boolean;
  /** Color grading preset — aproksimasi CSS dari VIDEO_FILTERS backend (preview saja). */
  videoFilter?: string;
  /** Motion graphics overlay preview (judul intro / CTA outro / lower third). */
  overlayIntro?: string | null;
  overlayIntroPause?: boolean;
  overlayOutro?: string | null;
  overlayLowerThird?: string | null;
  videoSrc?: string;
  cropOffsetX?: number;
  /** Optional video ref to link playback with parent controls */
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  onTimeUpdate?: (e: React.SyntheticEvent<HTMLVideoElement>) => void;
  onVideoClick?: () => void;
  isMuted?: boolean;
  /** Isi layar di depan video — mis. notch ponsel, grid line, tombol play/pause di Clip Studio. */
  children?: React.ReactNode;
  className?: string;
}

/**
 * Layar 9:16 yang menskalakan gaya subtitle secara proporsional terhadap hasil
 * render 1080x1920. Semua ukuran (font, outline, shadow, margin) dihitung dengan
 * faktor `lebar layar / 1080`, sehingga pratinjau benar-benar mewakili hasil akhir.
 */
export const SubtitleFrame: React.FC<SubtitleFrameProps> = ({
  font,
  fontSize,
  primaryColor,
  activeColor,
  outlineWidth,
  shadowDepth,
  isUppercase,
  position,
  marginV,
  sampleText = 'Momen terbaik dalam klip ini!',
  highlightWord = 'terbaik',
  motionType = 'karaoke',
  highlightBgColor = '#FFCC00',
  enableKeywordColor = true,
  keywordColor = '#10B981',
  enableDynamicScaling = false,
  enableEmojiInjection = false,
  glowEffect = false,
  framingLayout = 'single',
  screenMode = 'full',
  personShape = 'circle',
  personScale = 0.35,
  personOffsetX = 0,
  personOffsetY = 0,
  screenOffsetX = 0,
  screenOffsetY = 0,
  screenScale = 1.0,
  screenAspect = '16:9',
  enableVocalDynamics = false,
  videoFilter = 'none',
  overlayIntro = null,
  overlayIntroPause = false,
  overlayOutro = null,
  overlayLowerThird = null,
  videoSrc,
  cropOffsetX = 0,
  videoRef,
  onTimeUpdate,
  onVideoClick,
  isMuted = true,
  children,
  className = '',
}) => {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [frameWidth, setFrameWidth] = useState(0);
  const [activeWordIndex, setActiveWordIndex] = useState(0);
  const pipVideoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const element = frameRef.current;
    if (!element) return;

    const measure = () => setFrameWidth(element.clientWidth);
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const scale = frameWidth / SCRIPT_WIDTH;
  const effectiveMarginV = marginV ?? DEFAULT_MARGIN_V[position] ?? 340;

  // -webkit-text-stroke menggambar setengah keluar dan setengah ke dalam glyph,
  // sedangkan outline ASS seluruhnya di luar. Karena itu lebar stroke digandakan.
  const strokeWidth = outlineWidth * scale * 2;
  // Shadow ASS adalah salinan teks yang digeser diagonal tanpa blur.
  const shadowOffset = shadowDepth * scale;

  // Visual emphasis color resolution
  const effectiveActiveColor = enableKeywordColor ? keywordColor : activeColor;
  const wordScaleMultiplier = enableDynamicScaling || enableVocalDynamics ? 1.25 : 1.1;

  // Smart emoji prefix injection for preview
  const displayEmoji = enableEmojiInjection ? '🔥 ' : '';
  const baseSampleText =
    enableEmojiInjection && !sampleText.includes('🔥') && !sampleText.includes('💰')
      ? `${displayEmoji}${sampleText}`
      : sampleText;

  // Tokenize sample text for live dynamic sequencer
  const words = React.useMemo(() => {
    const tokens = baseSampleText.trim().split(/\s+/).filter(Boolean);
    return tokens.length > 0 ? tokens : ['Momen', 'terbaik', 'dalam', 'klip', 'ini!'];
  }, [baseSampleText]);

  // Dynamic word cycle sequencer (every 650ms cycles next word)
  useEffect(() => {
    if (words.length <= 1) return;
    const interval = setInterval(() => {
      setActiveWordIndex((prev) => (prev + 1) % words.length);
    }, 650);
    return () => clearInterval(interval);
  }, [words.length]);

  // Handle synchronized playback for secondary PIP facecam video
  const handleTimeUpdateInternal = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    if (pipVideoRef.current && videoRef?.current) {
      if (Math.abs(pipVideoRef.current.currentTime - videoRef.current.currentTime) > 0.15) {
        pipVideoRef.current.currentTime = videoRef.current.currentTime;
      }
      if (videoRef.current.paused && !pipVideoRef.current.paused) {
        pipVideoRef.current.pause();
      } else if (!videoRef.current.paused && pipVideoRef.current.paused) {
        pipVideoRef.current.play().catch(() => {});
      }
    }
    onTimeUpdate?.(e);
  };

  // Shadow style with softened diffuse neon glow
  const baseShadow =
    shadowOffset > 0 ? `${shadowOffset.toFixed(2)}px ${shadowOffset.toFixed(2)}px 0 rgba(0,0,0,0.9)` : 'none';
  const glowShadow = glowEffect
    ? `0 0 ${(4 * scale).toFixed(1)}px ${activeColor}99, 0 0 ${(10 * scale).toFixed(1)}px ${activeColor}40, ${baseShadow}`
    : baseShadow;

  // Aproksimasi CSS untuk VIDEO_FILTERS backend (preview saja, bukan hasil akhir FFmpeg)
  const VIDEO_FILTER_CSS: Record<string, string | undefined> = {
    none: undefined,
    cinematic: 'contrast(1.1) saturate(0.85) brightness(0.92)',
    vivid: 'saturate(1.4) brightness(1.05)',
    warm: 'sepia(0.35) saturate(1.2) hue-rotate(-10deg)',
    cool: 'saturate(1.1) hue-rotate(15deg) brightness(1.02)',
    drama: 'contrast(1.25) saturate(1.1)',
    vintage: 'sepia(0.5) contrast(0.95) brightness(0.95) saturate(0.8)',
  };
  const cssVideoFilter = VIDEO_FILTER_CSS[(videoFilter || 'none').toLowerCase()] ?? undefined;

  // Helper renderers for Multi-Layer Framing preview
  const renderPersonLayer = (isPip = true) => {
    const shapeClass =
      personShape === 'circle'
        ? 'rounded-full aspect-square'
        : personShape === 'rounded'
        ? 'rounded-2xl aspect-[4/3]'
        : 'rounded-md aspect-[16/9]';

    // Facecam object position mapping (for 16:9 source, cropOffsetX ranges from 0 to 1380px)
    const facecamXPercent =
      cropOffsetX !== 0
        ? Math.max(0, Math.min(100, Math.round((cropOffsetX / 1380) * 100)))
        : 85; // Default streamer webcam is bottom-right
    const facecamYPercent = cropOffsetX > 350 && cropOffsetX < 1050 ? 50 : 85;

    return (
      <div
        className={`bg-stone-900 flex flex-col items-center justify-center overflow-hidden border-2 border-white/90 shadow-2xl ring-1 ring-black/40 transition-all duration-100 ${shapeClass}`}
        style={
          isPip
            ? {
                width: `${Math.round(personScale * 100)}%`,
                transform: `translate(${(personOffsetX * scale).toFixed(1)}px, ${(personOffsetY * scale).toFixed(1)}px)`,
              }
            : {
                width: '100%',
                height: '100%',
                transform: `translate(${(personOffsetX * scale).toFixed(1)}px, ${(personOffsetY * scale).toFixed(1)}px)`,
              }
        }
      >
        {videoSrc ? (
          <div className="relative w-full h-full overflow-hidden flex items-center justify-center bg-black">
            <video
              ref={pipVideoRef}
              src={videoSrc}
              autoPlay
              loop
              muted
              playsInline
              className="w-full h-full pointer-events-none transition-transform duration-150"
              style={{
                objectFit: 'cover',
                transform: 'scale(2.4)',
                transformOrigin: `${facecamXPercent}% ${facecamYPercent}%`,
                filter: cssVideoFilter,
              }}
            />
            <span className="absolute bottom-1 bg-black/60 text-[8px] font-bold text-white px-1.5 py-0.5 rounded backdrop-blur-xs pointer-events-none">
              Facecam
            </span>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-2 bg-gradient-to-b from-stone-800 to-stone-900 w-full h-full">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-amber-600 to-orange-500 flex items-center justify-center text-xl shadow-lg border border-white/30">
              👤
            </div>
            <span className="text-[9px] font-bold text-white/90 bg-black/60 px-2 py-0.5 rounded-full mt-1 backdrop-blur-xs tracking-tight">
              Facecam PIP
            </span>
          </div>
        )}
      </div>
    );
  };

  const renderScreenLayer = (isFullBg = false) => {
    if (isFullBg) {
      return (
        <div className="absolute inset-0 bg-stone-950 flex items-center justify-center overflow-hidden">
          {videoSrc ? (
            <video
              ref={videoRef}
              src={videoSrc}
              autoPlay
              loop
              playsInline
              muted={isMuted}
              onTimeUpdate={handleTimeUpdateInternal}
              onClick={onVideoClick}
              className="absolute inset-0 w-full h-full object-cover cursor-pointer"
              style={{
                objectPosition: cropOffsetX
                  ? `${Math.max(0, Math.min(100, Math.round((cropOffsetX / 1380) * 100)))}% 50%`
                  : '50% 50%',
                filter: cssVideoFilter,
              }}
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-stone-900 via-stone-950 to-stone-900 flex flex-col items-center justify-center text-stone-600">
              <span className="text-3xl opacity-40">📱</span>
              <span className="text-[10px] font-bold tracking-wider uppercase mt-1 opacity-50">Layar 9:16 Penuh</span>
            </div>
          )}
        </div>
      );
    }

    // Centered 16:9 Screen with ambient blurred background
    return (
      <div className="relative w-full h-full bg-black flex items-center justify-center overflow-hidden">
        {videoSrc ? (
          <video
            src={videoSrc}
            autoPlay
            loop
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover blur-xl opacity-60 scale-110 pointer-events-none"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-b from-stone-900 via-stone-800 to-stone-900 opacity-90" />
        )}
        <div
          className="relative z-1 w-full border border-stone-600/50 rounded-xs bg-black flex items-center justify-center transition-all duration-100 shadow-2xl overflow-hidden"
          style={{
            aspectRatio: screenAspect === '9:16' ? '9/16' : '16/9',
            transform: `translate(${(screenOffsetX * scale).toFixed(1)}px, ${(screenOffsetY * scale).toFixed(1)}px) scale(${screenScale})`,
          }}
        >
          {videoSrc ? (
            <video
              ref={videoRef}
              src={videoSrc}
              autoPlay
              loop
              playsInline
              muted={isMuted}
              onTimeUpdate={handleTimeUpdateInternal}
              onClick={onVideoClick}
              className="w-full h-full object-contain cursor-pointer"
              style={{ filter: cssVideoFilter }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center p-2">
              <span className="text-xl">💻</span>
              <span className="text-[9px] font-bold text-stone-300 mt-1">
                Layar Konten ({screenAspect})
              </span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const isPipLayout =
    framingLayout === 'pip_full' ||
    framingLayout === 'pip_center' ||
    framingLayout === 'overlay_pip';

  const isCenterMode =
    screenMode === 'center' ||
    framingLayout === 'pip_center' ||
    framingLayout === 'fit_16_9_center';

  const isStreamerLayout =
    framingLayout === 'streamer_face_top' ||
    framingLayout === 'streamer_face_bottom';

  const renderStreamerLayers = () => {
    const faceFirst = framingLayout === 'streamer_face_top';
    const faceBox = (
      <div key="face" className="w-full flex flex-col items-center justify-center bg-gradient-to-b from-stone-800 to-stone-900 border-b-2 border-white/40" style={{ height: '40%' }}>
        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-amber-600 to-orange-500 flex items-center justify-center text-xl shadow-lg border border-white/30">
          👤
        </div>
        <span className="text-[9px] font-bold text-white/90 bg-black/60 px-2 py-0.5 rounded-full mt-1 tracking-tight">
          Zona Wajah (40%)
        </span>
      </div>
    );
    const screenBox = (
      <div key="screen" className="w-full flex flex-col items-center justify-center bg-gradient-to-br from-stone-900 via-stone-950 to-stone-900" style={{ height: '60%' }}>
        <span className="text-xl">💻</span>
        <span className="text-[9px] font-bold text-stone-300 mt-1">Konten / Game (60%)</span>
      </div>
    );
    return (
      <div className="absolute inset-0 flex flex-col" style={{ filter: cssVideoFilter }}>
        {faceFirst ? [faceBox, screenBox] : [screenBox, faceBox]}
      </div>
    );
  };

  return (
    <div
      ref={frameRef}
      className={`relative bg-black overflow-hidden select-none ${className}`}
      style={{ aspectRatio: `${SCRIPT_WIDTH} / ${SCRIPT_HEIGHT}` }}
    >
      {/* Dynamic Keyframes for Hormozi Pop and Slide Up */}
      <style>{`
        @keyframes hormoziPopAnim {
          0% { transform: scale(1.28); opacity: 0.9; }
          45% { transform: scale(1.0); opacity: 1; }
          100% { transform: scale(1.0); opacity: 1; }
        }
        @keyframes slideUpFadeAnim {
          0% { transform: translateY(12px); opacity: 0.4; }
          100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes typewriterCursor {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes bounceInAnim {
          0% { transform: translateY(-46px); opacity: 0; }
          60% { transform: translateY(4px); opacity: 1; }
          80% { transform: translateY(-2px); opacity: 1; }
          100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes zoomFlashAnim {
          0% { transform: scale(2.0); opacity: 0.6; filter: brightness(1.8); }
          60% { transform: scale(1.0); opacity: 1; filter: brightness(1.2); }
          100% { transform: scale(1.0); opacity: 1; filter: brightness(1.0); }
        }
        @keyframes glitchRevealAnim {
          0% { transform: translateX(6px); opacity: 0.5; filter: hue-rotate(90deg); }
          40% { transform: translateX(-6px); opacity: 0.9; filter: hue-rotate(-60deg); }
          70% { transform: translateX(2px); opacity: 1; filter: hue-rotate(0deg); }
          100% { transform: translateX(0); opacity: 1; }
        }
      `}</style>

      {/* Base Video Layer (Full 9:16 or Centered 16:9 Ambient Blur) */}
      {isStreamerLayout ? renderStreamerLayers() : isCenterMode ? renderScreenLayer(false) : renderScreenLayer(true)}

      {/* Picture-in-Picture Overlay Layer (Instance 2: Facecam/Webcam) */}
      {!isStreamerLayout && isPipLayout && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          {renderPersonLayer(true)}
        </div>
      )}

      {/* Vocal Dynamics Badge Indicator */}
      {enableVocalDynamics && (
        <div className="absolute top-2.5 right-2.5 z-20 pointer-events-none">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-600/90 text-white shadow-xs backdrop-blur-xs flex items-center space-x-1">
            <span>🎙️</span>
            <span>Vocal Dynamics</span>
          </span>
        </div>
      )}

      {/* Subtitle Layer (Always on top of composite video) */}
      <div
        className="absolute z-15 text-center pointer-events-none flex flex-col items-center justify-center"
        style={{
          left: `${(SIDE_MARGIN / SCRIPT_WIDTH) * 100}%`,
          right: `${(SIDE_MARGIN / SCRIPT_WIDTH) * 100}%`,
          bottom: `${(effectiveMarginV / SCRIPT_HEIGHT) * 100}%`,
        }}
      >
        {motionType === 'single_word_pop' ? (
          /* 1. Single Word Pop / Bouncy (Hormozi Style) with Live Word Sequencer */
          <div
            key={activeWordIndex}
            className="inline-block"
            style={{
              animation: 'hormoziPopAnim 0.65s cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          >
            <span
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: effectiveActiveColor,
                fontSize: `${fontSize * scale * (enableDynamicScaling || enableVocalDynamics ? 1.3 : 1.18)}px`,
                lineHeight: 1.2,
                fontWeight: 900,
                textTransform: isUppercase ? 'uppercase' : 'none',
                WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
                paintOrder: 'stroke fill',
                textShadow: glowShadow,
                display: 'inline-block',
                letterSpacing: '-0.02em',
              }}
            >
              {words[activeWordIndex] ?? highlightWord}
            </span>
          </div>
        ) : motionType === 'background_box' ? (
          /* 3. Background Box / Highlighter Sticker with Live Active Word Jump */
          <p
            style={{
              fontFamily: font === 'Poppins' ? 'sans-serif' : font,
              color: primaryColor,
              fontSize: `${fontSize * scale}px`,
              lineHeight: 1.35,
              fontWeight: 700,
              textTransform: isUppercase ? 'uppercase' : 'none',
              WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
              paintOrder: 'stroke fill',
              textShadow: baseShadow,
            }}
          >
            {words.map((word, idx) => {
              const isActive = idx === activeWordIndex;
              return (
                <span
                  key={idx}
                  className={`inline-block mx-1 transition-all duration-150 align-baseline ${
                    isActive ? 'rounded-sm shadow-md font-black' : ''
                  }`}
                  style={
                    isActive
                      ? {
                          backgroundColor: highlightBgColor,
                          color: '#1C1917',
                          WebkitTextStroke: '0px transparent',
                          textShadow: 'none',
                          padding: `${2 * scale}px ${8 * scale}px`,
                          borderRadius: `${4 * scale}px`,
                          transform: `scale(${wordScaleMultiplier})`,
                        }
                      : {
                          color: primaryColor,
                        }
                  }
                >
                  {word}
                </span>
              );
            })}
          </p>
        ) : motionType === 'typewriter' ? (
          /* 4. Typewriter / Word-by-Word Reveal */
          <div className="flex items-center justify-center">
            <p
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: primaryColor,
                fontSize: `${fontSize * scale}px`,
                lineHeight: 1.25,
                fontWeight: 700,
                textTransform: isUppercase ? 'uppercase' : 'none',
                WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
                paintOrder: 'stroke fill',
                textShadow: glowShadow,
              }}
            >
              {words.slice(0, activeWordIndex + 1).map((word, idx) => (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: idx === activeWordIndex ? effectiveActiveColor : primaryColor,
                    fontWeight: idx === activeWordIndex ? 800 : 700,
                    transform: idx === activeWordIndex ? `scale(${wordScaleMultiplier})` : 'scale(1)',
                  }}
                >
                  {word}
                </span>
              ))}
              <span
                className="inline-block ml-0.5 w-[2px] bg-amber-400 align-middle"
                style={{
                  height: `${fontSize * scale * 0.9}px`,
                  animation: 'typewriterCursor 0.8s infinite',
                }}
              />
            </p>
          </div>
        ) : motionType === 'slide_up' ? (
          /* 5. Slide Up / Fade In Live Sequence */
          <div
            key={activeWordIndex}
            style={{
              animation: 'slideUpFadeAnim 0.65s ease-out',
            }}
          >
            <p
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: primaryColor,
                fontSize: `${fontSize * scale}px`,
                lineHeight: 1.25,
                fontWeight: 700,
                textTransform: isUppercase ? 'uppercase' : 'none',
                WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
                paintOrder: 'stroke fill',
                textShadow: glowShadow,
              }}
            >
              {words.map((word, idx) => (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: idx === activeWordIndex ? effectiveActiveColor : primaryColor,
                    fontWeight: idx === activeWordIndex ? 800 : 700,
                    transform: idx === activeWordIndex ? `scale(${wordScaleMultiplier})` : 'scale(1)',
                  }}
                >
                  {word}
                </span>
              ))}
            </p>
          </div>
        ) : motionType === 'bounce_in' ? (
          /* 6. Bounce In / Scene Entry dari atas */
          <div
            key={`bounce-${activeWordIndex}`}
            style={{
              animation: 'bounceInAnim 0.65s cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          >
            <p
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: primaryColor,
                fontSize: `${fontSize * scale}px`,
                lineHeight: 1.25,
                fontWeight: 700,
                textTransform: isUppercase ? 'uppercase' : 'none',
                WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
                paintOrder: 'stroke fill',
                textShadow: glowShadow,
              }}
            >
              {words.map((word, idx) => (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: idx === activeWordIndex ? effectiveActiveColor : primaryColor,
                    fontWeight: idx === activeWordIndex ? 800 : 700,
                    transform: idx === activeWordIndex ? `scale(${wordScaleMultiplier})` : 'scale(1)',
                  }}
                >
                  {word}
                </span>
              ))}
            </p>
          </div>
        ) : motionType === 'zoom_flash' ? (
          /* 7. Zoom Flash / Kata aktif meledak + flash */
          <p
            style={{
              fontFamily: font === 'Poppins' ? 'sans-serif' : font,
              color: primaryColor,
              fontSize: `${fontSize * scale}px`,
              lineHeight: 1.25,
              fontWeight: 700,
              textTransform: isUppercase ? 'uppercase' : 'none',
              WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
              paintOrder: 'stroke fill',
              textShadow: glowShadow,
            }}
          >
            {words.map((word, idx) => {
              const isActive = idx === activeWordIndex;
              return (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: isActive ? effectiveActiveColor : primaryColor,
                    fontWeight: isActive ? 900 : 700,
                    display: 'inline-block',
                    animation: isActive ? 'zoomFlashAnim 0.65s ease-out' : undefined,
                    textShadow: isActive ? glowShadow : baseShadow,
                  }}
                >
                  {word}
                </span>
              );
            })}
          </p>
        ) : motionType === 'glitch_reveal' ? (
          /* 8. Glitch Reveal / Shake digital + inversi sesaat */
          <div
            key={`glitch-${activeWordIndex}`}
            style={{
              animation: 'glitchRevealAnim 0.5s steps(2, end)',
            }}
          >
            <p
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: primaryColor,
                fontSize: `${fontSize * scale}px`,
                lineHeight: 1.25,
                fontWeight: 700,
                textTransform: isUppercase ? 'uppercase' : 'none',
                WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
                paintOrder: 'stroke fill',
                textShadow: '2px 0 rgba(255,0,128,0.55), -2px 0 rgba(0,255,255,0.55)',
              }}
            >
              {words.map((word, idx) => (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: idx === activeWordIndex ? effectiveActiveColor : primaryColor,
                    fontWeight: idx === activeWordIndex ? 800 : 700,
                  }}
                >
                  {word}
                </span>
              ))}
            </p>
          </div>
        ) : (
          /* 2. Karaoke / Active Word Highlight (Default) */
          <p
            style={{
              fontFamily: font === 'Poppins' ? 'sans-serif' : font,
              color: primaryColor,
              fontSize: `${fontSize * scale}px`,
              lineHeight: 1.25,
              fontWeight: 700,
              textTransform: isUppercase ? 'uppercase' : 'none',
              WebkitTextStroke: strokeWidth > 0 ? `${strokeWidth.toFixed(2)}px rgba(0,0,0,0.95)` : undefined,
              paintOrder: 'stroke fill',
              textShadow: glowShadow,
            }}
          >
            {words.map((word, idx) => {
              const isActive = idx === activeWordIndex;
              return (
                <span
                  key={idx}
                  className="inline-block mr-1.5 transition-all duration-150"
                  style={{
                    color: isActive ? effectiveActiveColor : primaryColor,
                    fontWeight: isActive ? 800 : 700,
                    transform: isActive ? `scale(${wordScaleMultiplier})` : 'scale(1)',
                    textShadow: isActive ? glowShadow : baseShadow,
                  }}
                >
                  {word}
                </span>
              );
            })}
          </p>
        )}
      </div>

      {/* Children UI Overlays (Notch, Grid guides, Play/Pause overlay button) */}
      {children && (
        <div className="absolute inset-0 pointer-events-none z-20">
          {children}
        </div>
      )}

      {/* Darken background saat intro freeze frame aktif */}
      {overlayIntro && overlayIntroPause && (
        <div className="absolute inset-0 bg-black/45 z-25 pointer-events-none transition-opacity duration-300" />
      )}

      {/* Motion Graphics Overlay preview (di atas subtitle) */}
      {overlayIntro && (
        <div className="absolute left-0 right-0 z-30 text-center pointer-events-none px-3" style={{ top: '15%' }}>
          <span
            className="inline-block max-w-[90%] font-black text-white px-3 py-1.5 rounded-lg whitespace-pre-wrap break-words leading-tight shadow-lg border border-white/20 backdrop-blur-sm"
            style={{
              fontSize: `${Math.max(9, Math.min(14, fontSize * scale * (overlayIntro.length > 30 ? 0.65 : 0.85)))}px`,
              backgroundColor: 'rgba(0,0,0,0.75)',
              textShadow: '1px 1px 2px rgba(0,0,0,0.9)'
            }}
          >
            {overlayIntro}
          </span>
        </div>
      )}
      {overlayLowerThird && (
        <div className="absolute left-4 z-30 pointer-events-none" style={{ top: '70%' }}>
          <span className="inline-block font-bold text-white px-2 py-0.5 rounded" style={{ fontSize: `${Math.max(8, fontSize * scale * 0.5)}px`, backgroundColor: 'rgba(0,0,0,0.55)' }}>
            {overlayLowerThird}
          </span>
        </div>
      )}
      {overlayOutro && (
        <div className="absolute left-0 right-0 z-30 text-center pointer-events-none px-4" style={{ top: '80%' }}>
          <span className="inline-block font-bold text-white px-3 py-1 rounded-lg" style={{ fontSize: `${Math.max(9, fontSize * scale * 0.6)}px`, backgroundColor: 'rgba(0,0,0,0.6)' }}>
            {overlayOutro}
          </span>
        </div>
      )}
    </div>
  );
};

export default SubtitleFrame;
