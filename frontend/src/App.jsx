import React, { useState, useEffect, useRef } from "react";
import OmniSearchInput from "./components/OmniSearchInput";
import V2VerificationResult from "./components/V2VerificationResult";
import HistoryDrawer from "./components/HistoryDrawer";
import ArchitectureSection from "./components/ArchitectureSection";
import DocumentAuditView from "./components/DocumentAuditView";
import AnalyticsView from "./components/AnalyticsView";
import RadarView from "./components/RadarView";
import ImageAuditView from "./components/ImageAuditView";
import AudioAuditView from "./components/AudioAuditView";
import ChatbotBridgeView from "./components/ChatbotBridgeView";
import ExtensionModal from "./components/ExtensionModal";
import AuthModal from "./components/AuthModal";
import {
  NavVerifyIcon,
  NavRadarIcon,
  NavImageIcon,
  NavAudioIcon,
  NavChatbotIcon,
  NavDocIcon,
  NavAnalyticsIcon,
  NavClockIcon,
  PuzzleIcon,
  UserIcon,
  LogOutIcon,
  ShieldCheckIcon
} from "./components/Icons";
import { verifyNewsV2, fetchCurrentUser, pingBackendHealth } from "./api";

const LOCAL_STORAGE_KEY = "truthlens_verification_history_v1";

function App() {
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab");
      if (tabParam === "chatbot" || window.location.hash === "#chatbot") return "chatbot";
      if (tabParam === "radar" || window.location.hash === "#radar") return "radar";
      if (tabParam === "analytics" || window.location.hash === "#analytics") return "analytics";
    } catch (e) {
      // ignore
    }
    return "verify";
  });

  const [verifyModality, setVerifyModality] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab");
      const modalityParam = params.get("modality");
      if (modalityParam === "audio" || tabParam === "audio-audit" || window.location.hash === "#audio-audit") return "audio";
      if (modalityParam === "image" || tabParam === "image-audit" || window.location.hash === "#image-audit") return "image";
      if (modalityParam === "doc" || tabParam === "doc-audit" || window.location.hash === "#doc-audit") return "doc";
    } catch (e) {
      // ignore
    }
    return "search";
  });
  const [isLoading, setIsLoading] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [activeQuery, setActiveQuery] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const q = params.get("q") || params.get("claim") || params.get("text");
      const title = params.get("title") || "";
      if (q) return { title, text: q };
    } catch (e) {
      // ignore
    }
    return { title: "", text: "" };
  });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isExtensionModalOpen, setIsExtensionModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem("truthlens_user_profile");
      return savedUser ? JSON.parse(savedUser) : null;
    } catch (e) {
      return null;
    }
  });
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [error, setError] = useState("");
  const [validationError, setValidationError] = useState("");
  const autoVerifiedRef = useRef(false);

  // Validate active auth session on app mount & wake up cloud backend
  useEffect(() => {
    // 1. Silent wake-up ping for Render backend (solves cold start delay)
    pingBackendHealth();

    // 2. Validate active auth session
    const token = localStorage.getItem("truthlens_auth_token");
    if (token) {
      fetchCurrentUser().then((u) => {
        if (u) {
          setCurrentUser(u);
          localStorage.setItem("truthlens_user_profile", JSON.stringify(u));
        }
      });
    }
  }, []);

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setIsAuthModalOpen(false);
  };

  const handleLogout = () => {
    localStorage.removeItem("truthlens_auth_token");
    localStorage.removeItem("truthlens_user_profile");
    setCurrentUser(null);
    setIsUserMenuOpen(false);
  };

  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      console.warn("Failed to load verification history from localStorage", e);
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
      console.warn("Failed to save history to localStorage", e);
    }
  }, [history]);

  const handleVerify = async ({ title, text, sourceUrl, language = "auto" }) => {
    setIsLoading(true);
    setError("");
    setValidationError("");
    setActiveQuery({ title: title || "", text: text || "" });

    try {
      const data = await verifyNewsV2(title, text, language, false, sourceUrl);
      setVerificationResult(data);

      const newItem = {
        id: `tl_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        timestamp: new Date().toISOString(),
        title: title || "",
        text: text || "",
        sourceUrl: sourceUrl || "",
        result: data,
      };

      setHistory((prev) => [newItem, ...prev.filter((item) => item.text !== text)].slice(0, 15));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err.message || "An error occurred while performing real-time verification.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectHistoryItem = (item) => {
    setActiveTab("verify");
    setVerifyModality("search");
    setVerificationResult(item.result);
    setActiveQuery({ title: item.title || "", text: item.text || "" });
    setError("");
    setValidationError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleClearHistory = () => {
    setHistory([]);
  };

  // URL Query Parameter Auto-Verification & Demo Loader
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const queryParam = params.get("q") || params.get("claim") || params.get("text");
      const titleParam = params.get("title") || "";

      if (queryParam && !autoVerifiedRef.current) {
        autoVerifiedRef.current = true;
        setActiveTab("verify");
        setVerifyModality("search");
        handleVerify({ title: titleParam, text: queryParam });
        return;
      }

      if (params.get("demo") === "1" && !verificationResult) {
        if (history.length > 0) {
          handleSelectHistoryItem(history[0]);
        } else {
          setVerificationResult({
            overall_assessment: "SUPPORTED",
            assessment_summary: "Multi-source wire consensus confirms the core factual statements regarding Tata Trent standalone revenue growth and brand store expansion.",
            has_conflict: false,
            claims: [
              {
                claim_id: "claim_demo_1",
                text: "Tata Group retail arm Trent reported standalone revenue surge led by Zudio and Westside expansion.",
                verdict: "SUPPORTED",
                reasoning: "Confirmed by earnings filings and multiple primary financial press reports citing official regulatory disclosures.",
                supporting_evidence_count: 3,
                contradicting_evidence_count: 0,
                neutral_evidence_count: 1,
                evidence: [
                  {
                    id: "ev_1",
                    title: "Tata's Trent reports strong Q2 net profit surge driven by retail network",
                    publisher: "Reuters",
                    domain: "reuters.com",
                    url: "https://reuters.com",
                    snippet: "Trent Ltd posted substantial year-on-year revenue gains as apparel chains Westside and Zudio expanded rapidly across tier-1 and tier-2 markets.",
                    stance: "SUPPORTS"
                  },
                  {
                    id: "ev_2",
                    title: "Trent Q2 financial results: Net profit up, retail footprint expands",
                    publisher: "Bloomberg",
                    domain: "bloomberg.com",
                    url: "https://bloomberg.com",
                    snippet: "Standalone quarterly revenue jumped 46 percent according to stock exchange disclosures filed on Wednesday.",
                    stance: "SUPPORTS"
                  },
                  {
                    id: "ev_3",
                    title: "Financial Express Market Desk: Trent quarterly earnings breakdown",
                    publisher: "Financial Express",
                    domain: "financialexpress.com",
                    url: "https://financialexpress.com",
                    snippet: "Tata-backed fashion and retail enterprise Trent continues robust expansion trajectory.",
                    stance: "SUPPORTS"
                  },
                  {
                    id: "ev_4",
                    title: "Trent Limited corporate overview and regulatory history",
                    publisher: "Wikipedia",
                    domain: "en.wikipedia.org",
                    url: "https://en.wikipedia.org",
                    snippet: "Trent is an Indian retail company and part of the Tata Group, operating Westside and Zudio.",
                    stance: "NEUTRAL"
                  }
                ]
              }
            ],
            service_status: { gemini_api: "ok" }
          });
          setActiveQuery({
            title: "Trent Q2 Revenue Growth",
            text: "Tata Group retail arm Trent reported standalone revenue surge led by Zudio and Westside expansion."
          });
        }
      }
    } catch (e) {
      // ignore
    }
  }, []);

  const handleDeleteHistoryItem = (id) => {
    setHistory((prev) => prev.filter((item) => item.id !== id));
  };

  const handleResetHome = () => {
    setVerificationResult(null);
    setActiveQuery({ title: "", text: "" });
    setError("");
    setValidationError("");
    setVerifyModality("search");
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  };

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [activeTab]);

  const switchTab = (tab) => {
    setActiveTab(tab);
    setError("");
    setValidationError("");
    try {
      let url;
      if (tab === "verify") {
        url = verifyModality === "search" ? window.location.pathname : `?tab=${verifyModality === "audio" ? "audio-audit" : verifyModality === "image" ? "image-audit" : "doc-audit"}`;
      } else {
        url = `?tab=${tab}`;
      }
      window.history.replaceState(null, "", url);
    } catch (e) {
      // ignore
    }
    if (tab === "verify" && verifyModality === "search") {
      handleResetHome();
    }
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  };

  const switchModality = (modality) => {
    setActiveTab("verify");
    setVerifyModality(modality);
    setError("");
    setValidationError("");
    try {
      let url = window.location.pathname;
      if (modality === "audio") url = "?tab=audio-audit";
      else if (modality === "image") url = "?tab=image-audit";
      else if (modality === "doc") url = "?tab=doc-audit";
      window.history.replaceState(null, "", url);
    } catch (e) {
      // ignore
    }
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  };

  const handleNavigateArchitecture = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (activeTab !== "verify" || verifyModality !== "search") {
      setActiveTab("verify");
      setVerifyModality("search");
      try {
        window.history.replaceState(null, "", window.location.pathname);
      } catch (err) {
        // ignore
      }
    }

    const scrollToArch = () => {
      const el = document.getElementById("how-it-works");
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        return true;
      }
      return false;
    };

    if (!scrollToArch()) {
      setTimeout(scrollToArch, 80);
      setTimeout(scrollToArch, 250);
    }
  };

  return (
    <div className="app-layout">
      {/* Ambient Cosmic Aurora Glow */}
      <div className="ambient-background-glow" aria-hidden="true">
        <div className="glow-orb glow-orb-primary" />
        <div className="glow-orb glow-orb-secondary" />
        <div className="glow-orb glow-orb-accent" />
      </div>

      {/* Sleek Top Navbar */}
      <nav className="navbar">
        <div className="nav-brand" onClick={() => switchTab("verify")} role="button" tabIndex={0}>
          <img src="/favicon.svg" alt="TruthLens AI" className="nav-brand-icon" />
          <span className="brand-logo">TruthLens</span>
          <span className="brand-ai">AI</span>
          <span className="nav-badge">Agentic RAG</span>
        </div>

        {/* Primary Page Navigation Tabs (Centered & Balanced) */}
        <div className="nav-center-tabs">
          <button
            type="button"
            className={`nav-tab-link ${activeTab === "verify" ? "active" : ""}`}
            onClick={() => {
              if (activeTab === "verify") {
                setVerifyModality("search");
                handleResetHome();
              } else {
                switchTab("verify");
              }
            }}
          >
            <NavVerifyIcon size={14} /> <span>Live Verify</span>
          </button>
          <button
            type="button"
            className={`nav-tab-link ${activeTab === "radar" ? "active" : ""}`}
            onClick={() => switchTab("radar")}
          >
            <NavRadarIcon size={14} /> <span>Radar</span>
          </button>
          <button
            type="button"
            className={`nav-tab-link ${activeTab === "chatbot" ? "active" : ""}`}
            onClick={() => switchTab("chatbot")}
          >
            <NavChatbotIcon size={14} /> <span>Chatbot Bridge</span>
          </button>
          <button
            type="button"
            className={`nav-tab-link ${activeTab === "analytics" ? "active" : ""}`}
            onClick={() => switchTab("analytics")}
          >
            <NavAnalyticsIcon size={14} /> <span>Analytics</span>
          </button>
        </div>

        {/* Clean Right-Side Actions */}
        <div className="nav-actions">
          {activeTab === "verify" && verifyModality === "search" && verificationResult && (
            <button
              type="button"
              className="nav-btn nav-new-search-pill"
              onClick={handleResetHome}
              title="Start a new news or claim verification"
            >
              <span className="plus-symbol">+</span> <span>New Search</span>
            </button>
          )}

          <button
            type="button"
            className="nav-btn nav-extension-btn"
            onClick={() => setIsExtensionModalOpen(true)}
            title="TruthLens Browser Extension"
          >
            <PuzzleIcon size={15} style={{ color: "#38bdf8" }} />
            <span>Extension</span>
          </button>

          <button
            type="button"
            className="nav-btn nav-history-btn"
            onClick={() => setIsDrawerOpen(true)}
            title="Open Recent Verification History"
          >
            <NavClockIcon size={14} /> <span>History</span>
            {history.length > 0 && <span className="nav-history-count">{history.length}</span>}
          </button>

          {/* Authentication User Pill / Sign In Button */}
          {currentUser ? (
            <div className="nav-user-wrapper">
              <button
                type="button"
                className="nav-btn nav-user-btn"
                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                title="Account & Investigator Profile"
              >
                <span className="user-avatar-badge">
                  {currentUser.name
                    ? currentUser.name
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()
                    : "PK"}
                </span>
                <span className="user-name-text">{currentUser.name.split(" ")[0]}</span>
                <span className="user-menu-chevron">▾</span>
              </button>

              {isUserMenuOpen && (
                <div className="user-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <div className="user-dropdown-header">
                    <div className="user-dropdown-name">{currentUser.name}</div>
                    <div className="user-dropdown-email">{currentUser.email}</div>
                    <div className="user-dropdown-role">
                      <ShieldCheckIcon size={12} style={{ color: "#38bdf8" }} />
                      <span>{currentUser.role || "Senior Fact-Checker"}</span>
                    </div>
                  </div>
                  <div className="user-dropdown-divider" />
                  <div className="user-dropdown-item-info">
                    <span>Cloud Sync:</span> <strong style={{ color: "#34d399" }}>Active</strong>
                  </div>
                  <div className="user-dropdown-divider" />
                  <button
                    type="button"
                    className="user-dropdown-logout-btn"
                    onClick={handleLogout}
                  >
                    <LogOutIcon size={14} />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              type="button"
              className="nav-btn nav-auth-btn"
              onClick={() => setIsAuthModalOpen(true)}
              title="Sign in or create investigator account"
            >
              <UserIcon size={14} style={{ color: "#818cf8" }} />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="main-viewport">
        <div
          key={activeTab + (activeTab === "verify" ? `-${verifyModality}` : "") + (verificationResult ? "-result" : "-landing")}
          className="tab-viewport-fade"
        >
          {activeTab === "chatbot" ? (
            <ChatbotBridgeView
              onOpenInDashboard={(claim) => {
                switchTab("verify");
                setVerifyModality("search");
                handleVerify({ title: "Chat Forward Claim", text: claim });
              }}
            />
          ) : activeTab === "radar" ? (
            <RadarView
              onVerifyStory={(story) => {
                switchTab("verify");
                setVerifyModality("search");
                handleVerify({ title: story.title, text: story.text, sourceUrl: story.sourceUrl });
              }}
            />
          ) : activeTab === "analytics" ? (
            <AnalyticsView />
          ) : (
            /* Live Verify Omni Studio */
            <div className="live-verify-omni-studio">
              {/* Floating Omni Modality Switcher Bar */}
              <div className="omni-modality-wrapper">
                <div className="omni-modality-bar" role="tablist" aria-label="Verification Modality">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={verifyModality === "search"}
                    className={`modality-chip ${verifyModality === "search" ? "active" : ""}`}
                    onClick={() => switchModality("search")}
                    title="Real-Time Text & Web Claim Search"
                  >
                    <NavVerifyIcon size={14} />
                    <span className="modality-chip-text">Text & Claims</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={verifyModality === "audio"}
                    className={`modality-chip ${verifyModality === "audio" ? "active" : ""}`}
                    onClick={() => switchModality("audio")}
                    title="Acoustic Forensics & Speech Fact-Checker"
                  >
                    <NavAudioIcon size={14} />
                    <span className="modality-chip-text">Audio Audit</span>
                    <span className="modality-chip-tag">Mic & Speech</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={verifyModality === "image"}
                    className={`modality-chip ${verifyModality === "image" ? "active" : ""}`}
                    onClick={() => switchModality("image")}
                    title="Image Vision & Deepfake Analysis"
                  >
                    <NavImageIcon size={14} />
                    <span className="modality-chip-text">Image Audit</span>
                    <span className="modality-chip-tag">Vision OCR</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={verifyModality === "doc"}
                    className={`modality-chip ${verifyModality === "doc" ? "active" : ""}`}
                    onClick={() => switchModality("doc")}
                    title="Multi-Assertion Document Dossier"
                  >
                    <NavDocIcon size={14} />
                    <span className="modality-chip-text">Document Audit</span>
                    <span className="modality-chip-tag">PDF Dossier</span>
                  </button>
                </div>
              </div>

              {/* Modality View Content */}
              {verifyModality === "audio" ? (
                <AudioAuditView
                  onAuditToLiveVerify={(story) => {
                    switchModality("search");
                    handleVerify({ title: story.title, text: story.text });
                  }}
                />
              ) : verifyModality === "image" ? (
                <ImageAuditView
                  onAuditToLiveVerify={(story) => {
                    switchModality("search");
                    handleVerify({ title: story.title, text: story.text });
                  }}
                />
              ) : verifyModality === "doc" ? (
                <DocumentAuditView />
              ) : !verificationResult ? (
                /* Initial Minimalist Landing State (Perplexity / Grok style) */
                <div className="hero-landing-container">
                  <div className="hero-center-header">
                    <div className="hero-pill">
                      <span className="live-dot"></span>
                      <span>Real-Time Autonomous Fact-Checking</span>
                    </div>
                    <h1 className="hero-headline">Where claims meet evidence.</h1>
                    <p className="hero-tagline">
                      Verify breaking news, viral statements, and article URLs with real-time web retrieval, deep paragraph extraction, and Google Gemini AI.
                    </p>
                  </div>

                  {/* Omni Search AI Box */}
                  <div className="hero-search-area">
                    <OmniSearchInput
                      onSubmit={handleVerify}
                      isLoading={isLoading}
                      validationError={validationError}
                      setValidationError={setValidationError}
                      initialText={activeQuery.text}
                      initialTitle={activeQuery.title}
                      isCompact={false}
                    />
                  </div>

                  {error && (
                    <div className="error-card-floating" role="alert">
                      <strong>⚠️ Verification Failed:</strong> {error}
                    </div>
                  )}

                  {/* Below-the-fold Architecture Section */}
                  <ArchitectureSection />
                </div>
              ) : (
                /* Active Result State */
                <div className="result-view-container">
                  {/* Compact Search Bar at Top */}
                  <div className="compact-search-container">
                    <OmniSearchInput
                      onSubmit={handleVerify}
                      isLoading={isLoading}
                      validationError={validationError}
                      setValidationError={setValidationError}
                      initialText=""
                      initialTitle=""
                      isCompact={true}
                    />
                  </div>

                  {error && (
                    <div className="error-card-floating" role="alert">
                      <strong>⚠️ Verification Failed:</strong> {error}
                    </div>
                  )}

                  {/* Full Width Verification Report */}
                  <div className="result-report-card">
                    <V2VerificationResult result={verificationResult} />
                  </div>

                  {/* Below-the-fold Architecture Section */}
                  <ArchitectureSection />
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Slide-over Recent History Drawer */}
      <HistoryDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        history={history}
        onSelectHistoryItem={handleSelectHistoryItem}
        onClearHistory={handleClearHistory}
        onDeleteItem={handleDeleteHistoryItem}
      />

      {/* Chrome Extension Showcase & Install Modal */}
      <ExtensionModal
        isOpen={isExtensionModalOpen}
        onClose={() => setIsExtensionModalOpen(false)}
      />

      {/* Cloud Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      {/* Modern Footer */}
      <footer className="footer-bar">
        <div className="footer-content">
          <p className="footer-main-text">
            <strong>TruthLens AI</strong> searches live news, official archives, and investigative journalism to verify facts with transparent citations.
          </p>
          <p className="footer-sub-text">
            Powered by DuckDuckGo, Trafilatura & Google Gemini AI • <a href="#how-it-works" onClick={handleNavigateArchitecture} className="footer-arch-link">System Architecture & Pipeline</a>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
