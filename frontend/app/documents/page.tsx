"use client";

import { DragEvent, useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { formatFileSize, formatDate } from "../classification";
import { useAuth } from "../context/AuthContext";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

type UploadState = "idle" | "ready" | "uploading" | "success" | "error";

interface FileItem {
  name: string;
  id: string;
  date: string;
  genre: string;
  confidence?: string;
  status?: string;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];
const ACCEPTED_MIME = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "application/octet-stream",
];

function validateFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return "Only PDF, PNG, JPG and JPEG files are supported.";
  }
  if (file.type && !ACCEPTED_MIME.includes(file.type)) {
    return "Only PDF, PNG, JPG and JPEG files are supported.";
  }
  if (file.size === 0) return "The selected file is empty (0 bytes).";
  if (file.size > MAX_FILE_SIZE) return "File exceeds the archival ceiling of 10 MB.";
  return null;
}

function DocumentsContent() {
  const router = useRouter();
  const { fetchWithAuth, user, activeOrgId, isAuthenticated } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGenre, setSelectedGenre] = useState("ALL");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);

  const currentOrg = activeOrgId || user?.organization_id || "ACME GLOBAL ENTERPRISE";

  const loadDocuments = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents`);
      if (res.ok) {
        const raw = await res.json().catch(() => []);
        const docsList = Array.isArray(raw) ? raw : raw?.documents || [];
        if (docsList.length > 0) {
          const items: FileItem[] = docsList.map(
            (d: {
              id?: string;
              document_id?: string;
              filename?: string;
              name?: string;
              created_at?: string;
              category?: string;
              document_type?: string;
              confidence?: number;
              status?: string;
            }) => ({
              name: d.filename || d.name || "document.pdf",
              id: d.id || d.document_id || "doc_unknown",
              date: d.created_at ? formatDate(d.created_at) : "Recent",
              genre: d.category || d.document_type || "Unclassified document",
              confidence: d.confidence != null
                ? `${(d.confidence > 1 ? d.confidence : d.confidence * 100).toFixed(1)}%`
                : "—",
              status: d.status || "UPLOADED",
            })
          );
          setFiles(items);
          return;
        }
        setFiles([]);
        return;
      }
    } catch {
      // Fallback to local session storage
    } finally {
      setLoading(false);
    }

    try {
      const cachePrefix = `kagaz_doc_${user?.user_id || ""}_${activeOrgId || user?.organization_id || ""}_`;
      const keys = Object.keys(sessionStorage).filter((k) => k.startsWith(cachePrefix));
      if (keys.length > 0) {
        const loaded: FileItem[] = [];
        for (const k of keys) {
          const item = JSON.parse(sessionStorage.getItem(k) || "{}");
          if (item && item.document_id && item.filename) {
            loaded.push({
              name: item.filename,
              id: item.document_id,
              date: item.uploaded_at ? formatDate(item.uploaded_at) : "Recently Added",
              genre: item.category || "Unclassified document",
              confidence: item.confidence != null ? `${(item.confidence * 100).toFixed(1)}%` : "—",
              status: item.status || "UPLOADED",
            });
          }
        }
        if (loaded.length > 0) {
          setFiles(loaded);
          return;
        }
      }
    } catch {}
    setFiles([]);
  }, [activeOrgId, fetchWithAuth, isAuthenticated, user]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadDocuments();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadDocuments]);

  function chooseFile(nextFile?: File) {
    if (!nextFile || state === "uploading") return;
    const validationError = validateFile(nextFile);
    if (validationError) {
      setError(validationError);
      setFile(null);
      setState("error");
      return;
    }
    setError("");
    setFile(nextFile);
    setState("ready");
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }

  function reset() {
    setFile(null);
    setError("");
    setState("idle");
    if (inputRef.current) inputRef.current.value = "";
  }

  async function uploadFile() {
    if (!file) return;
    setState("uploading");
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    let docId = "";

    try {
      const response = await fetchWithAuth(`${API_URL}/api/documents`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const serverMsg =
          errorData?.detail?.message ||
          errorData?.detail ||
          errorData?.error?.message ||
          `Upload failed with HTTP ${response.status}.`;
        setError(serverMsg);
        setState("error");
        return;
      }

      const body = await response.json().catch(() => ({}));
      docId = body.document_id;
      if (!docId) {
        setError("The upload completed without a document ID. Refresh the document list before retrying.");
        setState("error");
        return;
      }

      const record = {
        document_id: docId,
        filename: file.name,
        file_size: file.size,
        status: body.status || "UPLOADED",
        category: body.category || null,
        confidence: body.confidence ?? null,
        uploaded_at: body.uploaded_at || new Date().toISOString(),
        organization_id: activeOrgId || user?.organization_id,
        submitter_id: user?.user_id,
      };

      try {
        const cacheKey = `kagaz_doc_${user?.user_id || ""}_${activeOrgId || user?.organization_id || ""}_${docId}`;
        sessionStorage.setItem(cacheKey, JSON.stringify(record));
      } catch {}

      setState("success");
      await loadDocuments();

      setTimeout(() => {
        router.push(`/documents/${docId}`);
      }, 700);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error during upload.";
      setError(msg);
      setState("error");
    }
  }

  const filteredFiles = files.filter((f) => {
    const matchesSearch =
      f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.genre.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesGenre =
      selectedGenre === "ALL" ||
      f.genre.toLowerCase().includes(selectedGenre.toLowerCase());
    return matchesSearch && matchesGenre;
  });

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="inbox" size={14} /> Workspace <span>/</span> Intake &amp; Library
        </div>
        <div className="sync">
          <span className="brand-dot" /> {loading ? "Syncing..." : "Synced just now"}
        </div>
        <div className="head-main">
          <div>
            <h1>Bring a document into focus.</h1>
            <p className="subline">
              DOCUMENT INTAKE · {files.length} RECORDS IN {currentOrg.toUpperCase()}
            </p>
          </div>
          <Button icon="sliders" onClick={loadDocuments}>
            Sync Library
          </Button>
        </div>
      </header>

      <div className="intake-body">
        {/* Upload dropzone matching Figma Board 08 */}
        <div
          className={`upload-panel ${isDragging ? "dragging" : ""}`}
          style={{
            border: isDragging ? "2px dashed var(--brand)" : "1px dashed var(--line2)",
            background: isDragging ? "var(--brand-surface)" : "white",
            transition: "all 0.2s ease",
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            ref={inputRef}
            style={{ display: "none" }}
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(e) => chooseFile(e.target.files?.[0])}
          />
          <span className="upload-icon">↥</span>
          <h2>Deposit a file for intelligence.</h2>
          <p>
            {file
              ? `Ready to process: ${file.name} (${formatFileSize(file.size)})`
              : "Drop a PDF or image here or browse files from storage."}
          </p>
          <span className="upload-spec">PDF · PNG · JPG · JPEG · MAXIMUM 10 MB</span>

          <div style={{ marginTop: "16px", display: "flex", gap: "10px" }}>
            {!file ? (
              <Button variant="primary" icon="file" onClick={() => inputRef.current?.click()}>
                Select Document File
              </Button>
            ) : (
              <>
                <Button variant="primary" icon="check" onClick={uploadFile} disabled={state === "uploading"}>
                  {state === "uploading" ? "RapidOCR Ingesting..." : "Process & Extract"}
                </Button>
                <Button variant="ghost" onClick={reset} disabled={state === "uploading"}>
                  Cancel
                </Button>
              </>
            )}
          </div>

          {error && (
            <p style={{ color: "var(--red)", fontSize: "11px", marginTop: "12px", fontWeight: 500 }}>
              ⚠ {error}
            </p>
          )}

          {state === "success" && (
            <p style={{ color: "var(--green)", fontSize: "11px", marginTop: "12px", fontWeight: 600 }}>
              ✓ File registered. Redirecting to Document Inspector...
            </p>
          )}
        </div>

        {/* Library Card with Filters & Search */}
        <section className="library-card">
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">WORKSPACE REPOSITORY</span>
              <h2>Intake &amp; Library</h2>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "4px" }}>
                {["ALL", "INVOICE", "CONTRACT", "RECORD"].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setSelectedGenre(cat)}
                    style={{
                      border: "1px solid var(--line)",
                      background: selectedGenre === cat ? "var(--brand-surface)" : "white",
                      color: selectedGenre === cat ? "var(--brand)" : "var(--muted)",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "10px",
                      fontWeight: 600,
                    }}
                  >
                    {cat}
                  </button>
                ))}
              </div>
              <label className="search">
                <Icon name="search" size={13} />
                <input
                  placeholder="Find a document…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <kbd>⌘ K</kbd>
              </label>
            </div>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head">
              <span>FILE NAME</span>
              <span>UNIQUE ID</span>
              <span>UPLOADED</span>
              <span>CLASSIFICATION</span>
              <span>AI CONF.</span>
            </div>

            {filteredFiles.map((d) => (
              <Link className="lib-row" key={d.id} href={`/documents/${d.id}`}>
                <span className="doc-name">
                  <span className="doc-icon">
                    <Icon name="file" />
                  </span>
                  <b>{d.name}</b>
                </span>
                <code>{d.id}</code>
                <span>{d.date}</span>
                <span>{d.genre}</span>
                <Badge
                  tone={
                    d.confidence && parseFloat(d.confidence) < 75
                      ? "amber"
                      : d.confidence && parseFloat(d.confidence) >= 90
                      ? "green"
                      : "violet"
                  }
                >
                  {d.confidence || "—"}
                </Badge>
              </Link>
            ))}

            {filteredFiles.length === 0 && (
              <div style={{ padding: "40px", textAlign: "center", color: "var(--muted)" }}>
                No documents match your query. Deposit a new file above to start extraction.
              </div>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsContent />
    </ProtectedRoute>
  );
}
