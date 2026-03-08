import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { FieldBool } from "../components/EnvFields";
import { IconBook, IconClipboard, IconBot, IconPlus, LogoTelegram, LogoFeishu, LogoWework, LogoDingtalk, LogoQQ } from "../icons";
import { safeFetch } from "../providers";
import type { EnvMap } from "../types";
import { envGet, envSet } from "../utils";
import { copyToClipboard } from "../utils/clipboard";

type IMBot = {
  id: string;
  type: string;
  name: string;
  agent_profile_id: string;
  enabled: boolean;
  credentials: Record<string, unknown>;
};

const BOT_TYPE_LABELS: Record<string, string> = {
  feishu: "飞书",
  telegram: "Telegram",
  dingtalk: "钉钉",
  wework: "企业微信",
  onebot: "OneBot (QQ)",
  qqbot: "QQ 官方机器人",
};

const ENABLED_KEY_TO_TYPE: Record<string, string> = {
  TELEGRAM_ENABLED: "telegram",
  FEISHU_ENABLED: "feishu",
  WEWORK_ENABLED: "wework",
  DINGTALK_ENABLED: "dingtalk",
  QQBOT_ENABLED: "qqbot",
  ONEBOT_ENABLED: "onebot",
};

type IMConfigViewProps = {
  envDraft: EnvMap;
  setEnvDraft: (updater: (prev: EnvMap) => EnvMap) => void;
  setNotice: (v: string | null) => void;
  busy: string | null;
  secretShown: Record<string, boolean>;
  onToggleSecret: (k: string) => void;
  currentWorkspaceId: string | null;
  onNavigateToBotConfig?: (presetType?: string) => void;
  apiBaseUrl?: string;
};

export function IMConfigView(props: IMConfigViewProps) {
  const {
    envDraft, setEnvDraft, setNotice, busy,
    onNavigateToBotConfig, apiBaseUrl,
  } = props;
  const { t } = useTranslation();
  const [bots, setBots] = useState<IMBot[]>([]);

  const fetchBots = useCallback(async () => {
    if (!apiBaseUrl) return;
    try {
      const res = await safeFetch(`${apiBaseUrl}/api/agents/bots`);
      const data = await res.json();
      setBots(data.bots || []);
    } catch { /* ignore */ }
  }, [apiBaseUrl]);

  useEffect(() => { fetchBots(); }, [fetchBots]);

  const _envBase = { envDraft, onEnvChange: setEnvDraft, busy };
  const FB = (p: { k: string; label: string; help?: string; defaultValue?: boolean }) =>
    <FieldBool {...p} {..._envBase} />;

  const channels = [
    {
      title: "Telegram",
      appType: t("config.imTypeLongPolling"),
      logo: <LogoTelegram size={22} />,
      enabledKey: "TELEGRAM_ENABLED",
      docUrl: "https://t.me/BotFather",
      needPublicIp: false,
    },
    {
      title: t("config.imFeishu"),
      appType: t("config.imTypeCustomApp"),
      logo: <LogoFeishu size={22} />,
      enabledKey: "FEISHU_ENABLED",
      docUrl: "https://open.feishu.cn/",
      needPublicIp: false,
    },
    {
      title: t("config.imWework"),
      appType: t("config.imTypeSmartBot"),
      logo: <LogoWework size={22} />,
      enabledKey: "WEWORK_ENABLED",
      docUrl: "https://work.weixin.qq.com/",
      needPublicIp: true,
    },
    {
      title: t("config.imDingtalk"),
      appType: t("config.imTypeInternalApp"),
      logo: <LogoDingtalk size={22} />,
      enabledKey: "DINGTALK_ENABLED",
      docUrl: "https://open.dingtalk.com/",
      needPublicIp: false,
    },
    {
      title: "QQ 机器人",
      appType: t("config.imTypeQQBot"),
      logo: <LogoQQ size={22} />,
      enabledKey: "QQBOT_ENABLED",
      docUrl: "https://bot.q.qq.com/wiki/develop/api-v2/",
      needPublicIp: false,
    },
    {
      title: "OneBot",
      appType: t("config.imTypeOneBot"),
      logo: <LogoQQ size={22} />,
      enabledKey: "ONEBOT_ENABLED",
      docUrl: "https://github.com/botuniverse/onebot-11",
      needPublicIp: false,
    },
  ];

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="cardTitle">{t("config.imTitle")}</div>
          <div style={{ display: "flex", gap: 6 }}>
            {onNavigateToBotConfig && (
              <button
                className="btnSmall"
                style={{
                  display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12,
                  background: "var(--primary, #3b82f6)", color: "#fff", border: "none",
                  padding: "4px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
                }}
                onClick={() => onNavigateToBotConfig()}
              >
                <IconBot size={13} />{t("config.imGoToBotConfig")}
              </button>
            )}
            <button className="btnSmall" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12 }}
              onClick={() => { navigator.clipboard.writeText("https://github.com/anthropic-lab/openakita/blob/main/docs/im-channels.md"); setNotice(t("config.imGuideDocCopied")); }}
              title={t("config.imGuideDoc")}
            ><IconBook size={13} />{t("config.imGuideDoc")}</button>
          </div>
        </div>
        <div className="cardHint">{t("config.imHint")}</div>
        <div className="divider" />

        <FB k="IM_CHAIN_PUSH" label={t("config.imChainPush")} help={t("config.imChainPushHelp")} />
        <div className="divider" />

        {channels.map((c) => {
          const enabled = envGet(envDraft, c.enabledKey, "false").toLowerCase() === "true";
          const botType = ENABLED_KEY_TO_TYPE[c.enabledKey] || "";
          const channelBots = bots.filter((b) => b.type === botType);

          return (
            <div key={c.enabledKey} className="card" style={{ marginTop: 10 }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <div className="row" style={{ alignItems: "center", gap: 10 }}>
                  {c.logo}
                  <span className="label" style={{ marginBottom: 0 }}>{c.title}</span>
                  <span className="pill" style={{ fontSize: 10, padding: "1px 6px", background: "#f1f5f9", color: "#475569" }}>{c.appType}</span>
                  {c.needPublicIp && <span className="pill" style={{ fontSize: 10, padding: "1px 6px", background: "#fef3c7", color: "#92400e" }}>{t("config.imNeedPublicIp")}</span>}
                </div>
                <label className="pill" style={{ cursor: "pointer", userSelect: "none" }}>
                  <input style={{ width: 16, height: 16 }} type="checkbox" checked={enabled}
                    onChange={(e) => setEnvDraft((m) => envSet(m, c.enabledKey, String(e.target.checked)))} />
                  {t("config.enable")}
                </label>
              </div>
              <div className="row" style={{ alignItems: "center", gap: 6, marginTop: 4 }}>
                <button className="btnSmall"
                  style={{ fontSize: 11, padding: "2px 8px", display: "inline-flex", alignItems: "center", gap: 3 }}
                  title={c.docUrl}
                  onClick={async () => { const ok = await copyToClipboard(c.docUrl); if (ok) setNotice(t("config.imDocCopied")); }}
                ><IconClipboard size={12} />{t("config.imDoc")}</button>
                <span className="help" style={{ fontSize: 11, userSelect: "all", opacity: 0.6 }}>{c.docUrl}</span>
              </div>

              {/* Bot list for this channel */}
              <div style={{ marginTop: 8 }}>
                {channelBots.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, opacity: 0.5, marginBottom: 2 }}>
                      {t("config.imConfiguredBots")} ({channelBots.length})
                    </div>
                    {channelBots.map((bot) => (
                      <div key={bot.id} style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "6px 10px", borderRadius: 6,
                        background: "var(--bg2, #f8fafc)", fontSize: 12,
                      }}>
                        <span style={{
                          width: 6, height: 6, borderRadius: 3, flexShrink: 0,
                          background: bot.enabled ? "#10b981" : "#94a3b8",
                        }} />
                        <span style={{ fontWeight: 600, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {bot.name || bot.id}
                        </span>
                        <span style={{ opacity: 0.4, fontFamily: "monospace", fontSize: 10 }}>{bot.id}</span>
                        <span style={{ marginLeft: "auto", opacity: 0.5, fontSize: 11, whiteSpace: "nowrap" }}>
                          Agent: {bot.agent_profile_id}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, opacity: 0.4, fontStyle: "italic" }}>
                    {t("config.imNoBots")}
                  </div>
                )}
                {onNavigateToBotConfig && (
                  <button
                    onClick={() => onNavigateToBotConfig(botType)}
                    style={{
                      marginTop: 6, display: "inline-flex", alignItems: "center", gap: 4,
                      padding: "3px 10px", borderRadius: 6, border: "1px dashed var(--line)",
                      background: "transparent", cursor: "pointer", fontSize: 11,
                      color: "var(--primary, #3b82f6)", fontWeight: 500,
                    }}
                  >
                    <IconPlus size={10} />{t("config.imAddBot")}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
