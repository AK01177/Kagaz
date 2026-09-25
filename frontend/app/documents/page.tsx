"use client";

import { DragEvent, useRef, useState } from "react";
import Link from "next/link";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type UploadState = "idle" | "ready" | "uploading" | "success" | "error";

type UploadResult = {
  document_id: string;
  filename: string;
  status: string;
  uploaded_at: string;
};

type ApiError = {
  error?: { code?: string; message?: string };
};

function formatSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function validateFile(file: File) {
  if (!file.name.toLowerCase().endsWith(".pdf") || file.type && !["application/pdf", "application/octet-stream"].includes(file.type)) {
    return "Only PDF files are supported right now.";
  }
  if (file.size === 0) return "This file is empty. Choose a readable PDF.";
  if (file.size > MAX_FILE_SIZE) return "This file is larger than the 10 MB limit.";
  return null;
}

export default function DocumentsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);

  function chooseFile(nextFile?: File) {
    if (!nextFile) return;
    const validationError = validateFile(nextFile);
    setError(validationError ?? "");
    setResult(null);
    setFile(validationError ? null : nextFile);
    setState(validationError ? "error" : "ready");
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  function reset() {
    setFile(null);
    setResult(null);
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
    const token = window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token");

    try {
      const response = await fetch(`${API_URL}/api/documents`, {
        method: "POST",
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const body = (await response.json()) as UploadResult & ApiError;
      if (!response.ok) {
        throw new Error(body.error?.message ?? "The document could not be uploaded.");
      }
      setResult(body);
      setState("success");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The document could not be uploaded.");
      setState("error");
    }
  }

  const isBusy = state === "uploading";

  return (
    <main className="upload-page">
      <nav className="topbar" aria-label="Primary navigation">
        <Link className="wordmark" href="/">Kagaz<span>.</span></Link>
        <div className="topbar-meta"><span className="status-dot" /> Secure workspace</div>
      </nav>

      <section className="upload-shell" aria-labelledby="upload-title">
        <div className="eyebrow"><span>01</span> Document intake</div>
        <div className="heading-row">
          <div>
            <h1 id="upload-title">Bring a document<br /><em>into focus.</em></h1>
            <p className="intro">Upload a document to start its journey through Kagaz. We&apos;ll acknowledge it immediately, then prepare it for review.</p>
          </div>
          <div className="file-note" aria-label="Current file requirements">
            <span className="file-note-mark">PDF</span>
            <span>PDF file only<br />Up to 10 MB</span>
          </div>
        </div>

        <div
          className={`dropzone ${isDragging ? "dropzone-active" : ""} ${state === "error" ? "dropzone-error" : ""}`}
          onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => { if (event.currentTarget === event.target) setIsDragging(false); }}
          onDrop={onDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
          aria-label="Choose a PDF document to upload"
        >
          <input ref={inputRef} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={(event) => chooseFile(event.target.files?.[0])} />
          {file && state !== "error" ? (
            <div className="selected-file">
              <div className="pdf-icon">PDF</div>
              <div className="selected-file-info"><strong>{file.name}</strong><span>{formatSize(file.size)} · Pending server validation</span></div>
              {!isBusy && <button className="icon-button" type="button" onClick={(event) => { event.stopPropagation(); reset(); }} aria-label="Remove selected file">×</button>}
            </div>
          ) : (
            <div className="dropzone-prompt">
              <div className="upload-glyph" aria-hidden="true">↑</div>
              <strong>{isDragging ? "Release to add your PDF" : "Drop your PDF here"}</strong>
              <span>or <button className="browse-button" type="button" onClick={(event) => { event.stopPropagation(); inputRef.current?.click(); }}>browse files</button></span>
            </div>
          )}
        </div>

        {error && <p className="feedback feedback-error" role="alert"><span>!</span>{error}</p>}

        {state === "success" && result ? (
          <div className="success-panel" role="status">
            <div className="success-check">✓</div>
            <div><strong>Upload accepted</strong><span>{result.filename} is now in your workspace · ID {result.document_id}</span></div>
            <button className="text-button" type="button" onClick={reset}>Upload another</button>
          </div>
        ) : (
          <div className="action-row">
            <p className="privacy-note"><span aria-hidden="true">⊙</span> Your document is encrypted in transit.</p>
            <button className="primary-button" type="button" disabled={!file || isBusy} onClick={uploadFile}>
              {isBusy ? "Uploading..." : "Upload document"}<span aria-hidden="true">→</span>
            </button>
          </div>
        )}

        <div className="process-strip" aria-label="Upload process">
          <span className="process-active"><b>1</b> Upload</span><i />
          <span><b>2</b> Prepare</span><i />
          <span><b>3</b> Review</span>
        </div>
      </section>
    </main>
  );
}