## 分析结果

感谢反馈！已在 v1.25.x 分支确认并修复了同样的问题（commit `166adf58`）。

### 根因

配置文件 `data/llm_endpoints.json` 的**读写路径存在结构性分歧**：

| 组件 | 路径来源 | 职责 |
|------|---------|------|
| Config API 读取 | `get_default_config_path()` → 从 CWD 向上搜索 | 前端展示 |
| EndpointManager 写入 | `settings.project_root / data / ...` 硬编码 | 保存变更 |
| LLMClient 加载 | `self._config_path`（初始化时缓存） | 运行时端点选择 |

三条路径各自独立计算，在 CWD ≠ `settings.project_root` 的部署场景下（如 Linux systemd 服务），读和写操作各自操作不同的文件，导致 Web 端变更 Priority 后看起来"没生效"。

### 修复方案

**统一为单一路径权威入口**，消除多路径独立计算的架构隐患：

1. **`get_default_config_path()`** — 当 `settings` 可用时，无条件返回 `settings.project_root / data / llm_endpoints.json`（不做文件探测），CWD 搜索仅作为 settings 不可用时的降级
2. **`EndpointManager`** — 新增 `config_path` 参数，所有创建点通过 `get_default_config_path()` 传入路径
3. **`_trigger_reload`** — 热重载前同步 `LLMClient._config_path` 到权威路径，确保 reload 读取的是刚写入的文件
4. **`_save_config`** — CLI 路径更新 priority 后对数组排序，保持 JSON 文件数组顺序与 priority 值一致

修复后所有读写路径统一收敛到 `get_default_config_path()` 一个函数的输出，彻底消除路径分歧。
