import re
from datetime import datetime
from typing import List, Set, Optional
from app.schemas.remediation import ValidationResult, UnsupportedClaim
from app.schemas.candidate import CandidateEvidence

METRIC_NUMBER_PATTERN = re.compile(
    r"(\d+(\.\d+)?%|\$\d+(\.\d+)?|\b\d+\+?(\s*(years?|months?|users?|clients?|engineers?|developers?|members?|requests?|transactions?|services?|nodes?|clusters?|rps|qps|ms|s|gb|tb|pb|m|k|b))\b|\b(99\.\d+%)\b)",
    re.IGNORECASE,
)

LEADERSHIP_PATTERNS = re.compile(
    r"\b(led|lead|leading|managed|managing|mentored|mentoring|directed|directing|spearheaded|oversaw|headed|founded)\b",
    re.IGNORECASE,
)

TEAM_SIZE_PATTERN = re.compile(
    r"\b(team of \d+|\d+\s*(engineers?|developers?|direct reports?|team members?))\b",
    re.IGNORECASE,
)

SCALE_TERMS = {
    "enterprise",
    "multi-region",
    "global",
    "mission-critical",
    "high-availability",
    "petabyte",
    "terabyte",
}

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
    "using", "utilizing", "utilize", "utilized", "utilizes", "use", "uses", "used",
    "via", "across", "within", "per", "core", "based",
}

BUILDER_VERBS = {
    "built", "build", "building", "builds",
    "developed", "develop", "developing", "develops",
    "implemented", "implement", "implementing", "implements",
    "created", "create", "creating", "creates",
    "engineered", "engineer", "engineering", "engineers",
    "constructed", "construct", "constructing", "constructs",
    "authored", "author", "authoring", "authors",
    "wrote", "write", "writing", "writes",
}

DESIGN_ARCHITECT_VERBS = {
    "designed", "design", "designing", "designs",
    "architected", "architect", "architecting", "architects",
}

LEADERSHIP_VERBS = {
    "led", "lead", "leading", "leads",
    "spearheaded", "spearhead", "spearheading", "spearheads",
    "owned", "own", "owning", "owns",
    "managed", "manage", "managing", "manages",
    "directed", "direct", "directing", "directs",
    "oversaw", "oversee", "overseeing", "oversees",
    "headed", "head", "heading", "heads",
    "founded", "found", "founding", "founds",
    "mentored", "mentor", "mentoring", "mentors",
}

COMMON_TECHNICAL_MODIFIERS = {
    "high-performance", "daily", "weekly", "monthly", "query", "queries",
    "data", "processing", "process", "handling", "handle", "serving", "serve",
    "delivering", "deliver", "lower", "higher", "reducing", "reduced", "reduction",
    "increasing", "increased",
}

OUTCOME_PATTERNS = [
    (re.compile(r"\b(enabling|to enable)\b", re.IGNORECASE), "enabling/to enable"),
    (re.compile(r"\b(to provide|providing)\b", re.IGNORECASE), "to provide/providing"),
    (re.compile(r"\b(resulting in|results in|resulted in)\b", re.IGNORECASE), "resulting in"),
    (re.compile(r"\b(driving|to drive|drove)\b", re.IGNORECASE), "driving/to drive"),
    (re.compile(r"\b(improving|to improve|improved)\b", re.IGNORECASE), "improving/to improve"),
    (re.compile(r"\b(achieving|to achieve|achieved)\b", re.IGNORECASE), "achieving/to achieve"),
    (re.compile(r"\b(to ensure|ensuring|ensured)\b", re.IGNORECASE), "to ensure/ensuring"),
    (re.compile(r"\b(to facilitate|facilitating|facilitated)\b", re.IGNORECASE), "to facilitate"),
    (re.compile(r"\b(to support|supporting)\b", re.IGNORECASE), "to support"),
    (re.compile(r"\b(to accelerate|accelerating|accelerated)\b", re.IGNORECASE), "to accelerate"),
]

UNSUPPORTED_BUZZWORDS = [
    re.compile(r"\b(drive business growth|driving business growth|drives business growth)\b", re.IGNORECASE),
    re.compile(r"\b(proven track record|proven expertise)\b", re.IGNORECASE),
    re.compile(r"\b(industry-leading|world-class|visionary)\b", re.IGNORECASE),
]


def _stem(word: str) -> str:
    """Lightweight suffix stripping stemmer for robust content token comparison."""
    w = word.lower().strip()
    w = re.sub(r"[^\w]", "", w)
    for suffix in ("ing", "tion", "ment", "ed", "es", "s", "ly", "al", "ive", "able", "ible"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def _extract_tokens(text: str) -> List[str]:
    """Extracts alphanumeric words from text."""
    if not text:
        return []
    return re.findall(r"\b[a-zA-Z0-9_\-\+#\.]+\b", text)


def extract_numbers_and_metrics(text: str) -> Set[str]:
    """Extracts normalized metrics, percentages, and numerical quantities from text."""
    if not text:
        return set()
    results = set()
    for m in METRIC_NUMBER_PATTERN.findall(text):
        val = m[0] if isinstance(m, tuple) else m
        if val and val.strip():
            norm_val = re.sub(r"\s+", " ", val.strip().lower())
            results.add(norm_val)
    # Extract discrete number, percentage, and currency tokens with word boundaries
    raw_num_tokens = re.findall(r"(?:\$\s*)?\b\d+(?:,\d+)*(?:\.\d+)?%?(?:\s*[mbkMBK])?\b", text)
    for num in raw_num_tokens:
        clean_num = num.strip().lower()
        results.add(clean_num)
        results.add(clean_num.replace(",", ""))
        if clean_num.endswith("%"):
            results.add(clean_num[:-1])
    return results


def extract_leadership_claims(text: str) -> bool:
    """Checks if text claims leadership, management, or mentorship."""
    if not text:
        return False
    return bool(LEADERSHIP_PATTERNS.search(text))


def extract_team_size_claims(text: str) -> Set[str]:
    """Extracts team size or direct report numbers."""
    if not text:
        return set()
    matches = TEAM_SIZE_PATTERN.findall(text)
    results = set()
    for m in matches:
        val = m[0] if isinstance(m, tuple) else m
        if val and val.strip():
            results.add(val.strip().lower())
    return results


def validate_claims_against_source(
    proposed_bullet: str,
    source_evidence: str,
    candidate_evidence_corpus: Optional[str] = None,
    item_context_tokens: Optional[Set[str]] = None,
    candidate_skills: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Deterministically compares proposed rewritten bullet against source evidence.
    Enforces strict grounding:
    1. Rejects ungrounded metrics using whole-number token matching (e.g. 5% rejected if source has 45%).
    2. Rejects scope-inflating verbs (Designed, Architected, Led, Spearheaded, Owned, Managed).
    3. Rejects purpose/outcome clauses (enabling ..., to enable ..., to provide ..., resulting in ..., etc.).
    4. Rejects new content words not present in source bullet, item context (title/tech list), or candidate skills list.
    """
    if not proposed_bullet or not proposed_bullet.strip():
        return ValidationResult(is_valid=True, status="Validated", sanitized_bullet="")

    unsupported: List[UnsupportedClaim] = []
    source_clean = source_evidence or ""
    source_lower = source_clean.lower()
    proposed_lower = proposed_bullet.lower()

    # 1. Whole-number Metric / Number Validation
    source_metrics = extract_numbers_and_metrics(source_clean)
    proposed_metrics = extract_numbers_and_metrics(proposed_bullet)

    for metric in proposed_metrics:
        # Check if the exact whole metric token or pattern exists in verified source metrics
        if metric not in source_metrics:
            unsupported.append(
                UnsupportedClaim(
                    category="Metric",
                    claim_text=metric,
                    reason=f"The metric '{metric}' does not appear in verified evidence.",
                    prompt_for_user="What was the actual measurable impact or scale for this achievement?",
                )
            )

    # 2. Scope-Inflating Verb Check (Rule 2)
    # Architecture / Design
    proposed_tokens_lower = [t.lower() for t in _extract_tokens(proposed_bullet)]
    proposed_has_design = any(t in DESIGN_ARCHITECT_VERBS for t in proposed_tokens_lower)
    source_has_design = any(t in DESIGN_ARCHITECT_VERBS for t in [t.lower() for t in _extract_tokens(source_clean)])
    if proposed_has_design and not source_has_design:
        unsupported.append(
            UnsupportedClaim(
                category="SeniorityRole",
                claim_text="Scope-Inflating Architecture/Design Verb",
                reason="Introduced scope-inflating design/architecture verb not present in source bullet.",
                prompt_for_user="Did your role explicitly include architecture and system design responsibility?",
            )
        )

    # Leadership / Ownership
    proposed_has_leadership = any(t in LEADERSHIP_VERBS for t in proposed_tokens_lower) or extract_leadership_claims(proposed_bullet)
    source_has_leadership = any(t in LEADERSHIP_VERBS for t in [t.lower() for t in _extract_tokens(source_clean)]) or extract_leadership_claims(source_clean)
    if proposed_has_leadership and not source_has_leadership:
        unsupported.append(
            UnsupportedClaim(
                category="SeniorityRole",
                claim_text="Scope-Inflating Leadership/Management Verb",
                reason="Introduced leadership responsibility (e.g. leading/managing/spearheading) not present in original evidence.",
                prompt_for_user="Did you lead or manage other engineers on this project?",
            )
        )

    # 3. Team Size Validation
    source_team_sizes = extract_team_size_claims(source_clean)
    proposed_team_sizes = extract_team_size_claims(proposed_bullet)
    for team_claim in proposed_team_sizes:
        if team_claim not in source_clean and not source_team_sizes:
            unsupported.append(
                UnsupportedClaim(
                    category="TeamOrganization",
                    claim_text=team_claim,
                    reason=f"Introduced team size '{team_claim}' not verified in candidate evidence.",
                    prompt_for_user="How many engineers or contributors were on your team for this project?",
                )
            )

    # 4. Scale & Environment Validation
    for scale_term in SCALE_TERMS:
        if scale_term in proposed_lower and scale_term not in source_lower:
            # Check item context and skills for scale term
            item_has_scale = bool(item_context_tokens and scale_term in item_context_tokens)
            if not item_has_scale:
                unsupported.append(
                    UnsupportedClaim(
                        category="Scale",
                        claim_text=scale_term,
                        reason=f"Introduced enterprise scale/infrastructure claim '{scale_term}' not verified in candidate evidence.",
                        prompt_for_user=f"Did your work operate in a {scale_term} environment?",
                    )
                )

    # 5. Purpose / Outcome Clauses Check (Rule 3)
    for pattern, label in OUTCOME_PATTERNS:
        if pattern.search(proposed_bullet) and not pattern.search(source_clean):
            unsupported.append(
                UnsupportedClaim(
                    category="Scale",
                    claim_text=label,
                    reason=f"Introduced purpose/outcome clause ('{label}') not present in original bullet.",
                    prompt_for_user="Did the original achievement explicitly state this outcome?",
                )
            )

    # 6. Content Words Grounding Check (Rule 1 & Item-Scoped Evidence)
    source_has_builder_or_design = (
        any(t in BUILDER_VERBS for t in [t.lower() for t in _extract_tokens(source_clean)])
        or any(t in DESIGN_ARCHITECT_VERBS for t in [t.lower() for t in _extract_tokens(source_clean)])
    )

    # Build allowed token and stem sets from:
    # a) source bullet tokens
    # b) item context tokens (title/role, item technologies)
    # c) candidate skills list
    # d) candidate_evidence_corpus fallback (if provided for backwards compatibility in older tests)
    allowed_tokens: Set[str] = set()
    for t in _extract_tokens(source_clean):
        allowed_tokens.add(t.lower())

    if item_context_tokens:
        for t in item_context_tokens:
            for subt in _extract_tokens(t):
                allowed_tokens.add(subt.lower())

    if candidate_skills:
        for s in candidate_skills:
            for subt in _extract_tokens(s):
                allowed_tokens.add(subt.lower())

    if candidate_evidence_corpus and not item_context_tokens and not candidate_skills:
        for t in _extract_tokens(candidate_evidence_corpus):
            allowed_tokens.add(t.lower())

    allowed_stems = {_stem(t) for t in allowed_tokens if t}

    for token in _extract_tokens(proposed_bullet):
        t_clean = token.strip(".,;:\"'()[]{}").lower()
        if not t_clean or t_clean in STOPWORDS:
            continue
        # Allow numbers and metric components matching verified source metrics
        if re.match(r"^\d+(?:,\d+)*(?:\.\d+)?%?$", t_clean) or t_clean in ("$", "%"):
            continue
        # Allow same-scope builder verbs if source had a builder/architect verb
        if t_clean in BUILDER_VERBS and source_has_builder_or_design:
            continue
        if t_clean in COMMON_TECHNICAL_MODIFIERS:
            continue
        # Check whole token and stem equality against allowed set (no substring matching!)
        t_stem = _stem(t_clean)
        if t_clean not in allowed_tokens and t_stem not in allowed_stems:
            unsupported.append(
                UnsupportedClaim(
                    category="Technology",
                    claim_text=token,
                    reason=f"Introduced new content word '{token}' not present in source evidence.",
                    prompt_for_user=f"Where does the fact '{token}' come from?",
                )
            )

    is_valid = len(unsupported) == 0
    status = "Validated" if is_valid else "RequiresCandidateInput"
    sanitized_bullet = proposed_bullet.strip()

    return ValidationResult(
        is_valid=is_valid,
        status=status,
        unsupported_claims=unsupported,
        sanitized_bullet=sanitized_bullet,
    )


def compute_candidate_experience_years(candidate_evidence: CandidateEvidence) -> float:
    """Computes total professional experience years from experience items."""
    total_months = 0
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    for exp in candidate_evidence.experience:
        start_str = exp.start_date or getattr(exp, "startDate", "")
        end_str = exp.end_date or getattr(exp, "endDate", "")
        if not start_str:
            continue
        try:
            start_parts = start_str.strip().split("-")
            s_year = int(start_parts[0])
            s_month = int(start_parts[1]) if len(start_parts) > 1 else 1

            if not end_str or end_str.lower() in ("present", "current", "now"):
                e_year = current_year
                e_month = current_month
            else:
                end_parts = end_str.strip().split("-")
                e_year = int(end_parts[0])
                e_month = int(end_parts[1]) if len(end_parts) > 1 else 12

            months = (e_year - s_year) * 12 + (e_month - s_month)
            if months > 0:
                total_months += months
        except Exception:
            continue

    return round(total_months / 12.0, 1) if total_months > 0 else 0.0


def validate_summary_grounding(
    summary: str,
    candidate_evidence: CandidateEvidence,
) -> ValidationResult:
    """
    Validates candidate summary against evidence:
    1. Rejects unsupported buzzwords ('drive business growth', 'proven expertise', etc.).
    2. Rejects ungrounded years of experience claims.
    3. Rejects hallucinated technologies not present in candidate skills or evidence.
    """
    if not summary or not summary.strip():
        return ValidationResult(is_valid=True, status="Validated", sanitized_bullet="")

    unsupported: List[UnsupportedClaim] = []
    summary_lower = summary.lower()

    # 1. Buzzwords / Business claims check
    orig_summary_lower = (candidate_evidence.summary + " " + (candidate_evidence.headline or "")).lower()
    for bw_pattern in UNSUPPORTED_BUZZWORDS:
        m = bw_pattern.search(summary)
        if m and not bw_pattern.search(orig_summary_lower):
            unsupported.append(
                UnsupportedClaim(
                    category="SeniorityRole",
                    claim_text=m.group(0),
                    reason=f"Introduced unsupported marketing/business claim '{m.group(0)}'.",
                    prompt_for_user="Please verify this claim against your background.",
                )
            )

    # 2. Years of experience check
    computed_years = compute_candidate_experience_years(candidate_evidence)
    year_match = re.search(r"\b(\d+)\+?\s*years?\b", summary, re.IGNORECASE)
    if year_match:
        claimed_years = int(year_match.group(1))
        # If claimed years > computed years + 1.5 (allowing small rounding), reject
        if computed_years > 0 and claimed_years > (computed_years + 1.5):
            unsupported.append(
                UnsupportedClaim(
                    category="Duration",
                    claim_text=f"{claimed_years} years",
                    reason=f"Claimed {claimed_years} years of experience, but computed experience from dates is {computed_years:.1f} years.",
                    prompt_for_user="How many total years of relevant experience do you have?",
                )
            )

    # 3. Technologies check (exact word boundaries to prevent 'scalable' -> 'scala' false positive)
    all_known_tech = set()
    for s in candidate_evidence.skills:
        all_known_tech.add(s.name.lower())
    for e in candidate_evidence.experience:
        for tech in (e.technologies or []):
            all_known_tech.add(tech.lower())
    for p in candidate_evidence.projects:
        for tech in (getattr(p, "tech_stack", None) or getattr(p, "technologies", [])):
            all_known_tech.add(tech.lower())
    for c in candidate_evidence.certifications:
        all_known_tech.add(c.title.lower())
        if c.issuer:
            all_known_tech.add(c.issuer.lower())

    full_evidence_tokens = set()
    corpus_parts = [
        candidate_evidence.headline or "",
        candidate_evidence.summary or "",
        " ".join(f"{e.company} {e.role} {' '.join(e.bullets)}" for e in candidate_evidence.experience),
        " ".join(f"{p.title} {p.description} {' '.join(getattr(p, 'highlights', None) if getattr(p, 'highlights', None) else getattr(p, 'bullets', []))}" for p in candidate_evidence.projects),
        " ".join(f"{ed.degree} {ed.institution} {ed.field_of_study}" for ed in candidate_evidence.education),
        " ".join(f"{c.title} {c.issuer}" for c in candidate_evidence.certifications),
        " ".join(f"{a.title} {a.issuer} {a.description}" for a in getattr(candidate_evidence, "achievements", [])),
    ]
    for t in _extract_tokens(" ".join(corpus_parts)):
        full_evidence_tokens.add(t.lower())

    # Check for known tech terms mentioned in summary using exact word boundary
    for tech_candidate in ("kubernetes", "aws", "gcp", "azure", "docker", "graphql", "rust", "c++", "java", "scala", "ruby"):
        # Match whole word only
        if re.search(r"\b" + re.escape(tech_candidate) + r"\b", summary_lower):
            if tech_candidate not in all_known_tech and tech_candidate not in full_evidence_tokens:
                unsupported.append(
                    UnsupportedClaim(
                        category="Technology",
                        claim_text=tech_candidate,
                        reason=f"Introduced technology '{tech_candidate}' not present in candidate skills or evidence.",
                        prompt_for_user=f"Do you have verified experience with {tech_candidate}?",
                    )
                )

    is_valid = len(unsupported) == 0
    status = "Validated" if is_valid else "RequiresCandidateInput"
    sanitized_summary = summary.strip()

    return ValidationResult(
        is_valid=is_valid,
        status=status,
        unsupported_claims=unsupported,
        sanitized_bullet=sanitized_summary,
    )
