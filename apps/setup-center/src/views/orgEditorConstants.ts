/**
 * Shared constants, types, and utility functions for OrgEditorView and its sub-panels.
 * Extracted to eliminate duplication and ensure single-source-of-truth for labels/colors.
 */

// ── Time helpers (always show local timezone) ──

export function fmtTime(v: string | number | undefined | null): string {
  if (!v) return "";
  const d = new Date(typeof v === "number" ? v : v);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtDateTime(v: string | number | undefined | null): string {
  if (!v) return "";
  const d = new Date(typeof v === "number" ? v : v);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtShortDate(v: string | number | undefined | null): string {
  if (!v) return "";
  const d = new Date(typeof v === "number" ? v : v);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function stripMd(s: string): string {
  return s
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/_(.+?)_/g, "$1")
    .replace(/~~(.+?)~~/g, "$1")
    .replace(/`(.+?)`/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\n+/g, " ")
    .trim();
}

// ── Label & color maps ──

export const TASK_STATUS_LABELS: Record<string, string> = {
  todo: "Todo",
  in_progress: "In Progress",
  delivered: "Delivered",
  rejected: "Rejected",
  accepted: "Accepted",
  cancelled: "Cancelled",
  blocked: "Blocked",
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  node_status_change: "Node status change",
  llm_usage: "Model call stats",
  task_completed: "Task completed",
  task_assigned: "Task assigned",
  task_delivered: "Task delivered",
  task_accepted: "Task accepted",
  task_rejected: "Task rejected",
  task_failed: "Task failed",
  node_activated: "Node activated",
  node_deactivated: "Node deactivated",
  node_dismissed: "Node dismissed",
  node_frozen: "Node frozen",
  node_unfrozen: "Node unfrozen",
  org_started: "Organization started",
  org_stopped: "Organization stopped",
  org_paused: "Organization paused",
  org_resumed: "Organization resumed",
  org_reset: "Organization reset",
  schedule_assigned: "Scheduled task assigned",
  schedule_completed: "Scheduled task completed",
  schedule_triggered: "Scheduled task triggered",
  schedule_requested: "Scheduled task requested",
  broadcast: "Broadcast message",
  auto_clone_created: "Auto clone created",
  clones_reclaimed: "Clones reclaimed",
  auto_kickoff: "Auto kickoff",
  scaling_requested: "Scale-up requested",
  scaling_approved: "Scale-up approved",
  scaling_rejected: "Scale-up rejected",
  tools_granted: "Tools granted",
  tools_requested: "Tools requested",
  tools_revoked: "Tools revoked",
  user_command: "User command",
  watchdog_recovery: "Watchdog recovery",
  heartbeat_triggered: "Heartbeat triggered",
  heartbeat_decision: "Heartbeat decision",
  standup_started: "Standup started",
  standup_completed: "Standup completed",
  meeting_completed: "Meeting completed",
  conflict_detected: "Conflict detected",
  policy_proposed: "Policy proposed",
  approval_resolved: "Approval resolved",
  tool_call_start: "Tool call",
  tool_call_end: "Tool call completed",
  plan_created: "Plan created",
  plan_completed: "Plan completed",
  plan_cancelled: "Plan cancelled",
  plan_step_updated: "Plan step updated",
  iteration_start: "Iteration started",
  agent_handoff: "Agent handoff",
  ask_user: "Ask user",
  done: "Done",
  error: "Error",
};

export const MSG_TYPE_LABELS: Record<string, string> = {
  task_assign: "Task assignment",
  task_result: "Task result",
  task_delivered: "Task delivered",
  task_accepted: "Task accepted",
  task_rejected: "Task rejected",
  report: "Work report",
  question: "Question",
  answer: "Answer",
  escalate: "Escalation",
  escalation: "Escalation",
  broadcast: "Broadcast",
  dept_broadcast: "Department broadcast",
  feedback: "Feedback",
  handshake: "Handshake",
  deliverable: "Deliverable",
};

export const DATA_KEY_LABELS: Record<string, string> = {
  from: "From",
  to: "To",
  reason: "Reason",
  node_id: "Node",
  calls: "Call count",
  tokens_in: "Input tokens",
  tokens_out: "Output tokens",
  model: "Model",
  result_preview: "Result preview",
  deliverable_preview: "Deliverable preview",
  error: "Error",
  content: "Content",
  task: "Task",
  title: "Title",
  role: "Role",
  name: "Name",
  tools: "Tools",
  source: "Source",
  target: "Target",
  scope: "Scope",
  prompt: "Prompt",
  schedule_id: "Schedule ID",
  chain_id: "Chain ID",
  clone_id: "Clone ID",
  approval_id: "Approval ID",
  request_id: "Request ID",
  new_node_id: "New node ID",
  superior: "Superior",
  participants: "Participants",
  pending_count: "Pending count",
  node_count: "Node count",
  rounds: "Rounds",
  cycle: "Cycle",
  decision: "Decision",
  stuck_secs: "Stuck time (s)",
  threshold: "Threshold",
  dismissed: "Dismissed",
  type: "Type",
  topic: "Topic",
  filename: "File name",
  core_business_len: "Core business count",
  tool: "Tool",
  args: "Arguments",
  result: "Result",
  duration_ms: "Duration (ms)",
  status: "Status",
  question: "Question",
  message: "Message",
};

export const DATA_VALUE_LABELS: Record<string, string> = {
  idle: "Idle",
  busy: "Running",
  waiting: "Waiting",
  error: "Error",
  offline: "Offline",
  frozen: "Frozen",
  task_started: "Task started",
  task_completed: "Task completed",
  task_failed: "Task failed",
  task_assigned: "Task assigned",
  task_delivered: "Task delivered",
  task_accepted: "Task accepted",
  task_rejected: "Task rejected",
  org_stopped: "Organization stopped",
  org_reset: "Organization reset",
  org_paused: "Organization paused",
  org_resumed: "Organization resumed",
  restart_cleanup: "Restart cleanup",
  watchdog_recovery: "Watchdog recovery",
  health_check_recovery: "Health check recovery",
  org_quota_pause: "Quota paused",
  quota_exhausted: "Quota exhausted",
  auto_recover_before_activate: "Auto-resume before activation",
  unfreeze: "Unfreeze",
  stuck_busy: "Sustained busy",
  error_not_recovering: "Error not recovering",
  idle_no_progress: "Idle, no progress",
  root_busy: "Root node busy",
  root_has_task: "Root node has task",
  skip: "Skip",
  activate: "Activate",
  do_nothing: "No action",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  completed: "Completed",
  in_progress: "In Progress",
  delivered: "Delivered",
  accepted: "Accepted",
  blocked: "Blocked",
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
  attention: "Needs attention",
};

export const STATUS_LABELS: Record<string, string> = {
  idle: "Idle",
  busy: "Running",
  waiting: "Waiting",
  error: "Error",
  offline: "Offline",
  frozen: "Frozen",
};

export const STATUS_COLORS: Record<string, string> = {
  idle: "var(--ok)",
  busy: "var(--primary)",
  waiting: "#f59e0b",
  error: "var(--danger)",
  offline: "var(--muted)",
  frozen: "#93c5fd",
  dormant: "var(--muted)",
  active: "var(--ok)",
  running: "var(--primary)",
  paused: "#f59e0b",
  archived: "var(--muted)",
};

export const ORG_STATUS_LABELS: Record<string, string> = {
  dormant: "Sleeping",
  active: "Running",
  running: "Running",
  paused: "Paused",
  archived: "Archived",
};

export const EDGE_COLORS: Record<string, string> = {
  hierarchy: "var(--primary)",
  collaborate: "var(--ok)",
  escalate: "var(--danger)",
  consult: "#a78bfa",
};

// TODO(i18n): department names come from backend in Chinese; translate at display
// time when backend org schema settles. Keys stay as data-contract strings.
export const DEPT_COLORS: Record<string, string> = {
  "管理层": "#6366f1",
  "技术部": "#0ea5e9",
  "产品部": "#8b5cf6",
  "市场部": "#f97316",
  "行政支持": "#64748b",
  "工程": "#0ea5e9",
  "前端组": "#06b6d4",
  "后端组": "#14b8a6",
  "编辑部": "#f97316",
  "创作组": "#ec4899",
  "运营组": "#84cc16",
};

export function getDeptColor(dept: string): string {
  return DEPT_COLORS[dept] || "#6b7280";
}

/** Unified blackboard entry type colors — single source of truth. */
export const BB_TYPE_COLORS: Record<string, string> = {
  fact: "#3b82f6",
  decision: "#f59e0b",
  lesson: "#10b981",
  progress: "#8b5cf6",
  todo: "#ef4444",
  resource: "#0891b2",
};

/** Unified blackboard entry type labels — single source of truth. */
export const BB_TYPE_LABELS: Record<string, string> = {
  fact: "Fact",
  decision: "Decision",
  lesson: "Experience",
  progress: "Progress",
  todo: "Todo",
  resource: "Output",
};

export function translateDataValue(
  key: string, value: unknown,
  nodeNameMap?: Map<string, string>,
): string {
  const s = String(value);
  if ((key === "node_id" || key === "new_node_id") && nodeNameMap?.has(s)) {
    return nodeNameMap.get(s)!;
  }
  return DATA_VALUE_LABELS[s] || s;
}

// ── Types ──

export interface OrgNodeData {
  id: string;
  role_title: string;
  role_goal: string;
  role_backstory: string;
  agent_source: string;
  agent_profile_id: string | null;
  position: { x: number; y: number };
  level: number;
  department: string;
  custom_prompt: string;
  identity_dir: string | null;
  mcp_servers: string[];
  skills: string[];
  skills_mode: string;
  preferred_endpoint: string | null;
  max_concurrent_tasks: number;
  timeout_s: number;
  can_delegate: boolean;
  can_escalate: boolean;
  can_request_scaling: boolean;
  is_clone: boolean;
  clone_source: string | null;
  external_tools: string[];
  enable_file_tools?: boolean;
  ephemeral: boolean;
  avatar: string | null;
  frozen_by: string | null;
  frozen_reason: string | null;
  frozen_at: string | null;
  status: string;
  auto_clone_enabled?: boolean;
  auto_clone_threshold?: number;
  auto_clone_max?: number;
  current_task?: string;
}

export interface OrgEdgeData {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  label: string;
  bidirectional: boolean;
  priority: number;
  bandwidth_limit: number;
}

export interface OrgSummary {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: string;
  node_count: number;
  edge_count: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface UserPersona {
  title: string;
  display_name: string;
  description: string;
}

export interface OrgFull {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: string;
  nodes: OrgNodeData[];
  edges: OrgEdgeData[];
  user_persona?: UserPersona;
  [key: string]: any;
}

export interface TemplateSummary {
  id: string;
  name: string;
  description: string;
  icon: string;
  node_count: number;
  tags: string[];
}
