import { Settings2, Sparkles } from "lucide-react";
import { Button } from "../../components/ui/button";
import { openConfig } from "../settings/config/configDeepLink";
import { ATTRIBUTION_LABELS, SALES_DEF_LABELS } from "./tanyaFormat";

export function TanyaRulesStrip({ status }) {
  if (!status) return null;
  return (
    <div className="tanya-rules" data-testid="tanya-rules-strip">
      <div className="tanya-rule">
        <span className="tanya-rule-label">Arti &ldquo;penjualan&rdquo;</span>
        <span className="tanya-rule-value" data-testid="tanya-rule-sales-definition">{SALES_DEF_LABELS[status.sales_definition] || status.sales_definition}</span>
      </div>
      <div className="tanya-rule">
        <span className="tanya-rule-label">Kredit sales tim</span>
        <span className="tanya-rule-value" data-testid="tanya-rule-attribution">{ATTRIBUTION_LABELS[status.sales_attribution] || status.sales_attribution}</span>
      </div>
      <div className="tanya-rule">
        <span className="tanya-rule-label">Chat AI</span>
        <span className={`tanya-pill ${status.chat_enabled ? "on" : "off"}`} data-testid="tanya-ai-status">
          <Sparkles className="h-3.5 w-3.5" /> {status.chat_enabled ? (status.mock ? "Mode uji (tiruan)" : "Aktif") : status.has_key ? "Kunci ada, belum diaktifkan" : "Menunggu kunci OpenAI"}
        </span>
      </div>
      {status.can_edit_rules && status.budget && (
        <div className="tanya-rule">
          <span className="tanya-rule-label">Biaya AI bulan ini</span>
          <span className={`tanya-rule-value ${status.budget.exceeded ? "tanya-over" : ""}`} data-testid="tanya-budget">
            ${Number(status.budget.spent_usd || 0).toFixed(2)} / ${Number(status.budget.limit_usd || 0).toFixed(0)}{status.budget.exceeded ? " · habis" : ""}
          </span>
        </div>
      )}
      {status.can_edit_rules && (
        <Button size="sm" variant="outline" className="tanya-rules-btn" data-testid="tanya-edit-rules"
          onClick={() => openConfig({ key: "ai.sales_definition", group: "asisten-analitik" })}>
          <Settings2 className="h-4 w-4" /> Atur di Pusat Pengaturan
        </Button>
      )}
    </div>
  );
}
