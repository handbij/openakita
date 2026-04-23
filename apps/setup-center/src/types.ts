// ─── Shared types for Setup Center ───

export type PlatformInfo = {
  os: string;
  arch: string;
  homeDir: string;
  openakitaRootDir: string;
};

export type WorkspaceSummary = {
  id: string;
  name: string;
  path: string;
  isCurrent: boolean;
};

export type ProviderInfo = {
  name: string;
  slug: string;
  api_type: "openai" | "anthropic" | string;
  default_base_url: string;
  api_key_env_suggestion: string;
  supports_model_list: boolean;
  supports_capability_api: boolean;
  requires_api_key?: boolean;  // default true; false for local providers like Ollama
  is_local?: boolean;          // true for local providers (Ollama, LM Studio, etc.)
  coding_plan_base_url?: string;   // Coding Plan 专用 API 地址（存在则支持 coding plan）
  coding_plan_api_type?: string;   // Coding Plan 模式下的协议类型（不存在则与 api_type 相同）
  default_context_window?: number;
  default_max_tokens?: number;
  note?: string;                   // i18n key — 显示在服务商选择下方的提示信息
};

export type ListedModel = {
  id: string;
  name: string;
  capabilities: Record<string, boolean>;
};

export type EndpointDraft = {
  name: string;
  provider: string;
  api_type: string;
  base_url: string;
  api_key_env: string;
  model: string;
  priority: number;
  max_tokens: number;
  context_window: number;
  timeout: number;
  capabilities: string[];
  rpm_limit?: number;
  note?: string | null;
  pricing_tiers?: { max_input: number; input_price: number; output_price: number }[];
  enabled?: boolean;
};

export type PythonCandidate = {
  command: string[];
  versionText: string;
  isUsable: boolean;
};

export type BundledPythonInstallResult = {
  pythonCommand: string[];
  pythonPath: string;
  installDir: string;
  assetName: string;
  tag: string;
};

export type InstallSource = "pypi" | "github" | "local";

export type EnvMap = Record<string, string>;

export type StepId =
  | "welcome"
  | "workspace"
  | "python"
  | "install"
  | "llm"
  | "im"
  | "tools"
  | "agent"
  | "advanced"
  | "finish"
  | "quick-form"
  | "quick-setup"
  | "quick-finish";

export type Step = {
  id: StepId;
  title: string;
  desc: string;
};

export type ViewId = "wizard" | "status" | "chat" | "skills" | "im" | "onboarding" | "token_stats" | "mcp" | "scheduler" | "memory" | "dashboard" | "agent_manager" | "agent_store" | "skill_store" | "org_editor" | "pixel_office" | "identity" | "docs" | "security" | "plugins" | `plugin_app:${string}`;

export type PluginUIApp = {
  id: string;
  title: string;
  title_i18n?: Record<string, string>;
  icon_url?: string;
  sidebar_group: string;
  enabled: boolean;
  status?: string;
};

// ─── Health check types ───

export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown" | "disabled";

export type EndpointHealthResult = {
  name: string;
  status: HealthStatus;
  latencyMs: number | null;
  error: string | null;
  errorCategory: string | null;
  consecutiveFailures: number;
  cooldownRemaining: number;
  isExtendedCooldown: boolean;
  lastCheckedAt: string | null;
};

export type IMHealthResult = {
  channel: string;
  name: string;
  status: HealthStatus;
  error: string | null;
  lastCheckedAt: string | null;
};

export type EndpointSummary = {
  name: string;
  provider: string;
  apiType: string;
  baseUrl: string;
  model: string;
  keyEnv: string;
  keyPresent: boolean;
  enabled?: boolean;
  health?: EndpointHealthResult | null;
};

export type IMStatus = {
  k: string;
  name: string;
  enabled: boolean;
  ok: boolean;
  missing: string[];
  health?: IMHealthResult | null;
};

// ─── Chat types ───

export type ChatArtifact = {
  artifact_type: string;  // "image" | "file" | "voice" etc.
  file_url: string;       // relative URL for /api/files/...
  path: string;           // absolute local path
  name: string;
  caption: string;
  size?: number;
};

export type ChatErrorInfo = {
  message: string;
  category: "auth" | "quota" | "timeout" | "content_filter" | "network" | "server" | "unknown";
  raw?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string | null;
  agentName?: string | null;
  toolCalls?: ChatToolCall[] | null;
  todo?: ChatTodo | null;
  askUser?: ChatAskUser | null;
  attachments?: ChatAttachment[] | null;
  artifacts?: ChatArtifact[] | null;
  thinkingChain?: ChainGroup[] | null;
  errorInfo?: ChatErrorInfo | null;
  usage?: { input_tokens: number; output_tokens: number; total_tokens?: number } | null;
  timestamp: number;
  streaming?: boolean;
};

// ─── 思维链 (Thinking Chain) 类型 ───

/** 叙事流条目类型 */
export type ChainEntry =
  | { kind: "thinking"; content: string }       // LLM extended thinking 内容
  | { kind: "text"; content: string; icon?: string }  // LLM 推理意图 / chain_text / 状态通知
  | { kind: "tool_start"; toolId: string; tool: string; args: Record<string, unknown>; description: string; status?: "running" | "done" | "error" }
  | { kind: "tool_end"; toolId: string; tool: string; result: string; status: "done" | "error" }
  | { kind: "compressed"; beforeTokens: number; afterTokens: number };

/** 一个 ReAct 迭代组 = 按时间顺序的叙事流 */
export type ChainGroup = {
  iteration: number;
  entries: ChainEntry[];             // 按时间顺序的叙事片段
  durationMs?: number;               // 本轮耗时 ms
  hasThinking: boolean;              // 模型是否返回了 extended thinking
  collapsed: boolean;                // 当前折叠状态
  // 向后兼容（用于 IM 视图等）
  toolCalls: ChainToolCall[];
};

export type ChainToolCall = {
  toolId: string;
  tool: string;
  args: Record<string, unknown>;
  result?: string;
  status: "running" | "done" | "error";
  description: string;
};

/** IM 消息中的思维链摘要项 */
export type ChainSummaryItem = {
  iteration: number;
  thinking_preview: string;
  thinking_duration_ms: number;
  tools: { name: string; input_preview: string; result_preview?: string }[];
  context_compressed?: { before_tokens: number; after_tokens: number };
};

/** 聊天显示模式 */
export type ChatDisplayMode = "bubble" | "flat";

export type ChatToolCall = {
  id?: string;
  tool: string;
  args: Record<string, unknown>;
  result?: string | null;
  status: "pending" | "running" | "done" | "error";
};

export type ChatTodo = {
  id: string;
  taskSummary: string;
  steps: ChatTodoStep[];
  status: "in_progress" | "completed" | "failed" | "cancelled";
};

/** @deprecated Use ChatTodo instead */
export type ChatPlan = ChatTodo;

export type ChatTodoStep = {
  id?: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "skipped" | "failed" | "cancelled";
  result?: string | null;
};

export type PlanApprovalEvent = {
  conversation_id: string;
  summary: string;
  plan_id: string;
  plan_file: string;
};

export type ChatAskQuestion = {
  id: string;
  prompt: string;
  options?: { id: string; label: string }[];
  allow_multiple?: boolean; // true = multi-select, false = single-select (default)
};

export type ChatAskUser = {
  /** Simple single question (backward compat, used when questions is empty) */
  question: string;
  options?: { id: string; label: string }[];
  /** Structured multi-question support */
  questions?: ChatAskQuestion[];
  answered?: boolean;
  answer?: string;
};

export type ChatAttachment = {
  type: "image" | "file" | "voice" | "video" | "document";
  name: string;
  url?: string;
  previewUrl?: string;
  size?: number;
  mimeType?: string;
  /** Transient upload tracking ID — not persisted to backend */
  _uploadId?: string;
};

export type ConversationStatus = "idle" | "running" | "completed" | "error";

export type ChatConversation = {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: number;
  messageCount: number;
  pinned?: boolean;
  titleGenerated?: boolean;
  titleManuallySet?: boolean;
  agentProfileId?: string;
  endpointId?: string;
  status?: ConversationStatus;
};

// ─── Slash commands ───

export type SlashCommand = {
  id: string;
  label: string;
  description: string;
  icon?: string;
  action: (args: string) => void;
};

// ─── MCP config types ───

export type MCPConfigField = {
  key: string;
  label: string;
  type: "text" | "secret" | "number" | "select" | "bool" | "url" | "path";
  required?: boolean;
  help?: string;
  helpUrl?: string;
  default?: string | number | boolean;
  placeholder?: string;
  options?: string[];
  when?: Record<string, string> | null;
};

// ─── Skill types ───

export type SkillConfigField = {
  key: string;
  label: string;
  type: "text" | "secret" | "number" | "select" | "bool";
  required?: boolean;
  help?: string;
  default?: string | number | boolean;
  options?: string[];
  min?: number;
  max?: number;
};

export type SkillInfo = {
  skillId: string;
  name: string;
  description: string;
  name_i18n?: Record<string, string> | null;
  description_i18n?: Record<string, string> | null;
  system: boolean;
  enabled?: boolean;
  toolName?: string | null;
  category?: string | null;
  path?: string | null;
  sourceUrl?: string | null;
  config?: SkillConfigField[] | null;
  configComplete?: boolean;
};

export type MarketplaceSkill = {
  id: string;         // e.g. "vercel-labs/agent-skills/vercel-react-best-practices"
  skillId: string;    // e.g. "vercel-react-best-practices"
  name: string;
  description: string;
  author: string;     // source repo owner
  url: string;        // install URL: "owner/repo@skill"
  installs?: number;
  stars?: number;
  tags?: string[];
  installed?: boolean;
};

// ─── Persona presets ───

export const PERSONA_PRESETS = [
  { id: "default", name: "Default Assistant", desc: "Professional, friendly, balanced", style: "Great for everyday use — a general-purpose persona" },
  { id: "business", name: "Business Consultant", desc: "Formal, professional, data-driven", style: "Suited to work: formal reports and data analysis" },
  { id: "tech_expert", name: "Tech Expert", desc: "Concise, precise, code-oriented", style: "Suited to programming and technical Q&A" },
  { id: "butler", name: "Personal Butler", desc: "Thoughtful, meticulous, polite", style: "Suited to lifestyle tasks: scheduling and travel planning" },
  { id: "girlfriend", name: "Virtual Girlfriend", desc: "Gentle, caring, emotionally warm", style: "Suited to emotional companionship, listening, and care" },
  { id: "boyfriend", name: "Virtual Boyfriend", desc: "Upbeat, cheerful, humorous", style: "Suited to emotional companionship, easygoing and fun" },
  { id: "family", name: "Family", desc: "Warm, caring, a bit chatty", style: "Suited to family settings: elder-like warmth and care" },
  { id: "jarvis", name: "Jarvis", desc: "Calm, wise, British wit", style: "Suited to tech enthusiasts — an Iron Man-style AI butler" },
] as const;
