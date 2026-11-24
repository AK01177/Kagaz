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
      if (rect.right - dropdownWidth < 12) {
        left = rect.left;
      } else {
        left = rect.right - dropdownWidth;
      }
    }

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

  const toggleOpen = () => {
    if (!isOpen) {
      const pos = calculatePosition();
      if (pos) {
        setDropdownPosition(pos);
      }
      loadNotifications();
    }
    setIsOpen((prev) => !prev);
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      loadNotifications();
    }, 0);
    const interval = setInterval(() => {
      loadNotifications();
    }, 30000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [loadNotifications]);

  useEffect(() => {
    if (!isOpen) return;

    function handleScrollOrResize() {
      updatePosition();
    }

    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [isOpen, updatePosition]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        const dialog = document.querySelector('[role="dialog"][aria-label="Notifications"]');
        if (dialog && !dialog.contains(event.target as Node)) {
          setIsOpen(false);
        }
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const markAllAsRead = async () => {
    try {
      const res = await fetchWithAuth(`/api/notifications/mark-read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => ({ ...n, is_read: true }))
        );
        setUnreadCount(0);
      }
    } catch {}
  };

  const markOneAsRead = async (notificationId: string) => {
    try {
      const res = await fetchWithAuth(`/api/notifications/${notificationId}/read`, {
        method: "PATCH",
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch {}
  };

  const formatRelativeTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return "just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString();
    } catch {
      return isoString;
    }
  };

  return (
    <div ref={containerRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        onClick={toggleOpen}
        title="Notifications"
        aria-label="Notifications"
        aria-expanded={isOpen}
        style={{
          background: isOpen ? "rgba(255, 255, 255, 0.12)" : "rgba(255, 255, 255, 0.05)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          cursor: "pointer",
          position: "relative",
          padding: "6px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: isOpen ? "#FFFFFF" : "#CBD5E1",
          borderRadius: "6px",
          transition: "all 0.15s ease",
        }}
      >
        <Icon name="alert" size={15} />
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              background: "var(--brand)",
              color: "#FFFFFF",
              fontSize: "10px",
              fontWeight: 700,
              padding: "1px 5px",
              borderRadius: "9999px",
              lineHeight: 1.2,
              minWidth: "16px",
              textAlign: "center",
              boxShadow: "0 0 8px rgba(79, 70, 229, 0.5)",
              animation: "pulseGlow 2.5s infinite ease-in-out",
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
            maxHeight: "min(460px, calc(100vh - 32px))",
            background: "#FFFFFF",
            border: "1px solid var(--line)",
            borderRadius: "12px",
            boxShadow: "var(--shadow-xl), 0 0 0 1px rgba(15, 23, 42, 0.05)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            animation: "scaleIn 0.2s var(--ease-spring)",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 18px",
              borderBottom: "1px solid var(--line)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "var(--surface-secondary)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <b style={{ fontSize: "13px", color: "var(--ink)" }}>Notifications</b>
              {unreadCount > 0 && (
                <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--brand)", background: "var(--brand-surface)", padding: "1px 6px", borderRadius: "9999px" }}>
                  {unreadCount} unread
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
                  color: "var(--brand)",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List Content */}
          <div style={{ overflowY: "auto", flex: 1, padding: "4px 0" }}>
            {loading && notifications.length === 0 ? (
              <div style={{ padding: "28px", textAlign: "center", fontSize: "12px", color: "var(--muted)" }}>
                Loading activity events...
              </div>
            ) : error ? (
              <div style={{ padding: "20px", textAlign: "center", fontSize: "12px", color: "var(--error)" }}>
                {error}
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: "36px 20px", textAlign: "center", color: "var(--muted)" }}>
                <span
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "50%",
                    background: "var(--success-bg)",
                    color: "var(--success)",
                    display: "grid",
                    placeItems: "center",
                    margin: "0 auto 10px",
                  }}
                >
                  <Icon name="check" size={18} />
                </span>
                <p style={{ margin: "0 0 2px", fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>All caught up</p>
                <small style={{ fontSize: "11px", color: "var(--secondary)" }}>No unread notifications for this workspace.</small>
              </div>
            ) : (
              notifications.map((item) => (
                <div
                  key={item.id}
                  onClick={() => !item.is_read && markOneAsRead(item.id)}
                  style={{
                    padding: "12px 18px",
                    borderBottom: "1px solid var(--border-subtle)",
                    background: item.is_read ? "transparent" : "var(--brand-surface)",
                    cursor: "pointer",
                    display: "flex",
                    gap: "12px",
                    alignItems: "flex-start",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = item.is_read ? "var(--surface-secondary)" : "var(--brand-tint)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = item.is_read ? "transparent" : "var(--brand-surface)";
                  }}
                >
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: item.is_read ? "transparent" : "var(--brand)",
                      marginTop: "5px",
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "baseline",
                        gap: "6px",
                      }}
                    >
                      <b
                        style={{
                          fontSize: "12px",
                          fontWeight: item.is_read ? 500 : 600,
                          color: "var(--ink)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {item.title}
                      </b>
                      <span
                        style={{
                          fontSize: "10px",
                          color: "var(--muted)",
                          flexShrink: 0,
                        }}
                      >
                        {formatRelativeTime(item.created_at)}
                      </span>
                    </div>
                    {item.body && (
                      <p
                        style={{
                          margin: "3px 0 0",
                          fontSize: "11px",
                          color: "var(--secondary)",
                          lineHeight: 1.4,
                        }}
                      >
                        {item.body}
                      </p>
                    )}
                    {item.document_id && (
                      <Link
                        href={`/workspace/documents/${item.document_id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsOpen(false);
                          if (!item.is_read) markOneAsRead(item.id);
                        }}
                        style={{
                          display: "inline-block",
                          marginTop: "6px",
                          fontSize: "11px",
                          color: "var(--brand)",
                          fontWeight: 600,
                          textDecoration: "none",
                        }}
                      >
                        Inspect Document →
                      </Link>
                    )}
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
