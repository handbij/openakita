/**
 * Project management kanban board — column-based task view.
 * Supports temporary and permanent projects, task CRUD, and status transitions.
 */
import { useState, useEffect, useCallback } from "react";
import { safeFetch } from "../providers";
import { OrgAvatar } from "./OrgAvatars";

interface ProjectTask {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: string;
  assignee_node_id: string | null;
  priority: number;
  progress_pct: number;
  created_at: string;
  started_at: string | null;
  delivered_at: string | null;
  completed_at: string | null;
}

interface Project {
  id: string;
  org_id: string;
  name: string;
  description: string;
  project_type: string;
  status: string;
  owner_node_id: string | null;
  tasks: ProjectTask[];
  created_at: string;
  updated_at: string;
}

interface OrgProjectBoardProps {
  orgId: string;
  apiBaseUrl: string;
  nodes?: Array<{ id: string; role_title?: string; avatar?: string | null }>;
  compact?: boolean;
}

const COLUMNS = [
  { key: "todo", label: "待办", color: "#64748b" },
  { key: "in_progress", label: "进行中", color: "#3b82f6" },
  { key: "delivered", label: "已交付", color: "#8b5cf6" },
  { key: "rejected", label: "已打回", color: "#f97316" },
  { key: "accepted", label: "已验收", color: "#22c55e" },
  { key: "blocked", label: "已阻塞", color: "#ef4444" },
];

const PROJECT_TYPE_LABEL: Record<string, string> = {
  temporary: "临时项目",
  permanent: "持续项目",
};

const PROJECT_STATUS_LABEL: Record<string, string> = {
  planning: "规划中",
  active: "进行中",
  paused: "暂停",
  completed: "已完成",
  archived: "已归档",
};

export function OrgProjectBoard({ orgId, apiBaseUrl, nodes = [], compact = false }: OrgProjectBoardProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showNewProject, setShowNewProject] = useState(false);
  const [showNewTask, setShowNewTask] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectType, setNewProjectType] = useState("temporary");
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskAssignee, setNewTaskAssignee] = useState("");
  const [dispatchingTaskId, setDispatchingTaskId] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<any>(null);
  const [taskDetail, setTaskDetail] = useState<any>(null);
  const [taskTimeline, setTaskTimeline] = useState<any[]>([]);
  const [taskDetailLoading, setTaskDetailLoading] = useState(false);
  const [subtasksExpanded, setSubtasksExpanded] = useState(true);

  const nodeMap = new Map(nodes.map(n => [n.id, n]));

  const fetchTaskDetail = useCallback(async (taskId: string) => {
    setTaskDetailLoading(true);
    setTaskDetail(null);
    setTaskTimeline([]);
    try {
      const [detailRes, timelineRes] = await Promise.all([
        safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/tasks/${taskId}`),
        safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/tasks/${taskId}/timeline`),
      ]);
      if (detailRes.ok) setTaskDetail(await detailRes.json());
      if (timelineRes.ok) {
        const tl = await timelineRes.json();
        setTaskTimeline(tl.timeline || []);
      }
    } catch { /* ignore */ }
    setTaskDetailLoading(false);
  }, [orgId, apiBaseUrl]);

  const openTaskDetail = useCallback((task: ProjectTask) => {
    setSelectedTask(task);
    fetchTaskDetail(task.id);
  }, [fetchTaskDetail]);

  const closeTaskDetail = useCallback(() => {
    setSelectedTask(null);
    setTaskDetail(null);
    setTaskTimeline([]);
  }, []);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        if (!selectedProjectId && data.length > 0) {
          setSelectedProjectId(data[0].id);
        }
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [orgId, apiBaseUrl, selectedProjectId]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const createProject = async () => {
    if (!newProjectName.trim()) return;
    try {
      await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newProjectName, project_type: newProjectType, status: "active" }),
      });
      setNewProjectName("");
      setShowNewProject(false);
      fetchProjects();
    } catch { /* ignore */ }
  };

  const createTask = async () => {
    if (!newTaskTitle.trim() || !selectedProjectId) return;
    try {
      await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects/${selectedProjectId}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTaskTitle,
          assignee_node_id: newTaskAssignee || null,
          status: "todo",
        }),
      });
      setNewTaskTitle("");
      setNewTaskAssignee("");
      setShowNewTask(false);
      fetchProjects();
    } catch { /* ignore */ }
  };

  const updateTaskStatus = async (projectId: string, taskId: string, newStatus: string) => {
    try {
      await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects/${projectId}/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      fetchProjects();
    } catch { /* ignore */ }
  };

  const deleteTask = async (projectId: string, taskId: string) => {
    try {
      await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects/${projectId}/tasks/${taskId}`, {
        method: "DELETE",
      });
      fetchProjects();
    } catch { /* ignore */ }
  };

  const dispatchTask = async (projectId: string, taskId: string) => {
    setDispatchingTaskId(taskId);
    try {
      const res = await safeFetch(`${apiBaseUrl}/api/orgs/${orgId}/projects/${projectId}/tasks/${taskId}/dispatch`, {
        method: "POST",
      });
      if (res.ok) fetchProjects();
    } catch { /* ignore */ }
    finally { setDispatchingTaskId(null); }
  };

  const selectedProject = projects.find(p => p.id === selectedProjectId);
  const tasks = selectedProject?.tasks || [];

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--muted)" }}>
        加载中...
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg-app)", position: "relative" }}>
      {/* Project tabs */}
      <div style={{
        display: "flex", alignItems: "center", gap: compact ? 4 : 6,
        padding: compact ? "4px 8px" : "8px 12px", borderBottom: "1px solid var(--line)",
        flexShrink: 0, overflowX: "auto", flexWrap: "nowrap",
      }}>
        {projects.map(p => (
          <button
            key={p.id}
            onClick={() => setSelectedProjectId(p.id)}
            style={{
              padding: compact ? "2px 8px" : "5px 12px", borderRadius: 6, border: "1px solid var(--line)",
              background: p.id === selectedProjectId ? "var(--accent)" : "var(--bg-subtle, var(--bg-card))",
              color: p.id === selectedProjectId ? "#fff" : "var(--text)",
              cursor: "pointer", fontSize: compact ? 11 : 12, fontWeight: p.id === selectedProjectId ? 600 : 400,
              whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 4,
            }}
          >
            {p.name}
            {!compact && (
            <span style={{
              fontSize: 9, padding: "1px 4px", borderRadius: 3,
              background: p.id === selectedProjectId ? "rgba(255,255,255,0.2)" : "var(--bg-app)",
              color: p.id === selectedProjectId ? "#fff" : "var(--muted)",
            }}>
              {PROJECT_TYPE_LABEL[p.project_type] || p.project_type}
            </span>
            )}
          </button>
        ))}
        <button
          onClick={() => setShowNewProject(true)}
          style={{
            padding: compact ? "2px 8px" : "5px 12px", borderRadius: 6, border: "1px dashed var(--line)",
            background: "transparent", color: "var(--muted)", cursor: "pointer", fontSize: compact ? 11 : 12,
          }}
        >
          + 新项目
        </button>
        {selectedProject && (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", flexShrink: 0 }}>
            {PROJECT_STATUS_LABEL[selectedProject.status] || selectedProject.status}
            &nbsp;&middot;&nbsp;
            {selectedProject.tasks.length} 个任务
          </span>
        )}
      </div>

      {/* New project form */}
      {showNewProject && (
        <div style={{
          padding: "8px 12px", borderBottom: "1px solid var(--line)",
          display: "flex", gap: 8, alignItems: "center", flexShrink: 0,
          background: "var(--bg-subtle, var(--bg-card))",
        }}>
          <input
            placeholder="项目名称"
            value={newProjectName}
            onChange={e => setNewProjectName(e.target.value)}
            style={{
              flex: 1, border: "1px solid var(--line)", borderRadius: 4,
              padding: "4px 8px", fontSize: 12, background: "var(--bg-input, var(--bg-app))",
              color: "var(--text)", outline: "none",
            }}
            onKeyDown={e => e.key === "Enter" && createProject()}
            autoFocus
          />
          <select
            value={newProjectType}
            onChange={e => setNewProjectType(e.target.value)}
            style={{
              border: "1px solid var(--line)", borderRadius: 4, padding: "4px 8px",
              fontSize: 12, background: "var(--bg-input, var(--bg-app))", color: "var(--text)",
            }}
          >
            <option value="temporary">临时项目</option>
            <option value="permanent">持续项目</option>
          </select>
          <button
            onClick={createProject}
            style={{
              padding: "4px 12px", borderRadius: 4, border: "none",
              background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: 12,
            }}
          >
            创建
          </button>
          <button
            onClick={() => setShowNewProject(false)}
            style={{
              padding: "4px 8px", borderRadius: 4, border: "none",
              background: "transparent", color: "var(--muted)", cursor: "pointer", fontSize: 12,
            }}
          >
            取消
          </button>
        </div>
      )}

      {/* Kanban columns */}
      {selectedProject ? (
        <div style={{
          flex: 1, display: "flex", gap: 8, padding: 12,
          overflowX: "auto", overflowY: "hidden",
        }}>
          {COLUMNS.map(col => {
            const colTasks = tasks.filter(t => t.status === col.key);
            return (
              <div key={col.key} style={{
                flex: "1 1 180px", minWidth: 180, maxWidth: 280,
                display: "flex", flexDirection: "column",
                background: "var(--bg-subtle, var(--bg-card))",
                borderRadius: 8, border: "1px solid var(--line)",
                overflow: "hidden",
              }}>
                {/* Column header */}
                <div style={{
                  padding: "8px 10px", display: "flex", alignItems: "center", gap: 6,
                  borderBottom: `2px solid ${col.color}`, flexShrink: 0,
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: "50%", background: col.color,
                  }} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                    {col.label}
                  </span>
                  <span style={{
                    fontSize: 10, color: "var(--muted)",
                    background: "var(--bg-app)", padding: "1px 5px", borderRadius: 8,
                  }}>
                    {colTasks.length}
                  </span>
                </div>

                {/* Tasks */}
                <div style={{ flex: 1, overflowY: "auto", padding: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                  {colTasks.map(task => {
                    const assignee = task.assignee_node_id ? nodeMap.get(task.assignee_node_id) : null;
                    return (
                      <div
                        key={task.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => openTaskDetail(task)}
                        onKeyDown={e => e.key === "Enter" && openTaskDetail(task)}
                        style={{
                          padding: "8px 10px", borderRadius: 6,
                          background: "var(--bg-app)", border: "1px solid var(--line)",
                          fontSize: 12, cursor: "pointer",
                        }}
                      >
                        <div style={{ fontWeight: 500, color: "var(--text)", marginBottom: 4 }}>
                          {task.title}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4 }}>
                          {assignee ? (
                            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <OrgAvatar avatarId={(assignee as any).avatar || null} size={16} />
                              <span style={{ fontSize: 10, color: "var(--muted)" }}>
                                {assignee.role_title || assignee.id}
                              </span>
                            </div>
                          ) : (
                            <span style={{ fontSize: 10, color: "var(--muted)" }}>未分配</span>
                          )}
                          {/* Quick status transitions */}
                          <div style={{ display: "flex", gap: 2 }} onClick={e => e.stopPropagation()}>
                            {col.key === "todo" && (
                              <>
                                <button
                                  onClick={() => dispatchTask(task.project_id, task.id)}
                                  disabled={dispatchingTaskId === task.id}
                                  style={{ ...miniBtn, color: "var(--primary)", fontWeight: 600 }}
                                  title="派发任务到组织"
                                >
                                  {dispatchingTaskId === task.id ? "…" : "派发"}
                                </button>
                                <button onClick={() => updateTaskStatus(task.project_id, task.id, "in_progress")}
                                  style={miniBtn} title="开始">▶</button>
                              </>
                            )}
                            {col.key === "in_progress" && (
                              <button onClick={() => updateTaskStatus(task.project_id, task.id, "delivered")}
                                style={miniBtn} title="交付">✓</button>
                            )}
                            {col.key === "delivered" && (
                              <>
                                <button onClick={() => updateTaskStatus(task.project_id, task.id, "accepted")}
                                  style={{ ...miniBtn, color: "#22c55e" }} title="验收">✓</button>
                                <button onClick={() => updateTaskStatus(task.project_id, task.id, "rejected")}
                                  style={{ ...miniBtn, color: "#ef4444" }} title="打回">✗</button>
                              </>
                            )}
                            {col.key === "rejected" && (
                              <button onClick={() => updateTaskStatus(task.project_id, task.id, "in_progress")}
                                style={miniBtn} title="重做">↻</button>
                            )}
                            {col.key === "blocked" && (
                              <button onClick={() => updateTaskStatus(task.project_id, task.id, "in_progress")}
                                style={miniBtn} title="恢复">↻</button>
                            )}
                            <button onClick={() => deleteTask(task.project_id, task.id)}
                              style={{ ...miniBtn, color: "var(--muted)" }} title="删除">×</button>
                          </div>
                        </div>
                        {task.progress_pct > 0 && task.progress_pct < 100 && (
                          <div style={{
                            marginTop: 4, height: 3, borderRadius: 2,
                            background: "var(--line)", overflow: "hidden",
                          }}>
                            <div style={{
                              height: "100%", borderRadius: 2,
                              background: col.color,
                              width: `${task.progress_pct}%`,
                            }} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{
          flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
          color: "var(--muted)", flexDirection: "column", gap: 12,
        }}>
          <span style={{ fontSize: 14 }}>暂无项目</span>
          <button
            onClick={() => setShowNewProject(true)}
            style={{
              padding: "6px 16px", borderRadius: 6, border: "none",
              background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: 13,
            }}
          >
            创建第一个项目
          </button>
        </div>
      )}

      {/* Add task button */}
      {selectedProject && (
        <div style={{
          padding: "6px 12px", borderTop: "1px solid var(--line)", flexShrink: 0,
          display: "flex", gap: 8, alignItems: "center",
        }}>
          {showNewTask ? (
            <>
              <input
                placeholder="任务标题"
                value={newTaskTitle}
                onChange={e => setNewTaskTitle(e.target.value)}
                style={{
                  flex: 1, border: "1px solid var(--line)", borderRadius: 4,
                  padding: "4px 8px", fontSize: 12, background: "var(--bg-input, var(--bg-app))",
                  color: "var(--text)", outline: "none",
                }}
                onKeyDown={e => e.key === "Enter" && createTask()}
                autoFocus
              />
              <select
                value={newTaskAssignee}
                onChange={e => setNewTaskAssignee(e.target.value)}
                style={{
                  border: "1px solid var(--line)", borderRadius: 4, padding: "4px 8px",
                  fontSize: 11, background: "var(--bg-input, var(--bg-app))", color: "var(--text)",
                  maxWidth: 120,
                }}
              >
                <option value="">未分配</option>
                {nodes.map(n => (
                  <option key={n.id} value={n.id}>{n.role_title || n.id}</option>
                ))}
              </select>
              <button onClick={createTask} style={{
                padding: "4px 12px", borderRadius: 4, border: "none",
                background: "var(--accent)", color: "#fff", cursor: "pointer", fontSize: 12,
              }}>
                添加
              </button>
              <button onClick={() => setShowNewTask(false)} style={{
                padding: "4px 8px", borderRadius: 4, border: "none",
                background: "transparent", color: "var(--muted)", cursor: "pointer", fontSize: 12,
              }}>
                取消
              </button>
            </>
          ) : (
            <button onClick={() => setShowNewTask(true)} style={{
              padding: "4px 12px", borderRadius: 6, border: "1px dashed var(--line)",
              background: "transparent", color: "var(--muted)", cursor: "pointer", fontSize: 12,
            }}>
              + 添加任务
            </button>
          )}
        </div>
      )}

      {/* Task Detail Panel */}
      {selectedTask && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "stretch",
            background: "rgba(0,0,0,0.3)",
          }}
          onClick={closeTaskDetail}
        >
          <div
            style={{
              width: Math.min(420, "100%" as any),
              maxWidth: "100%",
              marginLeft: "auto",
              background: "var(--bg-app)",
              borderLeft: "1px solid var(--line)",
              boxShadow: "-4px 0 16px rgba(0,0,0,0.15)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{
              padding: "12px 14px",
              borderBottom: "1px solid var(--line)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexShrink: 0,
            }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>任务详情</span>
              <button
                onClick={closeTaskDetail}
                style={{
                  padding: "4px 8px",
                  border: "none",
                  background: "transparent",
                  color: "var(--muted)",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                关闭 ×
              </button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
              {taskDetailLoading ? (
                <div style={{ color: "var(--muted)", fontSize: 12, padding: 24 }}>加载中...</div>
              ) : taskDetail ? (
                <TaskDetailContent
                  task={taskDetail}
                  timeline={taskTimeline}
                  nodeMap={nodeMap}
                  subtasksExpanded={subtasksExpanded}
                  setSubtasksExpanded={setSubtasksExpanded}
                  onAncestorClick={(t: any) => { setSelectedTask(t); fetchTaskDetail(t.id); }}
                  statusLabel={(s: string) => COLUMNS.find(c => c.key === s)?.label || s}
                />
              ) : (
                <div style={{ color: "var(--muted)", fontSize: 12, padding: 24 }}>
                  无法加载任务详情
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TaskDetailContent({
  task,
  timeline,
  nodeMap,
  subtasksExpanded,
  setSubtasksExpanded,
  onAncestorClick,
  statusLabel,
}: {
  task: any;
  timeline: any[];
  nodeMap: Map<string, { id: string; role_title?: string; avatar?: string | null }>;
  subtasksExpanded: boolean;
  setSubtasksExpanded: (v: boolean) => void;
  onAncestorClick: (t: any) => void;
  statusLabel: (s: string) => string;
}) {
  const assignee = task.assignee_node_id ? nodeMap.get(task.assignee_node_id) : null;
  const delegatedBy = task.delegated_by ? nodeMap.get(task.delegated_by) : null;
  const fmt = (s: string | null | undefined) => s ? new Date(s).toLocaleString("zh-CN") : "-";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 12 }}>
      {/* Breadcrumb */}
      {(task.ancestors?.length ?? 0) > 0 && (
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          {(task.ancestors || []).map((a: any, i: number) => (
            <span key={a.id}>
              {i > 0 && " / "}
              <button
                type="button"
                onClick={() => onAncestorClick(a)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--primary)",
                  cursor: "pointer",
                  padding: 0,
                  textDecoration: "underline",
                }}
              >
                {a.title || a.id}
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Meta */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 10, color: "var(--muted)" }}>ID: {task.id}</span>
        <span style={{
          fontSize: 10,
          padding: "2px 6px",
          borderRadius: 4,
          background: "var(--bg-subtle, var(--bg-card))",
          color: "var(--text)",
        }}>
          {statusLabel(task.status)}
        </span>
      </div>

      <div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{task.title}</div>
        {task.description && (
          <div style={{ color: "var(--muted)", fontSize: 11, whiteSpace: "pre-wrap" }}>
            {task.description}
          </div>
        )}
      </div>

      {/* Progress */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
          <span>进度</span>
          <span>{task.progress_pct ?? 0}%</span>
        </div>
        <div style={{
          height: 6,
          borderRadius: 3,
          background: "var(--line)",
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            borderRadius: 3,
            background: "var(--accent)",
            width: `${Math.min(100, task.progress_pct ?? 0)}%`,
          }} />
        </div>
      </div>

      {/* Assignee / Delegated by */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
        {assignee && (
          <div>
            <span style={{ color: "var(--muted)" }}>执行人: </span>
            <span>{assignee.role_title || assignee.id}</span>
          </div>
        )}
        {delegatedBy && (
          <div>
            <span style={{ color: "var(--muted)" }}>委派者: </span>
            <span>{delegatedBy.role_title || delegatedBy.id}</span>
          </div>
        )}
        <div>
          <span style={{ color: "var(--muted)" }}>创建时间: </span>
          <span>{fmt(task.created_at)}</span>
        </div>
      </div>

      {/* Plan steps */}
      {(task.plan_steps?.length ?? 0) > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>计划步骤</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {(task.plan_steps || []).map((s: any, i: number) => {
              const st = s.status || "pending";
              const icon = st === "completed" ? "✓" : st === "in_progress" ? "→" : "○";
              const color = st === "completed" ? "#22c55e" : st === "in_progress" ? "#3b82f6" : "var(--muted)";
              return (
                <div key={s.id || i} style={{ display: "flex", gap: 6, alignItems: "flex-start", fontSize: 11 }}>
                  <span style={{ color, fontWeight: 600, flexShrink: 0 }}>{icon}</span>
                  <span style={{ color: "var(--text)" }}>{s.description || s.title || `步骤 ${i + 1}`}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sub-tasks */}
      {(task.subtasks?.length ?? 0) > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setSubtasksExpanded(!subtasksExpanded)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 6,
              color: "var(--text)",
              padding: 0,
            }}
          >
            {subtasksExpanded ? "▼" : "▶"} 子任务 ({task.subtasks.length})
          </button>
          {subtasksExpanded && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {(task.subtasks || []).map((st: any) => (
                <div
                  key={st.id}
                  style={{
                    padding: 8,
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--bg-subtle, var(--bg-card))",
                  }}
                >
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>{st.title}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 10 }}>
                    <span style={{
                      padding: "1px 5px",
                      borderRadius: 3,
                      background: "var(--bg-app)",
                      color: "var(--muted)",
                    }}>
                      {statusLabel(st.status)}
                    </span>
                    <span style={{ color: "var(--muted)" }}>{(st.progress_pct ?? 0)}%</span>
                  </div>
                  {(st.progress_pct ?? 0) > 0 && (st.progress_pct ?? 0) < 100 && (
                    <div style={{
                      marginTop: 4,
                      height: 3,
                      borderRadius: 2,
                      background: "var(--line)",
                      overflow: "hidden",
                    }}>
                      <div style={{
                        height: "100%",
                        borderRadius: 2,
                        background: "var(--accent)",
                        width: `${st.progress_pct}%`,
                      }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      <div>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>执行时间线</div>
        {timeline.length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--muted)" }}>暂无事件</div>
        ) : (
          <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            {timeline.map((ev: any, i: number) => (
              <div
                key={i}
                style={{
                  padding: "4px 8px",
                  borderRadius: 4,
                  background: "var(--bg-subtle, var(--bg-card))",
                  fontSize: 11,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 500 }}>{ev.event || "event"}</span>
                  <span style={{ color: "var(--muted)", fontSize: 10 }}>{ev.ts ? new Date(ev.ts).toLocaleString("zh-CN") : ""}</span>
                </div>
                {ev.actor && <div style={{ fontSize: 10, color: "var(--muted)" }}>by {ev.actor}</div>}
                {ev.detail && <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>{String(ev.detail).slice(0, 80)}{String(ev.detail).length > 80 ? "…" : ""}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const miniBtn: React.CSSProperties = {
  padding: "1px 4px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  fontSize: 11,
  color: "var(--text)",
  borderRadius: 3,
  lineHeight: 1,
};
