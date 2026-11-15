"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Icon } from "./AppShell";
import { useAuth } from "../context/AuthContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export interface NotificationItem {
  id: string;
  recipient_user_id: string;
  organization_id: string;
  document_id?: string | null;
  notification_type: string;
  title: string;
  body?: string | null;
  is_read: boolean;
  created_at: string;
}

export function NotificationCenter({
  inline = false,
}: {
  inline?: boolean;
}) {
  const { fetchWithAuth, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/notifications?limit=25`);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.items || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, isAuthenticated]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadNotifications();
    }, 0);
    const interval = setInterval(() => {
      loadNotifications();
    }, 30000); // Polling every 30s
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [loadNotifications]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const markAsRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetchWithAuth(`${API_URL}/api/notifications/${id}/read`, {
        method: "PATCH",
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch {
      // Ignored
    }
  };

  const markAllAsRead = async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api/notifications/read-all`, {
        method: "POST",
      });
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        setUnreadCount(0);
      }
    } catch {
      // Ignored
    }
  };

  if (!isAuthenticated) return null;

  return (
    <div ref={containerRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        title="Notifications"
        aria-label="Notifications"
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          position: "relative",
          padding: "6px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: isOpen ? "var(--ink, #1f2328)" : "var(--muted, #666)",
          borderRadius: "4px",
        }}
      >
        <Icon name="alert" size={15} />
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "2px",
              right: "2px",
              background: "var(--red, #dc2626)",
              color: "white",
              fontSize: "9px",
              fontWeight: 700,
              padding: "1px 4px",
              borderRadius: "10px",
              lineHeight: 1,
              minWidth: "14px",
              textAlign: "center",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: inline ? "auto" : "100%",
            bottom: inline ? "100%" : "auto",
            right: 0,
            marginTop: inline ? 0 : "8px",
            marginBottom: inline ? "8px" : 0,
            width: "360px",
            maxHeight: "440px",
            background: "white",
            border: "1px solid var(--line2, #e0ddd5)",
            borderRadius: "8px",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            fontFamily: "var(--font-sans, system-ui)",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--line2, #e0ddd5)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "var(--side, #f8f7f4)",
            }}
          >
            <div>
              <b style={{ fontSize: "12px", color: "var(--ink, #1f2328)" }}>Notifications</b>
              {unreadCount > 0 && (
                <span style={{ fontSize: "10px", color: "var(--muted)", marginLeft: "6px" }}>
                  ({unreadCount} unread)
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllAsRead}
                style={{
                  background: "transparent",
                  border: "none",
                  fontSize: "11px",
                  color: "var(--sage, #4f6b5c)",
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List Content */}
          <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
            {loading && notifications.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", fontSize: "11px", color: "var(--muted)" }}>
                Loading notifications...
              </div>
            ) : error ? (
              <div style={{ padding: "16px", fontSize: "11px", color: "var(--red, #dc2626)", textAlign: "center" }}>
                {error}
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: "32px 16px", textAlign: "center", color: "var(--muted)" }}>
                <Icon name="check" size={20} />
                <p style={{ margin: "8px 0 0", fontSize: "12px" }}>All caught up!</p>
                <small style={{ fontSize: "10px" }}>No workflow notifications at this time.</small>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  style={{
                    padding: "10px 16px",
                    borderBottom: "1px solid var(--line2, #f0eee8)",
                    background: n.is_read ? "transparent" : "#faf8f5",
                    display: "flex",
                    gap: "10px",
                    alignItems: "flex-start",
                    transition: "background 0.2s",
                  }}
                >
                  <div
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: n.is_read ? "transparent" : "var(--amber, #b45309)",
                      marginTop: "6px",
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <b style={{ fontSize: "11px", color: "var(--ink)", display: "block" }}>
                        {n.title}
                      </b>
                      <span style={{ fontSize: "9px", color: "var(--muted)", flexShrink: 0, marginLeft: "8px" }}>
                        {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>

                    {n.body && (
                      <p style={{ margin: "3px 0 0", fontSize: "11px", color: "var(--muted)", lineHeight: 1.4 }}>
                        {n.body}
                      </p>
                    )}

                    <div style={{ display: "flex", gap: "10px", marginTop: "6px", alignItems: "center" }}>
                      {n.document_id && (
                        <Link
                          href={`/documents/${n.document_id}`}
                          onClick={() => setIsOpen(false)}
                          style={{
                            fontSize: "10px",
                            color: "var(--ink)",
                            textDecoration: "underline",
                            fontWeight: 500,
                          }}
                        >
                          View Document →
                        </Link>
                      )}

                      {!n.is_read && (
                        <button
                          type="button"
                          onClick={(e) => markAsRead(n.id, e)}
                          style={{
                            background: "transparent",
                            border: "none",
                            fontSize: "10px",
                            color: "var(--muted)",
                            cursor: "pointer",
                            padding: 0,
                          }}
                        >
                          Mark read
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
