/**
 * Organization Blackboard Panel — standalone second-layer drawer.
 * Manages its own data fetching, scope filtering, and WebSocket refresh.
 */
import { useState, useEffect, useCallback, useImperativeHandle, forwardRef, type ComponentType } from "react";
import { safeFetch } from "../providers";
import type { Node } from "@xyflow/react";
import { fmtShortDate, BB_TYPE_COLORS, BB_TYPE_LABELS } from "../views/orgEditorConstants";

type MdModules = {
  ReactMarkdown: ComponentType<{ children: string; remarkPlugins?: any[] }>;
  remarkGfm: any;
} | null;

export interface OrgBlackboardPanelProps {
  orgId: string;
  apiBaseUrl: string;
  nodes: Node[];
  mdModules: MdModules;
}

export interface OrgBlackboardPanelHandle {
  refresh: () => void;
}

export const OrgBlackboardPanel = forwardRef<OrgBlackboardPanelHandle, OrgBlackboardPanelProps>(
  function OrgBlackboardPanel({ orgId, apiBaseUrl, nodes, mdModules }, ref) {
    const [entries, setEntries] = useState<any[]>([]);
    const [scope, setScope] = useState<"all" | "org" | "department" | "node">("all");
    const [loading, setLoading] = useState(false);

    const fetchData = useCallback(async (s?: string) => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: "100" });
        if (s && s !== "all") params.set("scope", s);
        const res = await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/memory?${params}`);
        const data = await res.json();
        setEntries(data || []);
      } catch {
        setEntries([]);
      } finally {
        setLoading(false);
      }
    }, [apiBaseUrl, orgId]);

    useEffect(() => {
      fetchData(scope);
    }, [orgId, scope, fetchData]);

    useImperativeHandle(ref, () => ({
      refresh: () => fetchData(scope),
    }), [fetchData, scope]);

    const resolveNodeName = (id: string) => {
      if (!id) return "";
      const nd = nodes.find(n => n.id === id);
      return (nd?.data as any)?.role_title || id;
    };

    const handleDelete = async (entryId: string) => {
      try {
        await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/memory/${entryId}`, { method: "DELETE" });
        setEntries(prev => prev.filter(e => e.id !== entryId));
      } catch { /* ignore */ }
    };

    const SCOPES = [
      { key: "all" as const, label: "全部" },
      { key: "org" as const, label: "组织级" },
      { key: "department" as const, label: "部门级" },
      { key: "node" as const, label: "节点级" },
    ];

    return (
      <div
        style={{
          width: 380, flexShrink: 0,
          borderLeft: "1px solid var(--line)",
          overflowY: "auto", scrollbarGutter: "stable",
          background: "var(--bg-app)",
          animation: "org-panel-in 0.3s cubic-bezier(0.4,0,0.2,1) 0s both",
        }}
      >
        <div style={{ padding: "12px 14px 8px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>组织黑板</div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 2 }}>
              {SCOPES.map((s) => (
                <button
                  key={s.key}
                  className="btnSmall"
                  style={{
                    fontSize: 11, padding: "2px 7px",
                    fontWeight: scope === s.key ? 600 : 400,
                    background: scope === s.key ? "var(--primary)" : "transparent",
                    color: scope === s.key ? "#fff" : "var(--muted)",
                    borderRadius: 4,
                  }}
                  onClick={() => setScope(s.key)}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <button
              className="btnSmall"
              style={{ fontSize: 11, padding: "2px 8px" }}
              onClick={() => fetchData(scope)}
              disabled={loading}
            >
              {loading ? "..." : "刷新"}
            </button>
          </div>
        </div>

        <div style={{ padding: 12 }}>
          {entries.length === 0 ? (
            <div style={{
              fontSize: 12, color: "var(--muted)", padding: "32px 16px",
              textAlign: "center", border: "1px dashed var(--line)", borderRadius: 8,
            }}>
              {loading ? "加载中..." : "暂无黑板记录"}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {entries.map((entry: any) => {
                const scopeLabel = entry.scope === "org" ? "组织" : entry.scope === "department" ? entry.scope_owner : resolveNodeName(entry.source_node) || "节点";
                return (
                  <div
                    key={entry.id}
                    style={{
                      border: "1px solid var(--line)", borderRadius: 6,
                      padding: "8px 10px", background: "var(--card-bg)",
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
                        <span style={{
                          fontSize: 11, padding: "1px 6px", borderRadius: 3,
                          background: (BB_TYPE_COLORS[entry.memory_type] || "#6b7280") + "20",
                          color: BB_TYPE_COLORS[entry.memory_type] || "var(--muted)",
                          fontWeight: 600,
                        }}>
                          {BB_TYPE_LABELS[entry.memory_type] || entry.memory_type}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>{scopeLabel}</span>
                      </div>
                      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>{fmtShortDate(entry.created_at)}</span>
                        <button
                          className="btnSmall"
                          style={{ fontSize: 11, padding: "0 4px", color: "var(--muted)" }}
                          title="删除此条"
                          onClick={() => handleDelete(entry.id)}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    <div className="bb-entry-content">
                      {mdModules ? (
                        <mdModules.ReactMarkdown remarkPlugins={[mdModules.remarkGfm]}>
                          {entry.content}
                        </mdModules.ReactMarkdown>
                      ) : (
                        <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{entry.content}</pre>
                      )}
                    </div>
                    {Array.isArray(entry.tags) && entry.tags.length > 0 && (
                      <div style={{ marginTop: 4, display: "flex", gap: 3, flexWrap: "wrap" }}>
                        {entry.tags.map((t: string) => (
                          <span key={t} style={{
                            fontSize: 11, padding: "0 5px", borderRadius: 3,
                            background: "var(--hover-bg, rgba(100,100,100,0.1))", color: "var(--muted)",
                          }}>#{t}</span>
                        ))}
                      </div>
                    )}
                    {entry.source_node && (
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
                        来自 {resolveNodeName(entry.source_node)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }
);
