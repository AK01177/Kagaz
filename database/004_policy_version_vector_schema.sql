-- DB-04: Policy, Version, Chunk and Embedding Schema
-- Assumes existing tables: organizations(id uuid), users(id uuid)
-- Requires PostgreSQL 13+ (gen_random_uuid) and pgvector.
-- EMBEDDING DIMENSION: set to match your model (e.g. 1536 for OpenAI
-- text-embedding-3-small, 768 for many open models). Change vector(1536) below.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------- policies
CREATE TABLE policies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title           text NOT NULL,
    description     text,
    domain          text,            -- e.g. 'finance', 'hr'
    document_type   text,            -- e.g. 'invoice', 'contract'
    created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- lets child tables use (id, organization_id) composite FKs
    -- so a child can never point at another tenant's policy
    CONSTRAINT uq_policies_id_org UNIQUE (id, organization_id)
);

CREATE INDEX idx_policies_org ON policies (organization_id);
CREATE INDEX idx_policies_org_domain ON policies (organization_id, domain, document_type);

-- --------------------------------------------------------- policy_versions
CREATE TABLE policy_versions (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL,
    policy_id        uuid NOT NULL,
    version_number   integer NOT NULL CHECK (version_number > 0),
    is_active        boolean NOT NULL DEFAULT false,
    file_object_key  text NOT NULL,           -- key of original file in object storage
    original_filename text,
    ingestion_status text NOT NULL DEFAULT 'pending'
        CHECK (ingestion_status IN ('pending','processing','completed','failed')),
    ingestion_error  text,
    embedding_model  text,                    -- model used for this version's chunks
    embedding_dim    integer,
    created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    activated_at     timestamptz,
    CONSTRAINT fk_pv_policy FOREIGN KEY (policy_id, organization_id)
        REFERENCES policies (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT uq_pv_policy_version UNIQUE (policy_id, version_number),
    CONSTRAINT uq_pv_id_policy_org UNIQUE (id, policy_id, organization_id),
    -- only a fully ingested version may be active
    CONSTRAINT ck_pv_active_requires_ingested
        CHECK (NOT is_active OR ingestion_status = 'completed')
);

-- Deterministic active version: at most ONE active version per policy.
CREATE UNIQUE INDEX uq_pv_one_active_per_policy
    ON policy_versions (policy_id) WHERE is_active;

CREATE INDEX idx_pv_org_status ON policy_versions (organization_id, ingestion_status);

-- Activate a version atomically (deactivates the previous one).
CREATE OR REPLACE FUNCTION activate_policy_version(p_version_id uuid)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_policy uuid;
BEGIN
    SELECT policy_id INTO v_policy FROM policy_versions WHERE id = p_version_id FOR UPDATE;
    IF v_policy IS NULL THEN
        RAISE EXCEPTION 'policy version % not found', p_version_id;
    END IF;
    UPDATE policy_versions SET is_active = false
        WHERE policy_id = v_policy AND is_active AND id <> p_version_id;
    UPDATE policy_versions SET is_active = true, activated_at = now()
        WHERE id = p_version_id;
END $$;

-- ----------------------------------------------------------- policy_chunks
CREATE TABLE policy_chunks (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL,
    policy_id         uuid NOT NULL,
    policy_version_id uuid NOT NULL,
    chunk_index       integer NOT NULL CHECK (chunk_index >= 0),
    content           text NOT NULL,
    page_number       integer,          -- nullable: kept when available
    section_title     text,
    char_start        integer,
    char_end          integer,
    domain            text,
    document_type     text,
    embedding         vector(1536) NOT NULL,   -- keep in sync with embedding model
    created_at        timestamptz NOT NULL DEFAULT now(),
    -- chunk must reference a version that belongs to the same policy AND org
    CONSTRAINT fk_chunk_version FOREIGN KEY (policy_version_id, policy_id, organization_id)
        REFERENCES policy_versions (id, policy_id, organization_id) ON DELETE CASCADE,
    CONSTRAINT uq_chunk_version_index UNIQUE (policy_version_id, chunk_index),
    CONSTRAINT uq_chunk_id_org UNIQUE (id, organization_id)
);

CREATE INDEX idx_chunks_org_version ON policy_chunks (organization_id, policy_version_id);
CREATE INDEX idx_chunks_org_domain  ON policy_chunks (organization_id, domain, document_type);

-- Approximate nearest-neighbour search (cosine). HNSW needs pgvector >= 0.5.
CREATE INDEX idx_chunks_embedding_hnsw
    ON policy_chunks USING hnsw (embedding vector_cosine_ops);

-- Convenience view: chunks of ACTIVE versions only.
CREATE VIEW active_policy_chunks AS
SELECT c.*
FROM policy_chunks c
JOIN policy_versions v ON v.id = c.policy_version_id
WHERE v.is_active;

COMMIT;

-- ======================================================================
-- TENANT-AWARE QUERY PATTERN (document this in docs/)
-- Always filter by organization_id; never rely on similarity alone.
--
--   SELECT id, content, page_number, section_title,
--          embedding <=> :query_embedding AS distance
--   FROM active_policy_chunks
--   WHERE organization_id = :org_id
--     AND (:domain IS NULL OR domain = :domain)
--   ORDER BY embedding <=> :query_embedding
--   LIMIT 5;
--
-- Indexes: (organization_id, policy_version_id) for scoping,
-- HNSW on embedding for vector search, partial unique index
-- uq_pv_one_active_per_policy for deterministic active version.
-- Note: with HNSW + WHERE filter, pgvector filters after the index scan;
-- raise hnsw.ef_search or use iterative scan for small tenants.
-- ======================================================================
