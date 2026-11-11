-- DB-05: Workflow, Validation and Audit Schema
-- Depends on 004 (policies, policy_versions, policy_chunks) and existing
-- organizations, users, documents(id uuid, organization_id uuid).

BEGIN;

-- Allow composite FKs (document_id, organization_id) -> documents
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_id_org
    ON documents (id, organization_id);

-- ------------------------------------------------------- document_workflows
-- Human workflow state. Independent from validation state (validation_runs).
CREATE TABLE document_workflows (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    document_id     uuid NOT NULL,
    status          text NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review','in_review','changes_requested',
                          'approved','rejected')),
    assigned_to     uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_wf_document FOREIGN KEY (document_id, organization_id)
        REFERENCES documents (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT uq_wf_document UNIQUE (document_id),
    CONSTRAINT uq_wf_id_org UNIQUE (id, organization_id)
);
CREATE INDEX idx_wf_org_status   ON document_workflows (organization_id, status);
CREATE INDEX idx_wf_org_assignee ON document_workflows (organization_id, assigned_to);

-- ---------------------------------------------------------- validation_runs
-- One row per validation attempt. Keeps the exact policy version used.
CREATE TABLE validation_runs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL,
    document_id       uuid NOT NULL,
    policy_id         uuid NOT NULL,
    policy_version_id uuid NOT NULL,
    status            text NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed')),
    outcome           text CHECK (outcome IN ('pass','fail','needs_review')),
    model_name        text,
    summary           jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message     text,
    triggered_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    started_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz,
    CONSTRAINT fk_vr_document FOREIGN KEY (document_id, organization_id)
        REFERENCES documents (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT fk_vr_policy_version FOREIGN KEY (policy_version_id, policy_id, organization_id)
        REFERENCES policy_versions (id, policy_id, organization_id),  -- no cascade: keep history
    CONSTRAINT uq_vr_id_org UNIQUE (id, organization_id)
);
CREATE INDEX idx_vr_org_document ON validation_runs (organization_id, document_id, started_at DESC);
CREATE INDEX idx_vr_policy_version ON validation_runs (policy_version_id);

-- -------------------------------------------------------- validation_findings
CREATE TABLE validation_findings (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL,
    validation_run_id uuid NOT NULL,
    severity         text NOT NULL CHECK (severity IN ('info','warning','error')),
    category         text,                    -- e.g. 'missing_field','policy_violation'
    field_name       text,
    extracted_value  text,
    expected_value   text,
    message          text NOT NULL,
    policy_chunk_id  uuid,                    -- source reference into policy
    document_page    integer,
    document_excerpt text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_vf_run FOREIGN KEY (validation_run_id, organization_id)
        REFERENCES validation_runs (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT fk_vf_chunk FOREIGN KEY (policy_chunk_id, organization_id)
        REFERENCES policy_chunks (id, organization_id) ON DELETE SET NULL (policy_chunk_id),
    CONSTRAINT uq_vf_id_org UNIQUE (id, organization_id)
);
CREATE INDEX idx_vf_org_run ON validation_findings (organization_id, validation_run_id);

-- ------------------------------------------------------------ review_comments
-- Append-only: comments and request-changes records.
CREATE TABLE review_comments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    document_id     uuid NOT NULL,
    finding_id      uuid,
    author_id       uuid NOT NULL REFERENCES users(id),
    comment_type    text NOT NULL DEFAULT 'comment'
        CHECK (comment_type IN ('comment','request_changes')),
    body            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_rc_document FOREIGN KEY (document_id, organization_id)
        REFERENCES documents (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT fk_rc_finding FOREIGN KEY (finding_id, organization_id)
        REFERENCES validation_findings (id, organization_id) ON DELETE SET NULL (finding_id)
);
CREATE INDEX idx_rc_org_document ON review_comments (organization_id, document_id, created_at);

-- ----------------------------------------------------------- review_decisions
-- Append-only: every approve/reject is a NEW row; latest row = current decision.
CREATE TABLE review_decisions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL,
    document_id       uuid NOT NULL,
    validation_run_id uuid,
    decided_by        uuid NOT NULL REFERENCES users(id),
    decision          text NOT NULL CHECK (decision IN ('approved','rejected')),
    reason            text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_rd_document FOREIGN KEY (document_id, organization_id)
        REFERENCES documents (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT fk_rd_run FOREIGN KEY (validation_run_id, organization_id)
        REFERENCES validation_runs (id, organization_id) ON DELETE SET NULL (validation_run_id),
    -- rejection must carry a reason
    CONSTRAINT ck_rd_reject_reason CHECK (decision <> 'rejected' OR length(btrim(coalesce(reason,''))) > 0)
);
CREATE INDEX idx_rd_org_document ON review_decisions (organization_id, document_id, created_at DESC);

-- --------------------------------------------------------------- audit_events
CREATE TABLE audit_events (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id),
    actor_id        uuid REFERENCES users(id) ON DELETE SET NULL,  -- NULL = system
    document_id     uuid,
    action          text NOT NULL,        -- e.g. 'document.approved'
    entity_type     text,
    entity_id       uuid,
    details         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_time     ON audit_events (organization_id, created_at DESC);
CREATE INDEX idx_audit_org_document ON audit_events (organization_id, document_id, created_at);

-- ------------------------------------------------------ append-only guards
CREATE OR REPLACE FUNCTION forbid_update_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only (% not allowed)', TG_TABLE_NAME, TG_OP;
END $$;

CREATE TRIGGER trg_audit_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();
CREATE TRIGGER trg_decisions_append_only
    BEFORE UPDATE OR DELETE ON review_decisions
    FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();
CREATE TRIGGER trg_comments_append_only
    BEFORE UPDATE OR DELETE ON review_comments
    FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();

-- Convenience: current decision per document (latest row wins)
CREATE VIEW current_review_decisions AS
SELECT DISTINCT ON (document_id) *
FROM review_decisions
ORDER BY document_id, created_at DESC, id DESC;

COMMIT;
