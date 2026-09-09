"""Enum values persisted as short strings (portable, human-readable in DB)."""

from __future__ import annotations

from enum import Enum


class JobType(str, Enum):
    DISCOVERY = "DISCOVERY"
    RESEARCH = "RESEARCH"
    EVALUATION = "EVALUATION"
    OUTREACH_GENERATION = "OUTREACH_GENERATION"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Valid job state transitions (state machine guard).
JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.FAILED},
    JobStatus.RUNNING: {
        JobStatus.COMPLETED,
        JobStatus.COMPLETED_WITH_WARNINGS,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.QUEUED,  # requeue after stale-lease recovery
    },
    JobStatus.FAILED: {JobStatus.QUEUED},  # explicit retry
    JobStatus.COMPLETED: set(),
    JobStatus.COMPLETED_WITH_WARNINGS: set(),
    JobStatus.CANCELLED: set(),
}


class ProspectStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    RESEARCHING = "RESEARCHING"
    RESEARCHED = "RESEARCHED"
    EVALUATING = "EVALUATING"
    EVALUATED = "EVALUATED"
    OUTREACH_DRAFTED = "OUTREACH_DRAFTED"
    OUTREACH_APPROVED = "OUTREACH_APPROVED"
    CONTACTED = "CONTACTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class QualityStatus(str, Enum):
    OK = "OK"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class DataOrigin(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"


class RecordKind(str, Enum):
    REAL = "REAL"
    MOCK = "MOCK"
    TEST = "TEST"


class WebsiteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REDIRECTED = "REDIRECTED"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    FORBIDDEN = "FORBIDDEN"
    SERVER_ERROR = "SERVER_ERROR"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ProviderName(str, Enum):
    GOOGLE_PLACES = "google_places"
    DUCKDUCKGO = "duckduckgo"
    BRAVE = "brave"
    TAVILY = "tavily"
    DIRECT_HTTP = "direct_http"
    PLAYWRIGHT = "playwright"


class ResearchRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class EvidenceType(str, Enum):
    WEBSITE_STRUCTURE = "WEBSITE_STRUCTURE"
    WEBSITE_CONTENT = "WEBSITE_CONTENT"
    WEBSITE_STATUS = "WEBSITE_STATUS"
    CONTACT_CHANNEL = "CONTACT_CHANNEL"
    SOCIAL_PRESENCE = "SOCIAL_PRESENCE"
    BUSINESS_SIGNAL = "BUSINESS_SIGNAL"
    SEARCH_RESULT = "SEARCH_RESULT"
    TECHNOLOGY_SIGNAL = "TECHNOLOGY_SIGNAL"


class PainCategory(str, Enum):
    WEBSITE = "WEBSITE"
    AUTOMATION = "AUTOMATION"
    AI = "AI"
    BUSINESS_PROCESS = "BUSINESS_PROCESS"
    ONLINE_PRESENCE = "ONLINE_PRESENCE"
    CUSTOM_SOFTWARE = "CUSTOM_SOFTWARE"


class Confidence(str, Enum):
    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    POSSIBLE = "POSSIBLE"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


class CommercialPotential(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class OutreachChannel(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"


class OutreachStatus(str, Enum):
    DRAFTED = "DRAFTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT = "SENT"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    BLOCKED_DUPLICATE = "BLOCKED_DUPLICATE"


class OutreachEventType(str, Enum):
    DRAFTED = "drafted"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    FOLLOW_UP_DUE = "follow_up_due"
    FOLLOW_UP_SENT = "follow_up_sent"
    CLOSED = "closed"
