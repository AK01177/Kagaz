"use client";

import React, { useRef, useEffect } from "react";
import { Button, Icon } from "../../../../components/AppShell";
import { AssistantMessage } from "../types";

interface AssistantTabProps {
  messages: AssistantMessage[];
  questionInput: string;
  queryingAssistant: boolean;
  onQuestionInputChange: (value: string) => void;
  onAskAssistant: (e?: React.FormEvent, customQuery?: string) => void;
}

export function AssistantTab({
  messages,
  questionInput,
  queryingAssistant,
  onQuestionInputChange,
  onAskAssistant,
}: AssistantTabProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, queryingAssistant]);

  return (
    <div className="assistant-workspace">
      {/* Read-Only Notice Banner */}
      <div className="assistant-banner">
        <Icon name="shield" size={18} />
        <div>
          <b>Grounded Document &amp; Policy Assistant</b>
          <p style={{ margin: "2px 0 0" }}>
            Answers are grounded strictly in this document&apos;s extractions and your organization&apos;s active policy documents. The assistant is strictly read-only and cannot alter document states or make approval decisions.
          </p>
        </div>
      </div>

      {/* Suggested Queries */}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase" }}>
          Suggested Inquiries:
        </span>
        <button
          type="button"
          onClick={() => onAskAssistant(undefined, "What is the total amount and payment terms on this document?")}
          style={{
            background: "white",
            border: "1px solid var(--line)",
            borderRadius: "14px",
            padding: "4px 10px",
            fontSize: "10px",
            cursor: "pointer",
            color: "var(--body)",
          }}
        >
          Total amount &amp; payment terms
        </button>
        <button
          type="button"
          onClick={() => onAskAssistant(undefined, "Does this document meet vendor and tax ID requirements?")}
          style={{
            background: "white",
            border: "1px solid var(--line)",
            borderRadius: "14px",
            padding: "4px 10px",
            fontSize: "10px",
            cursor: "pointer",
            color: "var(--body)",
          }}
        >
          Vendor &amp; tax ID validation
        </button>
        <button
          type="button"
          onClick={() => onAskAssistant(undefined, "Are there any policy compliance violations or flags?")}
          style={{
            background: "white",
            border: "1px solid var(--line)",
            borderRadius: "14px",
            padding: "4px 10px",
            fontSize: "10px",
            cursor: "pointer",
            color: "var(--body)",
          }}
        >
          Policy flags &amp; violations
        </button>
      </div>

      {/* Messages Stream */}
      <div className="chat-messages-container">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`chat-bubble ${m.sender === "user" ? "user" : "assistant"}`}
          >
            <div>{m.content}</div>

            {/* Grounding & Uncertainty Indicators */}
            {m.sender === "assistant" && m.id !== "welcome" && (
              <div>
                {m.is_grounded ? (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "10px",
                      color: "var(--green)",
                      fontWeight: 600,
                      marginTop: "6px",
                    }}
                  >
                    ✓ Grounded in document &amp; policy evidence
                  </span>
                ) : (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "10px",
                      color: "var(--amber)",
                      fontWeight: 600,
                      marginTop: "6px",
                    }}
                  >
                    ⚠ Partial or ungrounded evidence
                  </span>
                )}

                {m.limitation && (
                  <div
                    style={{
                      marginTop: "8px",
                      background: "var(--amber-bg)",
                      border: "1px solid rgba(158, 109, 36, 0.2)",
                      borderRadius: "4px",
                      padding: "6px 10px",
                      fontSize: "10px",
                      color: "var(--amber)",
                    }}
                  >
                    <b>Limitation Notice:</b> {m.limitation}
                  </div>
                )}

                {/* Citations Grid */}
                {m.sources && m.sources.length > 0 && (
                  <div className="assistant-citations-grid">
                    <b style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase" }}>
                      Supporting Grounded Sources ({m.sources.length})
                    </b>
                    {m.sources.map((src, sIdx) => {
                      const type = src.source_type || "DOCUMENT_FIELD";
                      const badgeClass =
                        type === "POLICY_CHUNK"
                          ? "policy"
                          : type === "VALIDATION_FINDING"
                          ? "finding"
                          : "doc";

                      return (
                        <div className="assistant-source-card" key={sIdx}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                            <span className={`source-type-badge ${badgeClass}`}>
                              {type.replace(/_/g, " ")}
                            </span>
                            <strong style={{ fontSize: "11px", color: "var(--ink)" }}>{src.title}</strong>
                            <span style={{ color: "var(--muted)", fontSize: "10px", marginLeft: "auto" }}>
                              {src.reference}
                            </span>
                          </div>
                          <blockquote
                            style={{
                              margin: 0,
                              paddingLeft: "8px",
                              borderLeft: "2px solid var(--violet)",
                              fontSize: "10px",
                              color: "var(--body)",
                              fontStyle: "italic",
                            }}
                          >
                            &ldquo;{src.excerpt}&rdquo;
                          </blockquote>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div
              style={{
                fontSize: "9px",
                color: m.sender === "user" ? "rgba(255,255,255,0.7)" : "var(--muted)",
                alignSelf: "flex-end",
                marginTop: "4px",
              }}
            >
              {m.timestamp}
            </div>
          </div>
        ))}

        {queryingAssistant && (
          <div className="chat-bubble assistant">
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--muted)", fontSize: "11px" }}>
              <span>Synthesizing grounded citations...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Query Input Box */}
      <form className="assistant-input-box" onSubmit={(e) => onAskAssistant(e)}>
        <input
          type="text"
          className="assistant-input-field"
          placeholder="Ask a question about document values or policy requirements..."
          aria-label="Ask assistant a question"
          value={questionInput}
          onChange={(e) => onQuestionInputChange(e.target.value)}
          disabled={queryingAssistant}
        />
        <Button
          type="submit"
          variant="primary"
          icon="search"
          disabled={!questionInput.trim() || queryingAssistant}
        >
          {queryingAssistant ? "Querying..." : "Ask Assistant"}
        </Button>
      </form>
    </div>
  );
}
