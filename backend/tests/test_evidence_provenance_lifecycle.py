"""
Evidence Lifecycle & Provenance Linkage Tests for ResumeIQ

Verifies:
1. Document ingestion hydration attaches sourceDocumentId and sourceDocumentName.
2. Evidence normalization preserves document provenance.
3. Skill, Education, and Certification entities retain stable IDs (ev_{id}) unaffected by reordering.
4. Legacy items without document provenance normalize gracefully with None.
5. Provenance lookup service and API endpoint resolve full lineage.
6. Multi-tenant isolation is strictly enforced for provenance resolution.
7. Graceful fallback when an ingestion draft is deleted or missing.
8. Historical TargetedResumeVariant snapshots maintain immutability and backwards compatibility.
9. Claim validation and grounding verification operate accurately with provenance-enhanced evidence.
10. Hybrid retrieval and evidence ranking remain robust and fully functional.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.core.auth import AuthenticatedUser, get_authenticated_user
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.evidence import EvidenceItem, EvidenceProvenanceDetail
from app.schemas.ingestion import ParsedCandidateProfile, IngestionDraft
from app.schemas.variant import TargetedResumeVariant
from app.schemas.profile import ProfileDTO
from app.services.evidence_service import EvidenceService
from app.services.ingestion_service import IngestionService
from app.services.resume_service import ResumeService
from app.ai.retrieval.hybrid_matcher import HybridMatcher
from app.ai.claim_validator import validate_claims_against_source


@pytest.fixture
def mock_user():
    return AuthenticatedUser(
        uid="user_test_provenance_123",
        token="mock_valid_token",
        email="candidate@example.com",
    )


@pytest.fixture
def mock_other_user():
    return AuthenticatedUser(
        uid="user_test_other_999",
        token="mock_other_token",
        email="other@example.com",
    )


# 1. Test Document Ingestion Sets Provenance
@pytest.mark.asyncio
async def test_document_ingestion_sets_provenance(mock_user):
    draft_data = IngestionDraft(
        ingestionId="ingest_doc_001",
        documentName="senior_engineer_resume.pdf",
        documentType="Resume",
        fileSizeBytes=24500,
        status="Parsed",
        rawTextSnippet="Senior Software Engineer with 8 years...",
        rawTextCharCount=1200,
        fileUrl="https://storage.example.com/resumes/senior_engineer_resume.pdf",
        createdAt="2026-09-24T10:00:00Z",
        updatedAt="2026-09-24T10:00:00Z",
    )

    reviewed = ParsedCandidateProfile(
        profile=ProfileDTO(fullName="Jane Doe", headline="Staff Engineer"),
        evidence=CandidateEvidence(
            experience=[
                ExperienceItem(
                    company="Stripe",
                    role="Staff Software Engineer",
                    bullets=["Architected payments pipeline scaling to 50k tps."],
                    technologies=["Python", "Go"],
                )
            ],
            skills=[
                SkillItem(name="Distributed Systems", category="Technical", proficiency="Expert")
            ],
            education=[
                EducationItem(degree="B.S. Computer Science", institution="Stanford University")
            ],
            certifications=[
                CertificationItem(title="AWS Solutions Architect", issuer="Amazon Web Services")
            ],
            projects=[
                ProjectItem(title="Payment Gateway", description="Ultra-low latency ledger", tech_stack=["Go"])
            ],
        ),
    )

    saved_docs = []

    async def mock_patch(url, headers, json, timeout=25.0):
        saved_docs.append({"url": url, "payload": json})
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {}
        return m

    async def mock_get(url, headers):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"documents": []}
        return m

    with patch.object(IngestionService, "get_ingestion_draft", return_value=draft_data), \
         patch("app.services.ingestion_service.get_http_client") as mock_http, \
         patch("app.services.profile_service.ProfileService.save_profile", new_callable=AsyncMock):
        
        client_mock = MagicMock()
        client_mock.patch = AsyncMock(side_effect=mock_patch)
        client_mock.get = AsyncMock(side_effect=mock_get)
        mock_http.return_value = client_mock

        res = await IngestionService.confirm_and_hydrate_ingestion(
            user=mock_user,
            ingestion_id="ingest_doc_001",
            reviewed_data=reviewed,
        )

        assert res.success is True
        assert res.status == "Completed"
        assert res.hydrated_summary["experience"] == 1
        assert res.hydrated_summary["skills"] == 1
        assert res.hydrated_summary["education"] == 1
        assert res.hydrated_summary["certifications"] == 1
        assert res.hydrated_summary["projects"] == 1

        # Check saved entity payloads contain document provenance
        exp_save = next(s for s in saved_docs if "/experience/" in s["url"])
        assert exp_save["payload"]["fields"]["sourceDocumentId"]["stringValue"] == "ingest_doc_001"
        assert exp_save["payload"]["fields"]["sourceDocumentName"]["stringValue"] == "senior_engineer_resume.pdf"

        skill_save = next(s for s in saved_docs if "/skills/" in s["url"])
        assert skill_save["payload"]["fields"]["sourceDocumentId"]["stringValue"] == "ingest_doc_001"
        assert skill_save["payload"]["fields"]["sourceDocumentName"]["stringValue"] == "senior_engineer_resume.pdf"


# 2. Test Evidence Normalization Preserves Provenance
def test_evidence_normalization_preserves_provenance(mock_user):
    evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_stripe_01",
                company="Stripe",
                role="Senior Engineer",
                bullets=["Built high throughput API handling $10M+ daily volume."],
                technologies=["Python", "FastAPI"],
                source_document_id="ingest_doc_001",
                source_document_name="resume_2026.pdf",
            )
        ],
        skills=[
            SkillItem(
                id="skill_python_01",
                name="Python",
                category="Language",
                proficiency="Expert",
                source_document_id="ingest_doc_001",
                source_document_name="resume_2026.pdf",
            )
        ],
        education=[
            EducationItem(
                id="edu_mit_01",
                degree="M.S. in CS",
                institution="MIT",
                field_of_study="Computer Science",
                source_document_id="ingest_doc_001",
                source_document_name="resume_2026.pdf",
            )
        ],
    )

    items = EvidenceService.normalize_candidate_evidence(mock_user.uid, evidence)
    assert len(items) == 3

    exp_item = next(i for i in items if i.source_type == "experience")
    assert exp_item.evidence_id == "ev_exp_stripe_01"
    assert exp_item.source_document_id == "ingest_doc_001"
    assert exp_item.source_document_name == "resume_2026.pdf"

    skill_item = next(i for i in items if i.source_type == "skills")
    assert skill_item.evidence_id == "ev_skill_python_01"
    assert skill_item.source_document_id == "ingest_doc_001"
    assert skill_item.source_document_name == "resume_2026.pdf"

    edu_item = next(i for i in items if i.source_type == "education")
    assert edu_item.evidence_id == "ev_edu_mit_01"
    assert edu_item.source_document_id == "ingest_doc_001"
    assert edu_item.source_document_name == "resume_2026.pdf"


# 3. Test Skills, Education, Certifications Stable IDs (Index-Shift Invariant)
def test_skills_education_certifications_stable_ids(mock_user):
    # Initial order
    evidence_order_a = CandidateEvidence(
        skills=[
            SkillItem(id="skill_react_99", name="React", category="Frontend"),
            SkillItem(id="skill_k8s_88", name="Kubernetes", category="Cloud"),
        ],
        education=[
            EducationItem(id="edu_harvard_77", degree="B.A.", institution="Harvard"),
            EducationItem(id="edu_stanford_66", degree="M.S.", institution="Stanford"),
        ],
        certifications=[
            CertificationItem(id="cert_ckad_55", title="CKAD", issuer="Linux Foundation"),
            CertificationItem(id="cert_cisa_44", title="CISA", issuer="ISACA"),
        ]
    )

    # Reordered
    evidence_order_b = CandidateEvidence(
        skills=[
            SkillItem(id="skill_k8s_88", name="Kubernetes", category="Cloud"),
            SkillItem(id="skill_react_99", name="React", category="Frontend"),
        ],
        education=[
            EducationItem(id="edu_stanford_66", degree="M.S.", institution="Stanford"),
            EducationItem(id="edu_harvard_77", degree="B.A.", institution="Harvard"),
        ],
        certifications=[
            CertificationItem(id="cert_cisa_44", title="CISA", issuer="ISACA"),
            CertificationItem(id="cert_ckad_55", title="CKAD", issuer="Linux Foundation"),
        ]
    )

    items_a = {i.evidence_id: i for i in EvidenceService.normalize_candidate_evidence(mock_user.uid, evidence_order_a)}
    items_b = {i.evidence_id: i for i in EvidenceService.normalize_candidate_evidence(mock_user.uid, evidence_order_b)}

    assert "ev_skill_react_99" in items_a and "ev_skill_react_99" in items_b
    assert "ev_skill_k8s_88" in items_a and "ev_skill_k8s_88" in items_b
    assert "ev_edu_harvard_77" in items_a and "ev_edu_harvard_77" in items_b
    assert "ev_edu_stanford_66" in items_a and "ev_edu_stanford_66" in items_b
    assert "ev_cert_ckad_55" in items_a and "ev_cert_ckad_55" in items_b
    assert "ev_cert_cisa_44" in items_a and "ev_cert_cisa_44" in items_b

    # Verify ID does not change based on index position
    assert items_a["ev_skill_react_99"].source_item_id == items_b["ev_skill_react_99"].source_item_id == "skill_react_99"


# 4. Test Legacy Items Without Provenance Fallback
def test_legacy_items_without_provenance_fallback(mock_user):
    legacy_evidence = CandidateEvidence(
        skills=[SkillItem(name="Go")],
        education=[EducationItem(degree="B.S.", institution="MIT")],
        certifications=[CertificationItem(title="AWS Practitioner", issuer="AWS")],
    )

    items = EvidenceService.normalize_candidate_evidence(mock_user.uid, legacy_evidence)
    assert len(items) == 3

    for it in items:
        assert it.source_document_id is None
        assert it.source_document_name is None
        assert it.evidence_id.startswith("ev_")


# 5. Test Evidence Provenance Resolution Endpoint & Service
@pytest.mark.asyncio
async def test_evidence_provenance_resolution_endpoint(mock_user):
    candidate_ev = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_01",
                company="Google",
                role="Tech Lead",
                bullets=["Built distributed indexing system."],
                source_document_id="ingest_doc_100",
                source_document_name="google_resume.pdf",
            )
        ]
    )

    draft = IngestionDraft(
        ingestionId="ingest_doc_100",
        documentName="google_resume.pdf",
        documentType="Resume",
        fileSizeBytes=12000,
        status="Completed",
        fileUrl="https://storage.example.com/resumes/google_resume.pdf",
        createdAt="2026-09-24T10:00:00Z",
        updatedAt="2026-09-24T10:00:00Z",
    )

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=candidate_ev), \
         patch.object(IngestionService, "get_ingestion_draft", return_value=draft):
        
        detail = await EvidenceService.resolve_evidence_provenance(mock_user, "ev_exp_01")
        assert detail.evidence_id == "ev_exp_01"
        assert detail.user_id == mock_user.uid
        assert detail.source_document_id == "ingest_doc_100"
        assert detail.source_document_name == "google_resume.pdf"
        assert detail.ingestion_draft_status == "Completed"
        assert detail.file_url == "https://storage.example.com/resumes/google_resume.pdf"

    # API Endpoint integration test
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user
    client = TestClient(app)

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=candidate_ev), \
         patch.object(IngestionService, "get_ingestion_draft", return_value=draft):
        
        res = client.get("/api/v1/resumes/evidence/ev_exp_01/provenance")
        assert res.status_code == 200
        body = res.json()
        assert body["evidenceId"] == "ev_exp_01"
        assert body["sourceDocumentId"] == "ingest_doc_100"
        assert body["sourceDocumentName"] == "google_resume.pdf"
        assert body["fileUrl"] == "https://storage.example.com/resumes/google_resume.pdf"
    
    app.dependency_overrides.clear()


# 6. Test Provenance Tenant Isolation
@pytest.mark.asyncio
async def test_provenance_tenant_isolation(mock_user, mock_other_user):
    user_a_ev = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_secret_a",
                company="SecretCorp",
                role="Engineer",
                source_document_id="ingest_secret_a",
                source_document_name="secret_a.pdf",
            )
        ]
    )

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=user_a_ev):
        # User A can resolve their evidence
        detail = await EvidenceService.resolve_evidence_provenance(mock_user, "ev_exp_secret_a")
        assert detail.evidence_id == "ev_exp_secret_a"

    # User B fetching user A's evidence must return 404
    with patch.object(ResumeService, "get_candidate_resume_data", return_value=CandidateEvidence()):
        with pytest.raises(HTTPException) as exc_info:
            await EvidenceService.resolve_evidence_provenance(mock_other_user, "ev_exp_secret_a")
        assert exc_info.value.status_code == 404


# 7. Test Provenance with Missing Ingestion Draft
@pytest.mark.asyncio
async def test_provenance_with_missing_ingestion_draft(mock_user):
    candidate_ev = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_deleted_doc",
                company="Meta",
                role="Staff Engineer",
                bullets=["Led platform reliability."],
                source_document_id="ingest_deleted_999",
                source_document_name="meta_cv.pdf",
            )
        ]
    )

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=candidate_ev), \
         patch.object(IngestionService, "get_ingestion_draft", side_effect=HTTPException(status_code=404, detail="Draft not found")):
        
        detail = await EvidenceService.resolve_evidence_provenance(mock_user, "ev_exp_deleted_doc")
        assert detail.evidence_id == "ev_exp_deleted_doc"
        assert detail.source_document_id == "ingest_deleted_999"
        assert detail.source_document_name == "meta_cv.pdf"
        assert detail.ingestion_draft_status is None
        assert detail.file_url is None


# 8. Test Historical Variant Snapshot Immutability and Compatibility
def test_historical_variant_snapshot_immutability_and_compatibility():
    # Legacy variant payload created before provenance attributes
    legacy_payload = {
        "variantId": "var_legacy_001",
        "masterResumeId": "master_001",
        "title": "Netflix Senior Backend Variant",
        "targetRole": "Senior Backend Engineer",
        "targetCompany": "Netflix",
        "jobDescriptionHash": "abc123hash",
        "createdAt": "2026-08-01T12:00:00Z",
        "updatedAt": "2026-08-01T12:00:00Z",
        "snapshot": {
            "summary": "Experienced backend engineer specializing in high throughput systems.",
            "skills": [{"name": "Java"}, {"name": "Kafka"}],
            "experience": [
                {
                    "company": "Netflix",
                    "role": "Senior Engineer",
                    "bullets": ["Optimized playback streaming pipeline."],
                }
            ],
            "education": [],
            "projects": [],
        },
    }

    variant = TargetedResumeVariant.model_validate(legacy_payload)
    assert variant.variant_id == "var_legacy_001"
    assert variant.snapshot.skills[0].name == "Java"
    assert variant.snapshot.skills[0].source_document_id is None

    # Serializing back maintains exact legacy structure
    dumped = variant.model_dump(by_alias=True)
    assert dumped["variantId"] == "var_legacy_001"
    assert dumped["snapshot"]["skills"][0]["name"] == "Java"


# 9. Test Claim Validation Grounding Unbroken
def test_claim_validation_grounding_unbroken(mock_user):
    source_bullet = "Built DynamoDB storage engine scaling to 10M IOPS with 99.999% availability."
    item_context = {"dynamodb", "c++", "distributed systems", "aws", "senior", "engineer"}
    skills = ["DynamoDB", "Distributed Systems", "C++"]

    # Valid grounded claim
    result_valid = validate_claims_against_source(
        proposed_bullet="Built DynamoDB storage engine scaling to 10M IOPS with 99.999% availability.",
        source_evidence=source_bullet,
        item_context_tokens=item_context,
        candidate_skills=skills,
    )
    assert result_valid.is_valid is True

    # Hallucinated metric
    result_invalid = validate_claims_against_source(
        proposed_bullet="Built DynamoDB storage engine scaling to 500M IOPS with 100% availability.",
        source_evidence=source_bullet,
        item_context_tokens=item_context,
        candidate_skills=skills,
    )
    assert result_invalid.is_valid is False
    assert any(c.category == "Metric" for c in result_invalid.unsupported_claims)


# 10. Test Hybrid Retrieval & Ranking Pipeline Unbroken
def test_hybrid_retrieval_ranking_pipeline_unbroken(mock_user):
    from app.schemas.job_description import StructuredJobDescription, JobInfo, SkillRequirement
    from app.services.evidence_graph_service import CareerEvidenceGraph
    from app.ai.retrieval.evidence_ranker import EvidenceRanker

    evidence_items = [
        EvidenceItem(
            evidenceId="ev_skill_k8s",
            userId=mock_user.uid,
            sourceType="skills",
            sourceItemId="skill_k8s",
            title="Kubernetes",
            description="Expert proficiency in Kubernetes and container orchestration",
            skills=["Kubernetes", "Docker"],
            technologies=["Kubernetes", "Docker"],
            sourceDocumentId="ingest_cloud_01",
            sourceDocumentName="cloud_cv.pdf",
        ),
        EvidenceItem(
            evidenceId="ev_exp_k8s",
            userId=mock_user.uid,
            sourceType="experience",
            sourceItemId="exp_k8s",
            title="Staff Platform Engineer at CloudCorp",
            description="Managed 500-node Kubernetes clusters handling mission-critical traffic.",
            skills=["Kubernetes", "Terraform", "Go"],
            technologies=["Kubernetes", "Terraform"],
            responsibilities=["Managed 500-node Kubernetes clusters"],
            achievements=["handling mission-critical traffic"],
            metrics=["500-node"],
            sourceDocumentId="ingest_cloud_01",
            sourceDocumentName="cloud_cv.pdf",
        ),
    ]

    graph = CareerEvidenceGraph(user_id=mock_user.uid, items=evidence_items)

    jd = StructuredJobDescription(
        jobInfo=JobInfo(roleTitle="DevOps Engineer", company="CloudTech", seniorityLevel="Senior"),
        mustHaveSkills=[
            SkillRequirement(name="Kubernetes", category="DevOps", importance="MustHave", sourceEvidence="Kubernetes")
        ],
        preferredSkills=[],
    )

    match_res = HybridMatcher.match_job_requirements(jd, graph)
    assert match_res.overall_coverage_score > 0.0
    assert match_res.direct_match_count >= 1

    ranked = EvidenceRanker.rank_evidence(
        items=evidence_items,
        target_role="DevOps Engineer",
        job_description="Kubernetes cluster orchestration",
        must_have_skills=["Kubernetes"],
    )
    assert len(ranked) == 2
    top_item = ranked[0]
    assert "Kubernetes" in top_item.evidence_item.skills or "Kubernetes" in top_item.evidence_item.technologies
    assert top_item.evidence_item.source_document_id == "ingest_cloud_01"
    assert top_item.evidence_item.source_document_name == "cloud_cv.pdf"
    assert top_item.rank_score > 0.0
