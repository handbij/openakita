import { useTranslation } from "react-i18next";

type ConfirmDialogProps = {
  dialog: { message: string; onConfirm: () => void } | null;
  onClose: () => void;
};

export function ConfirmDialog({ dialog, onClose }: ConfirmDialogProps) {
  const { t } = useTranslation();
  if (!dialog) return null;
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalContent" style={{ maxWidth: 380, padding: 24 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>{dialog.message}</div>
        <div className="dialogFooter" style={{ justifyContent: "flex-end" }}>
          <button className="btnSmall" onClick={onClose}>{t("common.cancel")}</button>
          <button className="btnSmall" style={{ background: "var(--danger, #e53935)", color: "#fff", border: "none" }} onClick={() => { dialog.onConfirm(); onClose(); }}>{t("common.confirm")}</button>
        </div>
      </div>
    </div>
  );
}
