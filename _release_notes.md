## v1.26.9 更新日志

本版本聚焦于**对话质量提升**、**组织编排稳定性**和**多平台兼容性**，共解决 40+ 个已知问题，并全面升级了应用内反馈体验和 IM 通道覆盖。

### 🚀 新增功能

- **飞书 Lark 国际版支持** — 飞书适配器全面支持 Lark 国际版域名与 API，CLI 向导新增国际版配置选项，海外用户无需额外适配 (#346)
- **反馈系统全面重构** — 重新设计应用内反馈流程：支持进度追踪、用户回复、Markdown 渲染、公共反馈搜索与浏览，提交/回复交互全面优化
- **LLM 重试状态实时通知** — 当模型请求遇到限速或出错触发自动重试/模型切换时，用户界面会实时显示当前状态，不再无声等待 (#317)
- **编译端点与 STT 端点可编辑** — 设置中心新增对编译（Compiler）端点和语音识别（STT）端点的编辑能力
- **内网代理自动适配** — 内网地址（localhost、私有 IP 等）自动跳过代理，新增 `NO_PROXY` 环境变量支持，代理配置 UI 简化
- **移除本地 Whisper 语音识别** — 统一使用在线 STT 服务，减少安装体积和依赖

### 🐛 问题修复

**对话质量与 LLM**

- **ForceToolCall 误判信息请求** — 修复模型在回复纯信息性问题（总结/解释/列出）时被强制进行工具调用的误判逻辑，消除历史前缀措辞和时间戳注入导致的重复问题，整体对话质量显著改善
- **Stream-only 端点 ForceToolCall 失效** — 补齐流式响应路径下的文本工具调用提取逻辑，修复仅支持流式的端点无法正确触发工具调用重试的问题
- **单端点 thinking 被错误永久禁用** — 修复只有一个端点时，thinking 模式状态被错误地永久关闭，导致对话内容重复的问题 (#327)
- **429 限速被误判为结构性错误** — 修复 API 返回 429 限速响应时被错误归类为不可重试的结构性错误，导致请求直接失败而非自动等待重试的问题 (#324)
- **`model_not_found` (503) 错误分类错误** — 从 transient 改为 structural，避免对不存在的模型进行无意义的反复重试 (#314)
- **SSE 解析不兼容部分 API 提供商** — 修复 SSE 流解析要求 `data:` 后必须有空格的问题，兼容更多 API 提供商的非标准 SSE 实现 (#348)
- **Gemini 多轮工具调用 400 错误** — 修复 Gemini 模型的 `thought_signature` 在消息管道传递中丢失，导致后续工具调用轮次返回 400 错误的问题 (#294)
- **GLM 模型 Llama 风格工具调用无法解析** — 为文本工具调用解析器增加 Llama `<function=name>` 格式的 fallback 支持 (#296)
- **余额/配额错误分类与处理** — 修复余额不足和配额耗尽错误的分类逻辑，组织级场景下给出友好的错误提示而非原始报错

**消息与上下文**

- **消息历史管理破坏性截断** — 重构为 metadata trim 策略，超长对话不再丢失关键上下文 (#309)
- **Word/Excel/PPT 文档上传后无法提取内容** — 办公文档现在可以正常上传并提取文本内容 (#310)
- **Shell pip --user 命令改写** — 将 pip `--user` 参数从命令层改写移到 prompt 层，避免命令被意外修改 (#284)

**Windows 兼容性**

- **中文命令执行乱码** — 修复在 Windows 系统上执行含中文的命令时，`cmd.exe` 的 OEM 编码（GBK）损坏 Unicode 字符导致命令反复失败的问题。含非 ASCII 字符的命令现在自动通过 PowerShell `-EncodedCommand` 执行，完全绕过编码陷阱
- **Shell 工具拒绝访问** — 修复 Windows 下 Shell 工具遇到 `[WinError 5]` 拒绝访问的问题 (#284)
- **read_file 对目录路径误报** — 修复 Windows 下 `read_file` 工具对目录路径误报 PermissionError 的问题 (#307)

**微信 (WeChat)**

- **图片/视频/文件发送失败** — 补全 iLink Bot API 协议必需的 `base_info` 和 `context_token` 字段，修复媒体上传 URL 获取失败导致图片等媒体消息被降级为纯文本的问题 (#339 #351)
- **CDN 上传失败静默丢弃** — CDN 下载失败时正确标记媒体为失败状态并记录完整错误信息，而非静默丢弃 (#339)
- **网关层无意义二次下载** — 适配器已标记失败的媒体不再被网关层重复尝试下载

**技能系统**

- **安装技能超时** — 安装技能后的自动翻译改为后台异步执行，避免 LLM 调用阻塞安装响应导致超时 (#297)
- **第三方命令安装技能失败** — 用信号提取替代 CLI 前缀白名单机制，正确识别各种格式的技能安装链接和命令 (#298)
- **技能详情加载缓慢** — 后端并发请求 GitHub 获取技能信息，前端增加超时提示与重试机制

**组织编排**

- **指挥台对话持久化** — 修复退出组织指挥台后聊天记录丢失的问题，对话历史现在正确保存
- **OrgMemoryEntry 类型崩溃** — 修复 LLM 传入字符串类型 importance 值导致记忆排序崩溃的问题 (#335)
- **tags 类型防御** — 修复组织编辑器和后端 tags 字段收到非数组值时前后端崩溃的问题 (#336)
- **冻结节点死锁** — 冻结节点现在支持右键解除冻结，修复领导节点冻结后指挥台无法操作的死锁问题
- **项目面板缺陷** — 修复组织编排项目面板三个功能缺陷 (#340)
- **暗色主题 CSS** — 清理组织编排全部组件的暗色主题样式兜底 (#340)
- **新建组织无反馈** — 修复「新建组织」操作无交互反馈且列表校验缺失的问题
- **项目看板数据对齐** — 修复项目看板与运营大屏的数据口径不一致问题

**调度器**

- **定时任务结果未投递到 IM** — 修复 task 类型定时任务执行完成后结果未发送到 IM 通道的问题 (#295)
- **手动触发任务阻塞** — 手动触发定时任务改为非阻塞执行，并修复并发调度的安全隐患

**桌面端与前端**

- **聊天区含表格时自动滚到顶部** — 修复输出内容包含表格时聊天区域自动滚到页面顶部的问题 (#318)
- **托盘点击跳转页面** — 修复点击系统托盘图标恢复窗口时强制跳转到状态面板的问题，现在保持用户当前页面
- **远程模式功能受限** — 移除远程模式下的 UI 限制，Web 密码管理和技能导入功能现在对远程用户可见
- **端点操作无提示** — 端点保存/删除操作在后端不可达时给出友好错误提示，而非静默失败 (#312)
- **Lark 国际版平台名称未翻译** — 修复国际化配置中 Lark 平台名称未正确翻译的问题

### 💄 体验优化

- **技能详情 Markdown 渲染** — 技能详情弹窗增加层级样式支持，正确渲染代码块、标题、引用、表格等
- **反馈交互全面升级** — 独立进度弹窗、Markdown 回复渲染、气泡宽度自适应、内嵌发送按钮、时区修正、未读提示等十余项细节优化

### 📝 其他

- **refactor(frontend)**: 统一 Agent 图标渲染组件，消除三份重复的 SVG 图标数据
- **refactor(tags)**: 用 `__post_init__` 替代散布式 normalize 调用，消除标签处理的代码分散问题
- **refactor(core)**: MiniMax M2.7 能力推断补全、浏览器关闭超时保护、循环终态防护

---

## What's Changed in v1.26.9

This release focuses on **conversation quality**, **organization editor stability**, and **cross-platform compatibility**, resolving 40+ known issues and delivering a fully redesigned in-app feedback experience with expanded IM channel coverage.

### 🚀 New Features

- **Feishu Lark international support** — Feishu adapter now fully supports Lark international domains and APIs; CLI wizard adds international edition configuration, enabling overseas users out of the box (#346)
- **Feedback system overhaul** — Completely redesigned in-app feedback: progress tracking, user replies, Markdown rendering, public feedback search & browsing, and polished submission/reply interactions
- **Real-time LLM retry notifications** — When model requests hit rate limits or errors triggering automatic retry/model switching, the UI now shows live status updates instead of silent waiting (#317)
- **Compiler & STT endpoint editing** — Setup Center now supports editing Compiler endpoints and Speech-to-Text (STT) endpoints
- **Automatic proxy bypass for intranet** — Internal addresses (localhost, private IPs, etc.) auto-skip proxy; added `NO_PROXY` environment variable support; simplified proxy configuration UI
- **Removed local Whisper speech recognition** — Unified to online STT service, reducing install size and dependencies

### 🐛 Bug Fixes

**Conversation Quality & LLM**

- **ForceToolCall misjudging info requests** — Fix models being forced to make tool calls when responding to purely informational questions (summarize/explain/list); eliminated duplicates from history prefix wording and timestamp injection, significantly improving overall conversation quality
- **ForceToolCall broken on stream-only endpoints** — Add missing text tool call extraction in the streaming response path, fixing stream-only endpoints failing to trigger tool call retries correctly
- **Thinking permanently disabled with single endpoint** — Fix thinking mode being permanently turned off with only one endpoint configured, causing repetitive conversations (#327)
- **429 rate limit misclassified as structural error** — Fix API 429 rate-limit responses being incorrectly classified as non-retryable structural errors, causing requests to fail immediately instead of auto-retrying (#324)
- **`model_not_found` (503) error classification** — Changed from transient to structural, preventing pointless retries against non-existent models (#314)
- **SSE parsing incompatible with some providers** — Fix SSE stream parser requiring a space after `data:`, now compatible with more API providers' non-standard SSE implementations (#348)
- **Gemini multi-turn tool call 400 errors** — Fix `thought_signature` being lost during message pipeline propagation for Gemini models, causing subsequent tool call rounds to return 400 errors (#294)
- **GLM Llama-style tool calls not parsed** — Add fallback support for Llama `<function=name>` format in the text tool call parser (#296)
- **Balance/quota error classification** — Fix balance and quota error classification logic; organization-level scenarios now display friendly error messages instead of raw errors

**Messages & Context**

- **Destructive message history truncation** — Refactored to metadata trim strategy, preventing loss of critical context in long conversations (#309)
- **Word/Excel/PPT upload failing to extract content** — Office documents now upload and extract text correctly (#310)
- **Shell pip --user command rewrite** — Moved pip `--user` argument from command-level rewriting to prompt layer, preventing unintended command modifications (#284)

**Windows Compatibility**

- **Chinese commands garbled** — Fix commands containing Chinese characters being corrupted by `cmd.exe`'s OEM encoding (GBK), causing repeated failures. Commands with non-ASCII characters now automatically route through PowerShell `-EncodedCommand`, completely bypassing the encoding pitfall
- **Shell tool access denied** — Fix Shell tool encountering `[WinError 5]` access denied on Windows (#284)
- **read_file false PermissionError on directories** — Fix `read_file` tool incorrectly reporting PermissionError for directory paths on Windows (#307)

**WeChat**

- **Image/video/file sending failure** — Add missing `base_info` and `context_token` fields required by the iLink Bot API protocol, fixing media upload URL retrieval failures that caused media to be degraded to plain text (#339 #351)
- **CDN upload failure silently dropped** — CDN download failures now properly mark media as failed and log complete error responses, instead of silent drops (#339)
- **Gateway redundant re-download** — Media already marked as failed by the adapter is no longer re-attempted by the gateway layer

**Skills**

- **Skill installation timeout** — Post-install auto-translation now runs asynchronously in the background, preventing LLM calls from blocking the installation response (#297)
- **Third-party skill installation failure** — Replace CLI prefix whitelist with signal-based extraction to correctly identify skill installation links and commands in various formats (#298)
- **Slow skill detail loading** — Backend now fetches skill info from GitHub concurrently; frontend adds timeout alerts and retry mechanisms

**Organization Editor**

- **Command center chat persistence** — Fix chat history being lost after exiting the organization command center; conversations now correctly persist
- **OrgMemoryEntry type crash** — Fix LLM passing string-type importance values causing memory sorting to crash (#335)
- **Tags type defense** — Fix organization editor and backend crashing when tags field receives non-array values (#336)
- **Frozen node deadlock** — Frozen nodes now support right-click unfreeze, resolving command center deadlock when leader nodes are frozen
- **Project panel defects** — Fix three functional defects in the organization project panel (#340)
- **Dark theme CSS** — Clean up dark theme style fallbacks across all organization editor components (#340)
- **New organization no feedback** — Fix "New Organization" action having no interaction feedback and missing list validation
- **Project board data alignment** — Fix data metric discrepancies between project board and operations dashboard

**Scheduler**

- **Scheduled task results not delivered to IM** — Fix task-type scheduled job results not being sent to IM channels after execution (#295)
- **Manual task trigger blocking** — Manual task triggers are now non-blocking, with concurrent scheduling safety fixes

**Desktop & Frontend**

- **Chat area auto-scrolling to top with tables** — Fix chat area auto-scrolling to the top of the page when output contains table elements (#318)
- **Tray click forces page navigation** — Fix clicking the system tray icon to restore the window forcing navigation to the status panel; now preserves the user's current page
- **Remote mode feature restrictions** — Removed UI restrictions in remote mode; web password management and skill import now visible to remote users
- **No feedback when backend unreachable** — Endpoint save/delete operations now show friendly error messages when the backend is unreachable (#312)
- **Lark platform name not translated** — Fix Lark platform name not properly translated in i18n configuration

### 💄 UX Improvements

- **Skill detail Markdown rendering** — Skill detail popups now correctly render code blocks, headings, blockquotes, tables, and other Markdown elements with proper styling
- **Feedback UX overhaul** — Standalone progress dialogs, Markdown reply rendering, auto-width reply bubbles, inline send button, timezone correction, unread indicators, and 10+ other interaction refinements

### 📝 Other

- **refactor(frontend)**: Unified Agent icon rendering component, eliminating three duplicate copies of SVG icon data
- **refactor(tags)**: Replaced scattered normalize calls with `__post_init__`, eliminating dispersed tag processing code
- **refactor(core)**: MiniMax M2.7 capability inference, browser close timeout protection, loop terminal state safeguards

**Full Changelog**: https://github.com/openakita/openakita/compare/v1.26.8...v1.26.9
