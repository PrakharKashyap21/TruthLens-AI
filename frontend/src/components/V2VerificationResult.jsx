import React, { useState } from "react";
import EvidenceKnowledgeGraph from "./EvidenceKnowledgeGraph";
import {
  CheckCircleIcon,
  XCircleIcon,
  AlertTriangleIcon,
  HelpCircleIcon,
  CopyIcon,
  DocumentIcon,
  DownloadIcon,
  GlobeIcon,
  NewspaperIcon,
  SparklesIcon,
  ZapIcon
} from "./Icons";

const V2VerificationResult = ({ result }) => {
  if (!result) return null;

  const {
    overall_assessment,
    assessment_summary,
    has_conflict,
    claims,
    service_status,
    disclaimer,
    detected_language = "en",
    language_name = "English",
    vernacular_summary,
    vernacular_overall_verdict,
    is_developing_story = false,
    developing_story_note
  } = result;

  const isVernacular = detected_language && detected_language !== "en";
  const [displayLanguage, setDisplayLanguage] = useState(isVernacular ? "native" : "en");
  const [copied, setCopied] = useState(false);

  React.useEffect(() => {
    if (isVernacular) {
      setDisplayLanguage("native");
    } else {
      setDisplayLanguage("en");
    }
  }, [detected_language, isVernacular]);

  const getVerdictClass = (verdict) => {
    switch (verdict?.toUpperCase()) {
      case "SUPPORTED":
        return "verdict-supported";
      case "CONTRADICTED":
        return "verdict-contradicted";
      case "MISLEADING":
        return "verdict-misleading";
      case "UNVERIFIED":
      default:
        return is_developing_story ? "verdict-unverified verdict-developing" : "verdict-unverified";
    }
  };

  const getVerdictIcon = (verdict) => {
    switch (verdict?.toUpperCase()) {
      case "SUPPORTED":
        return <CheckCircleIcon size={22} style={{ color: "#10b981", verticalAlign: "middle" }} />;
      case "CONTRADICTED":
        return <XCircleIcon size={22} style={{ color: "#ef4444", verticalAlign: "middle" }} />;
      case "MISLEADING":
        return <AlertTriangleIcon size={22} style={{ color: "#f59e0b", verticalAlign: "middle" }} />;
      case "UNVERIFIED":
      default:
        return <HelpCircleIcon size={22} style={{ color: "#94a3b8", verticalAlign: "middle" }} />;
    }
  };

  const getVerdictDescription = (verdict) => {
    switch (verdict?.toUpperCase()) {
      case "SUPPORTED":
        return "All core factual statements in this news claim were directly confirmed by live journalism and credible reporting.";
      case "CONTRADICTED":
        return "Credible external news reports or official sources refute or debunk one or more key assertions in this claim.";
      case "MISLEADING":
        return "This claim mixes verified facts with false, distorted, or unconfirmed claims.";
      case "UNVERIFIED":
      default:
        return "No sufficient indexed news coverage or fact-check records were found. Note: UNVERIFIED indicates a lack of external reporting, not necessarily falsehood.";
    }
  };

  const getStanceBadge = (stance) => {
    switch (stance?.toUpperCase()) {
      case "SUPPORTS":
        return <span className="stance-chip stance-supports">✓ Corroborates</span>;
      case "CONTRADICTS":
        return <span className="stance-chip stance-contradicts">✗ Refutes</span>;
      case "NEUTRAL":
      default:
        return <span className="stance-chip stance-neutral">○ Context</span>;
    }
  };

  const handleCopyReport = () => {
    const reportText = `[TruthLens AI Verification Report]
Overall Verdict: ${overall_assessment}
Summary: ${assessment_summary}

Claims Evaluated:
${(claims || []).map((c, i) => `\n${i + 1}. "${c.text}" -> ${c.verdict}\nReasoning: ${c.reasoning}`).join("\n")}

Sources Consulted:
${(claims || []).flatMap((c) => c.evidence || []).map((e) => `- ${e.publisher}: ${e.title} (${e.url})`).join("\n") || "No sources"}
`;

    navigator.clipboard.writeText(reportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownloadMarkdown = () => {
    const timestamp = new Date().toLocaleString();
    const allSources = (claims || []).flatMap((c) => c.evidence || []);

    let md = `# 🔍 TruthLens AI — Verification Dossier\n\n`;
    md += `**Overall Assessment:** ${overall_assessment}\n\n`;
    md += `**Generated:** ${timestamp}\n\n`;
    md += `**Engine:** Agentic RAG • DuckDuckGo • Trafilatura • Google Gemini AI\n\n`;
    md += `## Executive Summary\n${assessment_summary}\n\n`;
    md += `> **Analysis Context:** ${getVerdictDescription(overall_assessment)}\n\n`;

    md += `## Detailed Claims Evaluated (${claims?.length || 0})\n\n`;
    (claims || []).forEach((c, idx) => {
      md += `### Claim #${idx + 1}: "${c.text}"\n`;
      md += `- **Verdict:** ${c.verdict}\n`;
      md += `- **AI Verification Analysis:** ${c.reasoning}\n`;
      if (c.evidence && c.evidence.length > 0) {
        md += `- **Evidence Citations:**\n`;
        c.evidence.forEach((e) => {
          md += `  - [${e.publisher}] **${e.title}** (${e.stance})\n`;
          md += `    URL: ${e.url}\n`;
          if (e.snippet) {
            md += `    > "${e.snippet.trim()}"\n`;
          }
        });
      }
      md += `\n`;
    });

    md += `## Sources Consulted (${allSources.length})\n\n`;
    allSources.forEach((e, idx) => {
      md += `${idx + 1}. **${e.publisher}** — [${e.title}](${e.url}) (${e.domain || "Web"})\n`;
    });

    md += `\n---\n*TruthLens AI automatically aggregates live news, fact-checking archives, and official statements with transparent attribution. UNVERIFIED indicates absence of indexed external journalism, not proven falsehood.*\n`;

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `TruthLens-Dossier-${Date.now()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportPDF = () => {
    window.print();
  };

  const totalSources = claims
    ? claims.reduce((acc, c) => acc + (c.evidence ? c.evidence.length : 0), 0)
    : 0;

  const activeOverallVerdict =
    displayLanguage === "native" && vernacular_overall_verdict
      ? vernacular_overall_verdict
      : overall_assessment;

  const activeOverallSummary =
    displayLanguage === "native" && vernacular_summary
      ? vernacular_summary
      : assessment_summary;

  return (
    <div className="v2-verification-container">
      {/* Vernacular Language Banner & Toggle Pill Bar */}
      {isVernacular && (
        <div className="vernacular-toggle-banner">
          <div className="vernacular-meta">
            <span className="vernacular-icon">
              <GlobeIcon size={18} style={{ color: "#38bdf8" }} />
            </span>
            <div className="vernacular-meta-text">
              <span className="vernacular-title">
                Multi-Lingual Claim Verified: <strong>{language_name}</strong>
              </span>
              <span className="vernacular-sub">
                Cross-referenced with regional fact-checks & global news wires
              </span>
            </div>
          </div>

          <div className="vernacular-lang-pills">
            <button
              type="button"
              className={`vernacular-lang-pill ${displayLanguage === "native" ? "active" : ""}`}
              onClick={() => setDisplayLanguage("native")}
              title={`View explanation in ${language_name}`}
              style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
            >
              <GlobeIcon size={12} /> मूल भाषा ({language_name.split(" ")[0]})
            </button>
            <button
              type="button"
              className={`vernacular-lang-pill ${displayLanguage === "en" ? "active" : ""}`}
              onClick={() => setDisplayLanguage("en")}
              title="View English translation"
            >
              English
            </button>
          </div>
        </div>
      )}

      {/* Top Banner with Verdict & Export Action Buttons */}
      <div className={`hero-verdict-card ${getVerdictClass(overall_assessment)}`}>
        <div className="hero-verdict-header">
          <div className="hero-verdict-badge-group">
            <span className="verdict-emoji">{getVerdictIcon(overall_assessment)}</span>
            <span className="hero-verdict-title">{activeOverallVerdict}</span>
            {is_developing_story && (
              <span className="developing-story-pill">
                <span className="developing-pulse-dot" /> Developing Story • Live News Active
              </span>
            )}
          </div>

          <div className="hero-verdict-actions">
            <button
              type="button"
              className="verdict-action-btn"
              onClick={handleCopyReport}
              title="Copy structured summary to clipboard"
              style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
            >
              {copied ? "✓ Copied" : <><CopyIcon size={13} /> Copy</>}
            </button>

            <button
              type="button"
              className="verdict-action-btn"
              onClick={handleDownloadMarkdown}
              title="Download structured Markdown (.md) dossier"
              style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
            >
              <DocumentIcon size={13} /> Markdown
            </button>

            <button
              type="button"
              className="verdict-action-btn verdict-action-pdf"
              onClick={handleExportPDF}
              title="Print or save official PDF dossier"
              style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
            >
              <DownloadIcon size={13} /> Export PDF
            </button>
          </div>
        </div>

        <p className="hero-verdict-summary">{activeOverallSummary}</p>

        <div className="hero-verdict-footer">
          <div className="verdict-guide-box">
            <strong>Analysis Context:</strong> {getVerdictDescription(overall_assessment)}
          </div>
          {is_developing_story && developing_story_note && (
            <div className="developing-story-box">
              <span className="developing-story-box-icon"><ZapIcon size={14} style={{ color: "#38bdf8" }} /></span>
              <span><strong>Live News Wire Update:</strong> {developing_story_note}</span>
            </div>
          )}
          {has_conflict && (
            <div className="conflict-alert-badge" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <AlertTriangleIcon size={14} style={{ color: "#f59e0b" }} /> Conflicting reports found across different publishers
            </div>
          )}
        </div>
      </div>

      {/* Stats Summary Strip */}
      <div className="stats-strip">
        <div className="stat-item">
          <span className="stat-num">{claims ? claims.length : 0}</span>
          <span className="stat-label">Claims Extracted</span>
        </div>
        <div className="stat-item">
          <span className="stat-num">{totalSources}</span>
          <span className="stat-label">Verified Sources</span>
        </div>
        <div className="stat-item">
          <span className="stat-num">
            {service_status?.gemini_api === "ok" ? (isVernacular ? `${language_name.split(" ")[0]} RAG` : "Gemini AI") : "Heuristic"}
          </span>
          <span className="stat-label">Reasoning Engine</span>
        </div>
      </div>

      {/* Interactive Evidence Knowledge Graph */}
      {claims && claims.length > 0 && (
        <EvidenceKnowledgeGraph
          claims={claims}
          overallAssessment={overall_assessment}
        />
      )}

      {/* Claims Breakdown Section */}
      <div className="claims-section">
        <h3 className="section-heading">Detailed Claim-by-Claim Verification</h3>

        {(!claims || claims.length === 0) ? (
          <div className="empty-state-box">
            No distinct factual claims were extracted. Try submitting a longer news excerpt.
          </div>
        ) : (
          claims.map((claim, index) => (
            <ClaimCard
              key={claim.claim_id || index}
              claim={claim}
              index={index}
              getVerdictClass={getVerdictClass}
              getVerdictIcon={getVerdictIcon}
              getStanceBadge={getStanceBadge}
              displayLanguage={displayLanguage}
            />
          ))
        )}
      </div>

      {/* Disclaimer */}
      <div className="disclaimer-footer-card">
        <span className="disclaimer-icon">ℹ️</span>
        <p className="disclaimer-text">
          {disclaimer ||
            "Verification is powered by real-time web news retrieval and Google Gemini AI reasoning. UNVERIFIED claims indicate an absence of indexed external reporting rather than proven falsehood."}
        </p>
      </div>
    </div>
  );
};

const ClaimCard = ({ claim, index, getVerdictClass, getVerdictIcon, getStanceBadge, displayLanguage = "en" }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const {
    text,
    verdict,
    reasoning,
    supporting_evidence_count = 0,
    contradicting_evidence_count = 0,
    neutral_evidence_count = 0,
    evidence = [],
    vernacular_info
  } = claim;

  const isNative = displayLanguage === "native" && vernacular_info;
  const activeVerdict = isNative && vernacular_info.native_verdict_label ? vernacular_info.native_verdict_label : verdict;
  const activeReasoning = isNative && vernacular_info.native_reasoning ? vernacular_info.native_reasoning : reasoning;
  const nativeFindings = isNative && vernacular_info.native_key_findings ? vernacular_info.native_key_findings : [];

  return (
    <div className={`claim-card-modern ${getVerdictClass(verdict)}`}>
      <div
        className="claim-header-modern"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex={0}
      >
        <div className="claim-headline-area">
          <div className="claim-headline-meta">
            <span className="claim-badge-num">Claim #{index + 1}</span>
            {vernacular_info?.language_name && (
              <span className="claim-lang-tag" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                <GlobeIcon size={12} /> {vernacular_info.language_name}
              </span>
            )}
          </div>
          <h4 className="claim-quote-text">"{text}"</h4>
          {vernacular_info?.translated_claim_en && (
            <p className="claim-translated-sub">
              <em>English Translation:</em> "{vernacular_info.translated_claim_en}"
            </p>
          )}
        </div>

        <div className="claim-verdict-pill-area">
          <span className={`verdict-pill-modern ${getVerdictClass(verdict)}`}>
            {getVerdictIcon(verdict)} {activeVerdict}
          </span>
          <button type="button" className="accordion-arrow" aria-label="Toggle details">
            {isExpanded ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="claim-content-modern">
          {/* AI Explanation Box */}
          <div className="ai-reasoning-card">
            <div className="reasoning-header">
              <span className="ai-icon">
                <SparklesIcon size={14} style={{ color: "#38bdf8" }} />
              </span>
              <span className="ai-label">
                AI Verification Analysis {isNative ? `(${vernacular_info.language_name})` : "(English)"}
              </span>
            </div>
            <p className="reasoning-text">{activeReasoning}</p>

            {/* Native Key Findings */}
            {nativeFindings.length > 0 && (
              <div className="native-findings-box">
                <span className="findings-title">📌 मुख्य निष्कर्ष (Key Verified Points):</span>
                <ul className="findings-list">
                  {nativeFindings.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Stance Counter */}
          {evidence.length > 0 && (
            <div className="stance-counters-bar">
              <span className="counter-pill sup">✓ {supporting_evidence_count} Supporting</span>
              <span className="counter-pill con">✗ {contradicting_evidence_count} Refuting</span>
              <span className="counter-pill neu">○ {neutral_evidence_count} Mentioning</span>
            </div>
          )}

          {/* Evidence Sources List */}
          {evidence.length > 0 ? (
            <div className="sources-container">
              <h5 className="sources-title" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <NewspaperIcon size={16} style={{ color: "#38bdf8" }} /> Citations & Verified Sources ({evidence.length})
              </h5>
              <div className="sources-grid">
                {evidence.map((item, idx) => (
                  <SourceCard key={item.id || idx} item={item} getStanceBadge={getStanceBadge} />
                ))}
              </div>
            </div>
          ) : (
            <div className="no-sources-alert">
              No direct external news articles or fact-checks were retrieved for this specific assertion.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const SourceCard = ({ item, getStanceBadge }) => {
  return (
    <div className="source-citation-card">
      <div className="source-card-header">
        <div className="publisher-badge">
          <span className="publisher-logo-icon">
            <GlobeIcon size={13} style={{ color: "#60a5fa" }} />
          </span>
          <span className="publisher-name">{item.publisher || item.domain}</span>
        </div>
        {getStanceBadge(item.stance)}
      </div>

      <h5 className="source-headline">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="source-external-link"
        >
          {item.title} <span className="external-arrow">↗</span>
        </a>
      </h5>

      {item.snippet && (
        <div className="quote-callout">
          <span className="quote-mark">“</span>
          <p className="quote-body">{item.snippet}</p>
        </div>
      )}

      <div className="source-footer">
        <span className="source-domain-tag">{item.domain}</span>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="read-article-link"
        >
          Read Source →
        </a>
      </div>
    </div>
  );
};

export default V2VerificationResult;
