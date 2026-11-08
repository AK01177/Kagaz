"""
Unit and integration tests for BE-09: Document Validation Service and Persistence.
Validates:
1. Compliant document achieves PASS status against active domain policy (US-19 AC1).
2. Missing mandatory fields trigger FAIL status with citation error issues (US-19 AC2).
3. Exceeding policy dollar thresholds triggers REVIEW_REQUIRED with policy citations (US-19 AC3).
4. Low extraction confidence flags REVIEW_REQUIRED with warning issues.
5. Multi-tenant isolation: Organization A validation cannot be accessed by Organization B (US-19 AC4).
6. Policy version snapshotting maintains audit trail immutability across policy updates (NFR-AUD-03).
7. Document metadata sidecar synchronization records validation status.
"""
import json
from pathlib import Path
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import Document, DocumentStatus
from app.models.organization import Organization
from app.models.policy import Policy
from app.models.validation import ValidationResult
from app.crud.policy import create_policy, update_policy
from app.crud.validation import get_validation_result, save_validation_result
from app.schemas.policy import PolicyCreate, PolicyUpdate
from services.validation import validate_document
from storage.document_storage import DocumentStorage


@pytest.fixture
def db():
    """In-memory SQLite database for isolated validation tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test organizations
    org_a = Organization(id="org_alpha_123", name="Alpha Corp", slug="alpha-corp")
    org_b = Organization(id="org_beta_456", name="Beta Corp", slug="beta-corp")
    session.add_all([org_a, org_b])

    # Seed test documents
    doc_a = Document(
        id="doc_alpha_001",
        organization_id="org_alpha_123",
        uploaded_by="user_1",
        filename="invoice_001.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="mock/path/invoice_001.pdf",
        status=DocumentStatus.CLASSIFIED,
    )
    session.add(doc_a)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


class TestBE09DocumentValidation:
    def test_validation_pass_when_compliant(self, db):
        policy_data = PolicyCreate(
            name="Alpha Expense Policy",
            domain="financial",
            content="Procurement invoices up to $500 do not require manual approval.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=policy_data)

        extracted_fields = {
            "invoice_number": "INV-2026-001",
            "supplier_name": "Office Supplies Co",
            "total_amount": "350.00",
        }
        confidences = {
            "invoice_number": 0.95,
            "supplier_name": 0.90,
            "total_amount": 0.92,
        }

        result = validate_document(
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            domain="financial",
            extracted_fields=extracted_fields,
            extracted_confidence=confidences,
            policy=policy,
            db=db,
            user_id="user_1",
        )

        assert result["status"] == "PASS"
        assert len(result["issues"]) == 0
        assert result["policy_id"] == policy.id
        assert result["policy_version"] == "v1"
        assert any("Alpha Expense Policy" in e["source"] for e in result["evidence"])

        # Persisted in DB
        record = get_validation_result(db, "doc_alpha_001", organization_id="org_alpha_123")
        assert record is not None
        assert record.status == "PASS"
        assert record.policy_version == "v1"

    def test_validation_fail_missing_required_fields(self, db):
        # Missing required supplier_name for financial domain
        extracted_fields = {
            "invoice_number": "INV-2026-002",
            "total_amount": "120.00",
        }

        result = validate_document(
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            domain="financial",
            extracted_fields=extracted_fields,
            db=db,
        )

        assert result["status"] == "FAIL"
        assert any(i["rule"] == "MANDATORY_SUPPLIER_NAME" for i in result["issues"])
        assert any(i["severity"] == "ERROR" for i in result["issues"])

    def test_validation_review_required_when_threshold_exceeded(self, db):
        policy_data = PolicyCreate(
            name="Budget Limit Policy",
            domain="financial",
            content="Standard expenses must not exceed $500 without department review.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=policy_data)

        extracted_fields = {
            "invoice_number": "INV-999",
            "supplier_name": "Global Hardware Ltd",
            "total_amount": "$750.00",
        }

        result = validate_document(
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            domain="financial",
            extracted_fields=extracted_fields,
            policy=policy,
            db=db,
        )

        assert result["status"] == "REVIEW_REQUIRED"
        assert any(i["rule"] == "POLICY_LIMIT_EXCEEDED" for i in result["issues"])
        assert any(i["severity"] == "WARNING" for i in result["issues"])

    def test_validation_review_required_low_confidence(self, db):
        extracted_fields = {
            "invoice_number": "INV-1234",
            "supplier_name": "Acme Corp",
            "total_amount": "200.00",
        }
        confidences = {
            "invoice_number": 0.50,  # Below 0.65 threshold
            "supplier_name": 0.95,
            "total_amount": 0.90,
        }

        result = validate_document(
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            domain="financial",
            extracted_fields=extracted_fields,
            extracted_confidence=confidences,
            db=db,
        )

        assert result["status"] == "REVIEW_REQUIRED"
        assert any("LOW_CONFIDENCE" in i["rule"] for i in result["issues"])

    def test_validation_tenant_isolation(self, db):
        save_validation_result(
            db=db,
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            status="PASS",
        )

        # Org Alpha can read validation result
        record_alpha = get_validation_result(db, "doc_alpha_001", organization_id="org_alpha_123")
        assert record_alpha is not None

        # Org Beta cannot read Org Alpha's validation result
        record_beta = get_validation_result(db, "doc_alpha_001", organization_id="org_beta_456")
        assert record_beta is None

    def test_policy_version_recorded_in_validation_result(self, db):
        policy_data = PolicyCreate(
            name="Immutability Test Policy",
            domain="financial",
            content="Initial limit is $500.",
        )
        policy = create_policy(db, organization_id="org_alpha_123", data=policy_data)
        assert policy.current_version == "v1"

        # Validate with v1
        result = validate_document(
            document_id="doc_alpha_001",
            organization_id="org_alpha_123",
            domain="financial",
            extracted_fields={"invoice_number": "1", "supplier_name": "A", "total_amount": "100"},
            policy=policy,
            db=db,
        )
        assert result["policy_version"] == "v1"

        # Update policy to v2
        update_data = PolicyUpdate(content="Updated limit is $1,000.", changelog="Bumped to $1000")
        updated_policy = update_policy(db, policy, update_data)
        assert updated_policy.current_version == "v2"

        # Historical validation record still references v1 (audit traceability)
        record = get_validation_result(db, "doc_alpha_001", organization_id="org_alpha_123")
        assert record.policy_version == "v1"

    def test_metadata_sidecar_sync(self, db):
        with tempfile.TemporaryDirectory(dir=".") as tmp:
            tmp_path = Path(tmp)
            metadata_dir = tmp_path / "metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            meta_file = metadata_dir / "doc_alpha_001.json"
            meta_file.write_text(json.dumps({
                "document_id": "doc_alpha_001",
                "organization_id": "org_alpha_123",
                "category": "financial",
                "status": "EXTRACTED",
            }), encoding="utf-8")

            mock_storage = DocumentStorage(base_dir=tmp_path)

            validate_document(
                document_id="doc_alpha_001",
                organization_id="org_alpha_123",
                domain="financial",
                extracted_fields={"invoice_number": "INV-1", "supplier_name": "Test", "total_amount": "100"},
                db=db,
                storage=mock_storage,
            )

            # Verify sidecar updated
            updated_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert updated_meta["status"] == "VALIDATED"
            assert updated_meta["validation"]["status"] == "PASS"
