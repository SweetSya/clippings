import React, { useEffect, useRef, useState } from 'react';
import { SubtitleMotionType } from '../types';

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
  /** Isi layar di belakang subtitle — mis. elemen <video> di Clip Studio. */
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
  children,
  className = '',
}) => {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [frameWidth, setFrameWidth] = useState(0);

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
  const wordScaleMultiplier = enableDynamicScaling ? 1.22 : 1.08;

  // Smart emoji prefix injection for preview
  const displayEmoji = enableEmojiInjection ? '🔥 ' : '';
  const effectiveHighlightWord = highlightWord;
  const effectiveSampleText = enableEmojiInjection && !sampleText.includes('🔥') && !sampleText.includes('💰')
    ? `${displayEmoji}${sampleText}`
    : sampleText;

  // Shadow style with optional neon glow
  const baseShadow = shadowOffset > 0 ? `${shadowOffset.toFixed(2)}px ${shadowOffset.toFixed(2)}px 0 rgba(0,0,0,0.9)` : 'none';
  const glowShadow = glowEffect
    ? `0 0 ${(12 * scale).toFixed(1)}px ${activeColor}, 0 0 ${(24 * scale).toFixed(1)}px ${activeColor}, ${baseShadow}`
    : baseShadow;

  return (
    <div
      ref={frameRef}
      className={`relative bg-black overflow-hidden select-none ${className}`}
      style={{ aspectRatio: `${SCRIPT_WIDTH} / ${SCRIPT_HEIGHT}` }}
    >
      {/* Dynamic Keyframes for Hormozi Pop and Slide Up */}
      <style>{`
        @keyframes hormoziPopAnim {
          0% { transform: scale(1.22); opacity: 0.9; }
          40% { transform: scale(1.0); opacity: 1; }
          100% { transform: scale(1.0); opacity: 1; }
        }
        @keyframes slideUpFadeAnim {
          0% { transform: translateY(14px); opacity: 0.3; }
          100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes typewriterCursor {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>

      {children}

      <div
        className="absolute z-10 text-center pointer-events-none flex flex-col items-center justify-center"
        style={{
          left: `${(SIDE_MARGIN / SCRIPT_WIDTH) * 100}%`,
          right: `${(SIDE_MARGIN / SCRIPT_WIDTH) * 100}%`,
          bottom: `${(effectiveMarginV / SCRIPT_HEIGHT) * 100}%`,
        }}
      >
        {motionType === 'single_word_pop' ? (
          /* 1. Single Word Pop / Bouncy (Hormozi Style) */
          <div
            className="inline-block"
            style={{
              animation: 'hormoziPopAnim 1.4s infinite cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          >
            <span
              style={{
                fontFamily: font === 'Poppins' ? 'sans-serif' : font,
                color: effectiveActiveColor,
                fontSize: `${fontSize * scale * (enableDynamicScaling ? 1.25 : 1.15)}px`,
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
              {displayEmoji}{effectiveHighlightWord}
            </span>
          </div>
        ) : motionType === 'background_box' ? (
          /* 3. Background Box / Highlighter Sticker (CapCut Style) */
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
            {effectiveSampleText.split(effectiveHighlightWord).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span
                    className="inline-block mx-1 rounded-sm shadow-md align-baseline"
                    style={{
                      backgroundColor: highlightBgColor,
                      color: '#1C1917',
                      WebkitTextStroke: '0px transparent',
                      textShadow: 'none',
                      padding: `${2 * scale}px ${8 * scale}px`,
                      borderRadius: `${4 * scale}px`,
                      fontWeight: 900,
                      transform: `scale(${wordScaleMultiplier})`,
                    }}
                  >
                    {effectiveHighlightWord}
                  </span>
                )}
              </React.Fragment>
            ))}
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
              {effectiveSampleText.split(effectiveHighlightWord).map((part, i, arr) => (
                <React.Fragment key={i}>
                  {part}
                  {i < arr.length - 1 && (
                    <span
                      style={{
                        color: effectiveActiveColor,
                        fontWeight: 800,
                        transform: `scale(${wordScaleMultiplier})`,
                        display: 'inline-block',
                      }}
                    >
                      {effectiveHighlightWord}
                    </span>
                  )}
                </React.Fragment>
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
          /* 5. Slide Up / Fade In */
          <div
            style={{
              animation: 'slideUpFadeAnim 1.8s infinite ease-out',
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
              {effectiveSampleText.split(effectiveHighlightWord).map((part, i, arr) => (
                <React.Fragment key={i}>
                  {part}
                  {i < arr.length - 1 && (
                    <span
                      style={{
                        color: effectiveActiveColor,
                        fontWeight: 800,
                        transform: `scale(${wordScaleMultiplier})`,
                        display: 'inline-block',
                      }}
                    >
                      {effectiveHighlightWord}
                    </span>
                  )}
                </React.Fragment>
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
            {effectiveSampleText.split(effectiveHighlightWord).map((part, i, arr) => (
              <React.Fragment key={i}>
                {part}
                {i < arr.length - 1 && (
                  <span
                    style={{
                      color: effectiveActiveColor,
                      fontWeight: 800,
                      transform: `scale(${wordScaleMultiplier})`,
                      display: 'inline-block',
                    }}
                  >
                    {effectiveHighlightWord}
                  </span>
                )}
              </React.Fragment>
            ))}
          </p>
        )}
      </div>
    </div>
  );
};

export default SubtitleFrame;

