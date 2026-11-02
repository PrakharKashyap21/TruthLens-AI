import React, { useState, useEffect } from "react";

const SPLASH_STORAGE_KEY = "truthlens_intro_shown_v1";

export default function SplashScreen({ onComplete }) {
  const [isFadingOut, setIsFadingOut] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if session has already seen the intro
    try {
      if (sessionStorage.getItem(SPLASH_STORAGE_KEY)) {
        if (onComplete) onComplete();
        return;
      }
    } catch (e) {
      // ignore storage errors
    }

    setIsVisible(true);

    // Sequence timing
    // 0.0s - 0.9s: Reveal logo, wordmark, hairline, and tagline
    // 0.95s: Start gentle fade out
    const fadeTimer = setTimeout(() => {
      setIsFadingOut(true);
    }, 1050);

    // 1.35s: Fully unmount splash and hand over to app
    const finishTimer = setTimeout(() => {
      try {
        sessionStorage.setItem(SPLASH_STORAGE_KEY, "true");
      } catch (e) {}
      setIsVisible(false);
      if (onComplete) onComplete();
    }, 1380);

    // Allow user to instantly dismiss by clicking or hitting any key
    const handleDismiss = () => {
      try {
        sessionStorage.setItem(SPLASH_STORAGE_KEY, "true");
      } catch (e) {}
      setIsFadingOut(true);
      setTimeout(() => {
        setIsVisible(false);
        if (onComplete) onComplete();
      }, 180);
    };

    window.addEventListener("keydown", handleDismiss, { once: true });

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(finishTimer);
      window.removeEventListener("keydown", handleDismiss);
    };
  }, [onComplete]);

  if (!isVisible) return null;

  return (
    <div
      className={`splash-overlay ${isFadingOut ? "splash-fade-out" : ""}`}
      onClick={() => {
        setIsFadingOut(true);
        setTimeout(() => {
          setIsVisible(false);
          if (onComplete) onComplete();
        }, 180);
      }}
      role="banner"
      aria-label="TruthLens AI Intro"
    >
      <div className="splash-ambient-halo" aria-hidden="true" />

      <div className="splash-content">
        {/* Emblem & Brand Header */}
        <div className="splash-brand-row">
          <div className="splash-emblem-wrap">
            <img src="/favicon.svg" alt="TruthLens Emblem" className="splash-emblem" />
          </div>
          <div className="splash-title-group">
            <span className="splash-wordmark">TruthLens</span>
            <span className="splash-badge-ai">AI</span>
          </div>
        </div>

        {/* Delicate Hairline Separator */}
        <div className="splash-hairline" />

        {/* Editorial Subtitle */}
        <p className="splash-tagline">
          Verifying facts behind the headlines<span className="splash-dot">.</span>
        </p>
      </div>

      <span className="splash-skip-hint">Click anywhere or press any key to skip</span>
    </div>
  );
}
