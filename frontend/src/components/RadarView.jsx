import React, { useState, useEffect, useRef } from "react";
import { getRadarFeed } from "../api";
import {
  FlameIcon,
  GlobeIcon,
  CpuIcon,
  ActivityIcon,
  TrendingUpIcon,
  ZapIcon,
  AlertTriangleIcon,
  SparklesIcon,
  RefreshIcon,
  RadarSignalIcon,
} from "./Icons";

const EMERGENCY_FALLBACK_ITEMS = [
  {
    id: "radar_client_1",
    title: "Viral Social Media Audio Claiming New 500-Rupee Notes With Star Symbol Are Invalid",
    summary: "Audio messages circulating on WhatsApp claim that currency notes with a star mark between serial digits are fake or banned by the Reserve Bank of India. Fact-checking agencies confirm these are genuine replacement notes.",
    category: "Markets & Finance",
    velocity: "HIGH",
    disputed_flag: true,
    source_preview: "Factly India",
    published_time: "12m ago",
    prefilled_query: "Is 500 rupee note with star symbol invalid or fake currency RBI clarification."
  },
  {
    id: "radar_client_2",
    title: "ISRO & NASA Finalize Readiness Protocols for NISAR Dual-Frequency Earth Satellite",
    summary: "Joint space agencies confirm completion of synthetic aperture radar antenna testing ahead of planned equatorial orbit launch for global environmental monitoring.",
    category: "Science & Health",
    velocity: "HIGH",
    disputed_flag: false,
    source_preview: "The Hindu Science",
    published_time: "18m ago",
    prefilled_query: "ISRO and NASA NISAR satellite launch and antenna testing readiness."
  },
  {
    id: "radar_client_3",
    title: "OpenAI & Anthropic Release Joint Safety Evaluation Protocol for Agentic Autonomous Workflows",
    summary: "Leading AI laboratories establish new alignment benchmarks to stress-test multi-turn autonomous coding agents against prompt injection and unauthorized API execution.",
    category: "Tech & AI",
    velocity: "SURGING",
    disputed_flag: false,
    source_preview: "The Verge",
    published_time: "25m ago",
    prefilled_query: "OpenAI Anthropic AI safety evaluation protocols for autonomous agents."
  },
  {
    id: "radar_client_4",
    title: "Debunked: Viral Video Claiming Sudden Infrastructure Bridge Collapse in Gujarat is CGI",
    summary: "A viral video purporting to capture a sudden bridge collapse in Gujarat has been debunked by forensic analysis as a digital 3D architectural rendering simulation from an overseas studio.",
    category: "World & Politics",
    velocity: "HIGH",
    disputed_flag: true,
    source_preview: "Alt News Fact Check",
    published_time: "34m ago",
    prefilled_query: "Gujarat bridge collapse viral video fact check CGI simulation."
  },
  {
    id: "radar_client_5",
    title: "Reserve Bank of India Clarifies Guidelines on UPI Merchant Surcharges and Wallet Transactions",
    summary: "The central bank reiterates that standard peer-to-peer and merchant UPI transactions remain completely free for retail customers following misleading social media rumors.",
    category: "Markets & Finance",
    velocity: "SURGING",
    disputed_flag: true,
    source_preview: "Moneycontrol",
    published_time: "42m ago",
    prefilled_query: "RBI clarification on UPI surcharge fees for normal user bank transactions."
  },
  {
    id: "radar_client_6",
    title: "Deepfake Audio Warning: Election Commission Issues Alert on AI-Cloned Candidate Calls",
    summary: "Election oversight monitors flag automated robocall campaigns using synthetic voice models mimicking regional candidates to mislead voters regarding polling schedule hours.",
    category: "World & Politics",
    velocity: "HIGH",
    disputed_flag: true,
    source_preview: "Times of India",
    published_time: "50m ago",
    prefilled_query: "Election Commission alert on AI deepfake audio robocalls and cloned voices."
  }
];

export default function RadarView({ onVerifyStory }) {
  const [radarData, setRadarData] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [selectedCountry, setSelectedCountry] = useState("IN");
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [verifyingId, setVerifyingId] = useState(null);
  const [justUpdated, setJustUpdated] = useState(false);

  // Approach A: Pending new stories notification state
  const [pendingNewData, setPendingNewData] = useState(null);
  const [pendingNewCount, setPendingNewCount] = useState(0);

  const selectedCategoryRef = useRef(selectedCategory);
  selectedCategoryRef.current = selectedCategory;

  const selectedCountryRef = useRef(selectedCountry);
  selectedCountryRef.current = selectedCountry;

  const radarDataRef = useRef(radarData);
  radarDataRef.current = radarData;

  const COUNTRIES = [
    { code: "IN", name: "India", flag: "🇮🇳" },
    { code: "US", name: "United States", flag: "🇺🇸" },
    { code: "GB", name: "United Kingdom", flag: "🇬🇧" },
    { code: "GL", name: "Global Edition", flag: "🌍" },
  ];

  const categories = [
    { label: "All Trending", val: "All", icon: <FlameIcon size={14} className="radar-cat-icon" /> },
    { label: "World & Politics", val: "World & Politics", icon: <GlobeIcon size={14} className="radar-cat-icon" /> },
    { label: "Tech & AI", val: "Tech & AI", icon: <CpuIcon size={14} className="radar-cat-icon" /> },
    { label: "Science & Health", val: "Science & Health", icon: <ActivityIcon size={14} className="radar-cat-icon" /> },
    { label: "Markets & Finance", val: "Markets & Finance", icon: <TrendingUpIcon size={14} className="radar-cat-icon" /> },
  ];

  // Fetch when category or country changes
  useEffect(() => {
    fetchFeed(selectedCategory, selectedCountry, false, false, false);
    setPendingNewData(null);
    setPendingNewCount(0);
  }, [selectedCategory, selectedCountry]);

  // Silent Background Polling Engine (Every 30s)
  useEffect(() => {
    const interval = setInterval(() => {
      // Trigger silent background poll with rotation without touching manual refresh state
      fetchFeed(selectedCategoryRef.current, selectedCountryRef.current, true, false, true);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Client-Side Live Relative Timestamp Engine (ticks every 10 seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      setRadarData((prev) => {
        if (!prev || !prev.items) return prev;
        const now = new Date();
        const updatedItems = prev.items.map((item) => {
          if (!item.pub_date_iso) return item;
          try {
            const pubDate = new Date(item.pub_date_iso);
            const diffMins = Math.max(0, Math.floor((now - pubDate) / 60000));
            let timeStr = "Just now";
            if (diffMins >= 1 && diffMins < 60) {
              timeStr = `${diffMins}m ago`;
            } else if (diffMins >= 60 && diffMins < 1440) {
              timeStr = `${Math.floor(diffMins / 60)}h ago`;
            } else if (diffMins >= 1440) {
              timeStr = `${Math.floor(diffMins / 1440)}d ago`;
            }
            return { ...item, published_time: timeStr };
          } catch (e) {
            return item;
          }
        });
        return { ...prev, items: updatedItems };
      });
    }, 10000);

    return () => clearInterval(timer);
  }, []);

  const fetchFeed = async (
    cat = "All",
    ctry = selectedCountryRef.current,
    isBackground = false,
    isManualRefresh = false,
    rotate = false
  ) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else if (!isBackground) {
      setLoading(true);
    }
    setError("");

    try {
      let data = await getRadarFeed(cat, ctry, rotate);

      if (!data || !data.items || data.items.length === 0) {
        // Fallback to client emergency items if response items are empty
        const fallbackItems = EMERGENCY_FALLBACK_ITEMS.filter(
          (it) => cat === "All" || it.category === cat
        );
        data = {
          last_updated: data?.last_updated || new Date().toISOString(),
          total_active_stories: fallbackItems.length,
          categories: ["All", "World & Politics", "Tech & AI", "Science & Health", "Markets & Finance"],
          country: ctry,
          items: fallbackItems
        };
      }

      const currentItems = radarDataRef.current?.items || [];

      if (isBackground && currentItems.length > 0) {
        // Approach A: Check if any stories are new compared to current screen
        const currentTitles = new Set(
          currentItems.map((it) => (it.title || "").trim().toLowerCase())
        );
        const freshItems = (data.items || []).filter(
          (it) => it.title && !currentTitles.has(it.title.trim().toLowerCase())
        );

        if (freshItems.length > 0) {
          // Do not abruptly replace the cards; prompt the user gracefully with the floating banner!
          setPendingNewData(data);
          setPendingNewCount(freshItems.length);
        }
      } else {
        // Immediate user-initiated fetch / category switch / manual refresh
        setRadarData(data);
        setPendingNewData(null);
        setPendingNewCount(0);
        setJustUpdated(true);
        setTimeout(() => setJustUpdated(false), 2500);
      }
    } catch (err) {
      if (!isBackground) {
        if (!radarDataRef.current?.items?.length) {
          // Populate with emergency items on connection failure so UI is never a blank screen
          const fallbackItems = EMERGENCY_FALLBACK_ITEMS.filter(
            (it) => cat === "All" || it.category === cat
          );
          setRadarData({
            last_updated: new Date().toISOString(),
            total_active_stories: fallbackItems.length,
            categories: ["All", "World & Politics", "Tech & AI", "Science & Health", "Markets & Finance"],
            country: ctry,
            items: fallbackItems
          });
        }
        setError(err.message || "Failed to load breaking news radar stream.");
      }
    } finally {
      if (!isBackground) {
        setLoading(false);
      }
      if (isManualRefresh) {
        setIsRefreshing(false);
      }
    }
  };

  const handleApplyPendingStories = () => {
    if (pendingNewData) {
      setRadarData(pendingNewData);
      setPendingNewData(null);
      setPendingNewCount(0);
      setJustUpdated(true);
      setTimeout(() => setJustUpdated(false), 2500);
      window.scrollTo({ top: 100, behavior: "smooth" });
    }
  };

  const handleAuditClick = (item) => {
    setVerifyingId(item.id);
    if (onVerifyStory) {
      onVerifyStory({
        title: item.title,
        text: item.prefilled_query || item.summary,
        sourceUrl: item.link || "",
      });
    }
  };

  const formatToIST = (dateStr) => {
    if (!dateStr) return "";
    try {
      const iso = dateStr.endsWith("Z")
        ? dateStr
        : dateStr.replace(" UTC", "Z").replace(" ", "T");
      const d = new Date(iso);
      if (isNaN(d.getTime())) return dateStr;
      return (
        d
          .toLocaleTimeString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
          })
          .toUpperCase() + " IST"
      );
    } catch (e) {
      return dateStr;
    }
  };

  return (
    <div className="radar-page-container">
      {/* Header */}
      <div className="radar-header">
        <div className="radar-pill">
          <span className="live-dot pulse-amber"></span>
          <span>Live Detection Stream</span>
          <span className="radar-live-indicator" title="Stream continuously updating in background">
            <ZapIcon size={11} className="inline-zap" /> LIVE
          </span>
        </div>
        <h1 className="radar-title">Breaking News Radar & Viral Claims</h1>
        <p className="radar-subtitle">
          Autonomous real-time stream tracking surging viral claims, breaking headlines, and unverified rumors across global media networks.
        </p>
      </div>

      {/* Control Bar: Categories, Country Selector & Controls */}
      <div className="radar-controls-bar">
        {/* Categories Bar */}
        <div className="radar-category-pills">
          {categories.map((c) => (
            <button
              key={c.val}
              type="button"
              className={`radar-cat-btn ${selectedCategory === c.val ? "active" : ""}`}
              onClick={() => setSelectedCategory(c.val)}
            >
              {c.icon}
              <span>{c.label}</span>
            </button>
          ))}
        </div>

        {/* Right Tools: Country Selector, Status & Refresh */}
        <div className="radar-meta-controls">
          {/* Country Regional Edition Selector */}
          <div className="radar-country-selector-wrapper" title="Select regional breaking news edition">
            <span className="country-globe-icon"><GlobeIcon size={14} /></span>
            <select
              className="radar-country-select"
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              aria-label="Select News Region"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.name}
                </option>
              ))}
            </select>
          </div>

          {radarData?.last_updated && (
            <span
              className="radar-updated-tag"
              title={`Last feed synchronization: ${formatToIST(radarData.last_updated)}`}
            >
              Updated: {formatToIST(radarData.last_updated)}
            </span>
          )}

          {justUpdated && (
            <span className="radar-flash-tag animate-fade">
              <SparklesIcon size={12} className="inline-sparkle" /> Fresh Stream
            </span>
          )}

          {/* Manual Refresh Button (rotates candidate buffer immediately) */}
          <button
            type="button"
            className="radar-refresh-btn"
            onClick={() => {
              fetchFeed(selectedCategory, selectedCountry, false, true, true);
            }}
            disabled={loading || isRefreshing}
            title="Rotate to fresh stories from buffer pool now"
            aria-label="Refresh stories stream"
          >
            <span className={isRefreshing ? "spin-icon" : ""}>
              <RefreshIcon size={15} />
            </span>
          </button>
        </div>
      </div>

      {/* Approach A: Floating New Stories Banner */}
      {pendingNewCount > 0 && (
        <div
          className="radar-new-stories-banner"
          onClick={handleApplyPendingStories}
          role="button"
          tabIndex={0}
          title="Click to display freshly retrieved stories"
        >
          <span className="radar-pill-dot pulse-emerald"></span>
          <span className="radar-banner-text">
            <SparklesIcon size={14} className="banner-sparkle-icon" /> <strong>{pendingNewCount} New Breaking Stories</strong> Available — Click to view latest updates
          </span>
          <span className="radar-banner-action">View Stream ↑</span>
        </div>
      )}

      {error && (
        <div className="radar-error-banner">
          <span><AlertTriangleIcon size={14} className="inline-alert" /> {error}</span>
          <button type="button" onClick={() => fetchFeed(selectedCategory, selectedCountry, false, false, false)} className="retry-btn">
            Retry
          </button>
        </div>
      )}

      {/* Loading State for initial fetch */}
      {loading && !radarData ? (
        <div className="radar-loading-container">
          <div className="radar-pulse-ring"></div>
          <p className="radar-loading-text">
            Scanning {COUNTRIES.find((c) => c.code === selectedCountry)?.name || "regional"} live news feeds & viral networks...
          </p>
        </div>
      ) : !radarData?.items?.length ? (
        <div className="radar-empty-box">
          <span className="radar-empty-icon"><RadarSignalIcon size={36} /></span>
          <h3>{selectedCategory === "All" ? "Scanning live wires..." : `No active stories in "${selectedCategory}"`}</h3>
          <p>{selectedCategory === "All" ? "Live streams are synchronizing. Click below to refresh the feed." : 'Try switching to "All Trending" or refreshing the feed.'}</p>
          <button
            type="button"
            className="btn-reset-filters"
            onClick={() => {
              if (selectedCategory !== "All") {
                setSelectedCategory("All");
              } else {
                fetchFeed("All", selectedCountry, false, true, false);
              }
            }}
          >
            {selectedCategory === "All" ? "↻ Refresh Live Stream" : "View All Trending"}
          </button>
        </div>
      ) : (
        /* Stories Grid */
        <div className="radar-stories-grid">
          {radarData.items.map((item) => {
            const isHigh = item.velocity === "HIGH";
            const isSurging = item.velocity === "SURGING";

            return (
              <div
                key={item.id}
                className={`radar-story-card ${item.disputed_flag ? "card-disputed" : ""}`}
              >
                {/* Card Top: Category, Velocity, Timestamp */}
                <div className="story-card-top">
                  <div className="story-badge-cluster">
                    <span className="story-category-tag">{item.category}</span>
                    <span
                      className={`story-velocity-pill ${
                        isHigh ? "velocity-high" : isSurging ? "velocity-surging" : "velocity-mod"
                      }`}
                    >
                      {isHigh ? (
                        <>
                          <FlameIcon size={12} className="inline-badge-icon" /> High Velocity
                        </>
                      ) : isSurging ? (
                        <>
                          <ZapIcon size={12} className="inline-badge-icon" /> Surging
                        </>
                      ) : (
                        <>
                          <TrendingUpIcon size={12} className="inline-badge-icon" /> Active
                        </>
                      )}
                    </span>
                    {item.disputed_flag && (
                      <span className="story-disputed-tag" title="Flagged as unverified or disputed rumor">
                        <AlertTriangleIcon size={12} className="inline-badge-icon" /> Disputed Rumor
                      </span>
                    )}
                  </div>
                  <span className="story-time-tag" title={item.pub_date_iso || ""}>
                    {item.published_time}
                  </span>
                </div>

                {/* Headline */}
                <h3 className="story-card-title">{item.title}</h3>

                {/* Summary */}
                <p className="story-card-summary">{item.summary}</p>

                {/* Card Bottom: Origin Preview & Action Button */}
                <div className="story-card-bottom">
                  <div className="story-origin">
                    <span className="origin-label">Source Context:</span>
                    <span className="origin-val">{item.source_preview}</span>
                  </div>

                  <button
                    type="button"
                    className="audit-story-btn"
                    onClick={() => handleAuditClick(item)}
                    disabled={verifyingId === item.id}
                  >
                    {verifyingId === item.id ? (
                      <>
                        <span className="btn-spinner"></span> Launching Audit...
                      </>
                    ) : (
                      <>
                        <ZapIcon size={13} className="inline-btn-icon" />
                        <span>Verify Story</span>
                        <span className="audit-arrow">→</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
