"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Icon } from "./AppShell";
import { useAuth } from "../context/AuthContext";


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
  align = "auto",
}: {
  inline?: boolean;
  align?: "left" | "right" | "auto";
}) {
  const { fetchWithAuth, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [dropdownPosition, setDropdownPosition] = useState<{
    top: number;
    left: number;
    width: number;
  }>({ top: 0, left: 0, width: 360 });

  const containerRef = useRef<HTMLDivElement>(null);

  const calculatePosition = useCallback(() => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const dropdownWidth = Math.min(360, window.innerWidth - 24);

    let left: number;
    if (align === "left") {
      left = rect.left;
    } else if (align === "right") {
      left = rect.right - dropdownWidth;
    } else {
      // Auto: if not enough space to the left of the button, align left
      if (rect.right - dropdownWidth < 12) {
        left = rect.left;
      } else {
        left = rect.right - dropdownWidth;
      }
    }

    // Clamp inside viewport with 12px gutter
    left = Math.max(12, Math.min(left, window.innerWidth - dropdownWidth - 12));
    const top = inline ? Math.max(12, rect.top - 448) : rect.bottom + 8;

    return { top, left, width: dropdownWidth };
  }, [align, inline]);

  const updatePosition = useCallback(() => {
    const pos = calculatePosition();
    if (pos) {
      setDropdownPosition(pos);
    }
  }, [calculatePosition]);

  const toggleOpen = () => {
    if (!isOpen) {
      const pos = calculatePosition();
      if (pos) {
        setDropdownPosition(pos);
      }
    }
    setIsOpen((prev) => !prev);
  };

  const loadNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`/api/notifications?limit=25`);
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
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      window.addEventListener("keydown", handleKeyDown);
      window.addEventListener("resize", updatePosition);
      window.addEventListener("scroll", updatePosition, true);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isOpen, updatePosition]);

  const markAsRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetchWithAuth(`/api/notifications/${id}/read`, {
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
      const res = await fetchWithAuth(`/api/notifications/read-all`, {
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
        onClick={toggleOpen}
        title="Notifications"
        aria-label="Notifications"
        aria-expanded={isOpen}
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
          role="dialog"
          aria-label="Notifications"
          style={{
            position: "fixed",
            top: `${dropdownPosition.top}px`,
            left: `${dropdownPosition.left}px`,
            width: `${dropdownPosition.width}px`,
            maxHeight: "min(440px, calc(100vh - 32px))",
            background: "white",
            border: "1px solid var(--line2, #e0ddd5)",
            borderRadius: "8px",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.05)",
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
                          href={`/workspace/documents/${n.document_id}`}
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
