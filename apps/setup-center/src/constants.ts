// ─── Shared constants for Setup Center ───

import type { ProviderInfo } from "./types";
import SHARED_PROVIDERS from "@shared/providers.json";

// 内置 Provider 列表（打包模式下 venv 不可用时作为回退）
// 数据来源：@shared/providers.json（与 Python 后端共享同一份文件）
// registry_class 字段仅 Python 使用，前端忽略
export const BUILTIN_PROVIDERS: ProviderInfo[] = SHARED_PROVIDERS as ProviderInfo[];

/** STT recommended models (indexed by provider slug) */
export const STT_RECOMMENDED_MODELS: Record<string, { id: string; note: string }[]> = {
  "openai":          [{ id: "gpt-4o-transcribe", note: "recommended" }, { id: "whisper-1", note: "" }],
  "dashscope":       [{ id: "qwen3-asr-flash", note: "recommended (file ≤5min)" }],
  "dashscope-intl":  [{ id: "qwen3-asr-flash", note: "recommended (file ≤5min)" }],
  "groq":            [{ id: "whisper-large-v3-turbo", note: "recommended" }, { id: "whisper-large-v3", note: "" }],
  "siliconflow":     [{ id: "FunAudioLLM/SenseVoiceSmall", note: "recommended" }, { id: "TeleAI/TeleSpeechASR", note: "" }],
  "siliconflow-intl":[{ id: "FunAudioLLM/SenseVoiceSmall", note: "recommended" }, { id: "TeleAI/TeleSpeechASR", note: "" }],
};

export const PIP_INDEX_PRESETS: { id: "official" | "tuna" | "aliyun" | "custom"; label: string; url: string }[] = [
  { id: "aliyun", label: "Aliyun (default)", url: "https://mirrors.aliyun.com/pypi/simple/" },
  { id: "tuna", label: "Tsinghua TUNA", url: "https://pypi.tuna.tsinghua.edu.cn/simple" },
  { id: "official", label: "Official PyPI", url: "https://pypi.org/simple/" },
  { id: "custom", label: "Custom…", url: "" },
];
