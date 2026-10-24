from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class StanceType(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class EvidenceSourceType(str, Enum):
    FACT_CHECK_API = "FACT_CHECK_API"
    LIVE_NEWS_SEARCH = "LIVE_NEWS_SEARCH"
    GENERAL_REFERENCE = "GENERAL_REFERENCE"


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class OverallAssessment(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class ClaimProposition(BaseModel):
    subjects: List[str] = Field(default_factory=list)
    predicates: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    numeric_constraints: List[str] = Field(default_factory=list)
    temporal_constraints: List[str] = Field(default_factory=list)
    negated: bool = False
    modality: Optional[str] = "completed"
    raw_text: Optional[str] = None


class EvidenceItem(BaseModel):
    id: str
    claim_id: str
    source_type: EvidenceSourceType
    publisher: str
    domain: str
    url: str
    title: str
    snippet: str
    content: Optional[str] = None
    publish_date: Optional[str] = None
    credibility_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stance: StanceType
    raw_rating: Optional[str] = None
    claim_reviewed: Optional[str] = None
    semantic_relation: Optional[str] = None
    semantic_probabilities: Optional[dict] = Field(default_factory=dict)
    proposition: Optional[ClaimProposition] = None
    proposition_diagnostic: Optional[dict] = Field(default_factory=dict)


class ExtractedClaim(BaseModel):
    claim_id: str
    text: str
    verdict: ClaimVerdict = ClaimVerdict.UNVERIFIED
    support_score: float = 0.0
    contradict_score: float = 0.0
    keywords: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    explanation: str = "Insufficient external evidence available to independently verify this claim."
    proposition: Optional[ClaimProposition] = None


class LinguisticSignal(BaseModel):
    label: int
    prediction: str
    confidence: float
    message: str


class VernacularAuditInfo(BaseModel):
    detected_language: str = "en"
    language_name: str = "English"
    original_claim: str
    translated_claim_en: Optional[str] = None
    native_verdict_label: Optional[str] = None
    native_reasoning: Optional[str] = None
    english_reasoning: Optional[str] = None
    native_key_findings: List[str] = Field(default_factory=list)
    vernacular_sources_searched: List[str] = Field(default_factory=list)


class VerificationRequest(BaseModel):
    title: Optional[str] = ""
    text: Optional[str] = ""
    max_claims: Optional[int] = 5
    include_linguistic_signal: Optional[bool] = True
    language: Optional[str] = "auto"
    target_language: Optional[str] = None
    source_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_content_present(self) -> "VerificationRequest":
        title_str = (self.title or "").strip()
        text_str = (self.text or "").strip()
        if not title_str and not text_str:
            raise ValueError("At least one of 'title' or 'text' must be provided for verification.")
        if len(title_str) + len(text_str) < 10:
            raise ValueError("Input is too short. Please provide at least 10 characters of content for verification.")
        return self


class EvidenceStrength(str, Enum):
    NONE = "NONE"
    LIMITED = "LIMITED"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class UncertaintyLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ClaimEvidenceSummary(BaseModel):
    claim_id: str
    claim_text: str
    total_evidence_count: int = 0
    fact_check_count: int = 0
    live_news_count: int = 0
    general_reference_count: int = 0
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    neutral_evidence_count: int = 0
    unique_source_domains: List[str] = Field(default_factory=list)
    unique_domain_count: int = 0
    most_recent_evidence_timestamp: Optional[str] = None
    has_conflicting_evidence: bool = False
    fact_check_evidence: List[EvidenceItem] = Field(default_factory=list)
    live_news_evidence: List[EvidenceItem] = Field(default_factory=list)
    general_reference_evidence: List[EvidenceItem] = Field(default_factory=list)
    all_evidence: List[EvidenceItem] = Field(default_factory=list)
    semantic_model: Optional[str] = "cross-encoder/nli-distilroberta-base"
    semantic_evidence_count: int = 0


class ClaimVerificationDetail(BaseModel):
    claim_id: str
    text: str
    verdict: ClaimVerdict
    reasoning: str
    evidence_strength: EvidenceStrength
    uncertainty_level: UncertaintyLevel
    has_conflicting_evidence: bool
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    neutral_evidence_count: int = 0
    keywords: List[str] = Field(default_factory=list)
    evidence_summary: Optional[ClaimEvidenceSummary] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    linguistic_signal: Optional[LinguisticSignal] = None
    semantic_relation: Optional[str] = None
    semantic_model: Optional[str] = "cross-encoder/nli-distilroberta-base"
    semantic_evidence_count: int = 0
    vernacular_info: Optional[VernacularAuditInfo] = None


class VerificationResponse(BaseModel):
    overall_assessment: OverallAssessment
    assessment_summary: str
    has_conflict: bool
    claims: List[ClaimVerificationDetail]
    linguistic_signal: Optional[LinguisticSignal] = None
    service_status: dict = Field(default_factory=dict)
    disclaimer: str = (
        "Verification is based on aggregated live news and fact-check sources. "
        "UNVERIFIED claims do not imply falsity, but rather an absence of conclusive external reporting."
    )
    detected_language: Optional[str] = "en"
    language_name: Optional[str] = "English"
    vernacular_summary: Optional[str] = None
    vernacular_overall_verdict: Optional[str] = None
    available_translations: List[str] = Field(default_factory=lambda: ["en"])
    is_developing_story: bool = False
    developing_story_note: Optional[str] = None


class ClaimVerificationResult(BaseModel):
    claim_id: str
    verdict: ClaimVerdict
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    neutral_evidence_count: int = 0
    has_conflicting_evidence: bool = False
    reasoning: str
    evidence_strength: EvidenceStrength = EvidenceStrength.NONE
    uncertainty_level: UncertaintyLevel = UncertaintyLevel.HIGH
    linguistic_signal: Optional[LinguisticSignal] = None
    semantic_relation: Optional[str] = None
    semantic_model: Optional[str] = "cross-encoder/nli-distilroberta-base"
    semantic_evidence_count: int = 0


class URLExtractRequest(BaseModel):
    url: str


class URLExtractResponse(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    domain: str = ""
    author: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class DocumentAuditRequest(BaseModel):
    title: Optional[str] = None
    content: str
    filename: Optional[str] = None


class DocumentClaimAudit(BaseModel):
    claim_id: str
    text: str
    verdict: str
    confidence: float = 0.9
    reasoning: str
    sources_count: int = 0
    top_sources: List[str] = Field(default_factory=list)
    source_links: List[dict] = Field(default_factory=list)


class DocumentAuditResponse(BaseModel):
    filename: Optional[str] = None
    document_title: str
    word_count: int
    authenticity_score: float
    overall_status: str
    executive_assessment: str
    total_claims_detected: int
    claims_breakdown: dict = Field(default_factory=dict)
    audited_claims: List[DocumentClaimAudit] = Field(default_factory=list)
    timestamp: Optional[str] = None


class DomainTrustProfile(BaseModel):
    domain: str
    name: str
    category: str
    credibility_score: float
    tier: str
    stance_bias: str
    fact_check_certified: bool
    description: str


class AnalyticsResponse(BaseModel):
    engine_metrics: dict
    stance_distribution: dict
    credibility_tiers: List[dict]
    domain_catalog: List[DomainTrustProfile]
    total_tracked_domains: int


class RadarItem(BaseModel):
    id: str
    title: str
    summary: str
    category: str
    velocity: str
    disputed_flag: bool
    source_preview: str
    published_time: str
    prefilled_query: str
    pub_date_iso: Optional[str] = None
    link: Optional[str] = None


class RadarResponse(BaseModel):
    last_updated: str
    total_active_stories: int
    categories: List[str]
    country: Optional[str] = "IN"
    items: List[RadarItem]


class ImageAuditResponse(BaseModel):
    filename: Optional[str] = None
    media_type: str = "Unknown"
    dimensions: str = "0 x 0"
    file_size_kb: float = 0.0
    visual_manipulation_risk: str = "LOW"
    visual_observations: List[str] = Field(default_factory=list)
    extracted_headline: str = ""
    extracted_text: str = ""
    core_claim: str = ""
    overall_verdict: str = "UNVERIFIED"
    confidence_score: float = 0.8
    authenticity_summary: str = ""
    evidence_sources: List[EvidenceItem] = Field(default_factory=list)
    claims_breakdown: List[DocumentClaimAudit] = Field(default_factory=list)
    timestamp: Optional[str] = None


class AudioAuditResponse(BaseModel):
    filename: Optional[str] = None
    audio_format: str = "Unknown"
    file_size_kb: float = 0.0
    duration_estimate_sec: Optional[float] = None
    detected_language: str = "Unknown"
    acoustic_context: str = "Speech / Audio"
    synthetic_voice_risk: str = "LOW"
    acoustic_observations: List[str] = Field(default_factory=list)
    transcription: str = ""
    extracted_headline: str = ""
    core_claim: str = ""
    overall_verdict: str = "UNVERIFIED"
    confidence_score: float = 0.8
    authenticity_summary: str = ""
    evidence_sources: List[EvidenceItem] = Field(default_factory=list)
    claims_breakdown: List[DocumentClaimAudit] = Field(default_factory=list)
    timestamp: Optional[str] = None


class BotVerificationRequest(BaseModel):
    message_text: str
    platform: Optional[str] = "whatsapp"
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    is_forwarded: bool = False
    forward_count: Optional[int] = None


class BotVerificationResponse(BaseModel):
    platform: str = "whatsapp"
    raw_claim: str
    sanitized_claim: str
    verdict: str = "UNVERIFIED"
    credibility_score: float = 50.0
    status_emoji: str = "⚪"
    headline: str = ""
    explanation: str = ""
    formatted_chat_reply: str = ""
    top_sources: List[str] = Field(default_factory=list)
    source_links: List[dict] = Field(default_factory=list)
    shareable_url: str = ""
    timestamp: str = ""


class BotPresetScenario(BaseModel):
    id: str
    platform: str
    title: str
    sender_label: str
    viral_text: str
    category: str
    is_forwarded: bool = True
    simulated_verdict: str = "CONTRADICTED"









