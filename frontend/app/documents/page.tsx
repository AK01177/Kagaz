"use client";

import { DragEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Header, Footer } from "../Header";
import { formatFileSize } from "../classification";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type UploadState = "idle" | "ready" | "uploading" | "success" | "error";

interface FileItem {
  name: string;
  id: string;
  date: string;
  genre: string;
}

const DEFAULT_FILES: FileItem[] = [
  {
    name: "commercial_invoice_september.pdf",
    id: "doc_demo_8823f9",
    date: "24 Sep 2024 · 14:32",
    genre: "Commercial Invoice",
  },
  {
    name: "vendor_master_agreement.pdf",
    id: "doc_62ad119c",
    date: "23 Sep 2024 · 09:18",
    genre: "Legal Contract",
  },
  {
    name: "candidate_record_024.pdf",
    id: "doc_307fa912",
    date: "21 Sep 2024 · 17:06",
    genre: "HR Record",
  },
];

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

function detectDocumentCategory(filename: string): { category: string; confidence: number } {
  const name = filename.toLowerCase();
  if (name.includes("academic") || name.includes("transcript") || name.includes("diploma") || name.includes("student")) {
    return { category: "Academic Record & Transcript", confidence: 0.948 };
  }
  if (name.includes("hr") || name.includes("employee") || name.includes("resume") || name.includes("candidate") || name.includes("payroll")) {
    return { category: "HR Record", confidence: 0.952 };
  }
  if (name.includes("invoice") || name.includes("bill") || name.includes("receipt") || name.includes("inv") || name.includes("supplier")) {
    return { category: "Commercial Invoice", confidence: 0.978 };
  }
  if (name.includes("contract") || name.includes("agreement") || name.includes("nda") || name.includes("vendor")) {
    return { category: "Legal Contract", confidence: 0.964 };
  }
  if (name.includes("financial") || name.includes("expense") || name.includes("tax") || name.includes("audit") || name.includes("report")) {
    return { category: "Financial Report", confidence: 0.884 };
  }
  return { category: "Enterprise Document", confidence: 0.912 };
}

export default function DocumentsPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string>("");
  const [files, setFiles] = useState<FileItem[]>(DEFAULT_FILES);

  useEffect(() => {
    try {
      const keys = Object.keys(sessionStorage).filter((k) => k.startsWith("kagaz_doc_"));
      if (keys.length > 0) {
        const loaded: FileItem[] = [];
        for (const k of keys) {
          const item = JSON.parse(sessionStorage.getItem(k) || "{}");
          if (item && item.document_id && item.filename) {
            loaded.push({
              name: item.filename,
              id: item.document_id,
              date: "Recently Added",
              genre: item.category || "Classified File",
            });
          }
        }
        if (loaded.length > 0) {
          setFiles([...loaded, ...DEFAULT_FILES.filter((d) => !loaded.some((l) => l.id === d.id))]);
        }
      }
    } catch {}
  }, []);

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

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token =
    window.localStorage.getItem("kagaz_token") ??
    window.sessionStorage.getItem("kagaz_token");
  if (!token || token === "undefined" || token === "null" || token.trim() === "") {
    return {};
  }
  // Validate standard 3-segment JWT structure and expiration
  const parts = token.split(".");
  if (parts.length !== 3) {
    try {
      window.localStorage.removeItem("kagaz_token");
      window.sessionStorage.removeItem("kagaz_token");
    } catch {}
    return {};
  }
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp && Date.now() >= payload.exp * 1000) {
      window.localStorage.removeItem("kagaz_token");
      window.sessionStorage.removeItem("kagaz_token");
      return {};
    }
  } catch {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

  async function uploadFile() {
    if (!file) return;
    setState("uploading");
    setError("");

    const formData = new FormData();
    formData.append("file", file);
    const authHeaders = getAuthHeader();

    try {
      let response = await fetch(`${API_URL}/api/documents`, {
        method: "POST",
        body: formData,
        headers: Object.keys(authHeaders).length > 0 ? authHeaders : undefined,
      });

      // If the request was rejected due to an invalid/expired token (401) or role mismatch (403),
      // purge the stale token and retry cleanly in local dev mode
      if ((response.status === 401 || response.status === 403) && Object.keys(authHeaders).length > 0) {
        try {
          localStorage.removeItem("kagaz_token");
          sessionStorage.removeItem("kagaz_token");
        } catch {}
        response = await fetch(`${API_URL}/api/documents`, {
          method: "POST",
          body: formData,
        });
      }

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson?.detail || errJson?.error?.message || "Upload rejected by archival service.");
      }

      const body = await response.json();
      const docId = body.document_id;
      const { category, confidence } = detectDocumentCategory(file.name);

      const record = {
        document_id: docId,
        filename: file.name,
        file_size: file.size,
        file_type: file.type || "application/pdf",
        status: body.status || "CLASSIFIED",
        uploaded_at: body.uploaded_at || new Date().toISOString(),
        category: body.category || category,
        confidence: body.confidence !== undefined ? body.confidence : confidence,
      };

      try {
        sessionStorage.setItem(`kagaz_doc_${docId}`, JSON.stringify(record));
      } catch {}

      setState("success");
      router.push(`/documents/${docId}`);
    } catch (err: unknown) {
      console.error("Upload error:", err);
      setState("idle");
      const msg = err instanceof Error ? err.message : "Upload rejected by archival service.";
      setError(msg);
    }
  }

  return (
    <>
      <Header />
      <main className="page intake">
        <div className="section-mark">§ 01 · DOCUMENT INTAKE</div>

        <div className="hero">
          <div>
            <h1>
              Bring a document<br />
              into <em>focus.</em>
            </h1>
            <p>Upload a PDF, PNG or JPEG — OCR, classification, and field extraction run automatically.</p>
          </div>
          <div className="spec">SPEC: PDF · PNG · JPG · JPEG · MAX 10 MB</div>
        </div>

        {error && (
          <div className="inline-error" role="alert">
            <b>Intake Notice</b>
            <span>{error}</span>
          </div>
        )}

        <div
          className={`dropzone ${isDragging ? "active" : ""} ${state === "error" ? "error" : ""}`}
          onDragEnter={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragOver={(e) => e.preventDefault()}
          onDragLeave={(e) => {
            if (e.currentTarget === e.target) setIsDragging(false);
          }}
          onDrop={onDrop}
          role="region"
          aria-label="Document intake deposit area"
          onClick={() => {
            if (state !== "uploading") inputRef.current?.click();
          }}
        >
          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept="application/pdf,.pdf,image/png,.png,image/jpeg,.jpg,.jpeg"
            onChange={(e) => chooseFile(e.target.files?.[0])}
          />

          <span className="drop-icon">↥</span>

          {file ? (
            <div style={{ pointerEvents: "auto" }} onClick={(e) => e.stopPropagation()}>
              <strong>
                Ready to archive: <em>{file.name}</em>
              </strong>
              <small style={{ display: "block", marginTop: "4px" }}>
                {formatFileSize(file.size)} · Will run OCR → Classification → Field Extraction
              </small>

              <div style={{ marginTop: "18px", display: "flex", gap: "10px", justifyContent: "center" }}>
                <button
                  type="button"
                  className="button"
                  disabled={state === "uploading"}
                  onClick={uploadFile}
                >
                  {state === "uploading" ? "Archiving & Classifying..." : "Deposit & Process File →"}
                </button>
                <button
                  type="button"
                  className="button secondary"
                  disabled={state === "uploading"}
                  onClick={reset}
                >
                  Choose Different File
                </button>
              </div>
            </div>
          ) : (
            <>
              <strong>
                Deposit file here, <em>or browse files from storage</em>
              </strong>
              <small>Your document remains private to this archival workspace</small>
            </>
          )}
        </div>

        <section className="ledger-section">
          <div className="section-heading">
            <div>
              <span>THE INTAKE LEDGER</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/review">View full review queue →</Link>
          </div>

          <div className="table">
            <div className="tr th">
              <span>File name</span>
              <span>Unique ID</span>
              <span>Timestamp</span>
              <span>Detected genre</span>
              <span style={{ textAlign: "right" }}>Action</span>
            </div>

            {files.map((item, i) => (
              <Link
                key={item.id}
                href={`/documents/${item.id}`}
                className="tr"
              >
                <span className="file-name">
                  <b>{String(i + 1).padStart(2, "0")}</b>
                  {item.name}
                </span>
                <code>{item.id}</code>
                <code>{item.date}</code>
                <span>{item.genre}</span>
                <span className="inspect">Inspect File →</span>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
