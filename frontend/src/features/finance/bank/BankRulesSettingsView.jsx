import { useCallback, useEffect, useState } from "react";
import ErrorNotice from "../../../components/ErrorNotice";
import { StatusTabs } from "../../../components/ListControls";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import ReconRulesPanel from "./ReconRulesPanel";
import ReconFormatsPanel from "./ReconFormatsPanel";

/** Pengaturan › Keuangan › Aturan & Template Bank (dulu tab di Rekonsiliasi Bank). */
export default function BankRulesSettingsView() {
  const [tab, setTab] = useState("rules");
  const [rules, setRules] = useState([]);
  const [formats, setFormats] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(""), 5000); };
  const fail = (e) => setErr(apiErrorText(e));

  const load = useCallback(async () => {
    try {
      const [rl, fm] = await Promise.all([
        axios.get(`${API}/bank-reconciliation/rules`),
        axios.get(`${API}/bank-reconciliation/formats`),
      ]);
      setRules(Array.isArray(rl.data) ? rl.data : []);
      setFormats(Array.isArray(fm.data) ? fm.data : []);
    } catch (e) { fail(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const suggested = rules.filter((r) => r.status === "suggested").length;
  return (
    <div data-testid="bank-rules-settings-view">
      <ErrorNotice message={err} onDismiss={() => setErr("")} onRetry={load} testId="bank-rules-error" />
      {msg && <p data-testid="bank-rules-notice" className="mb-2 rounded-lg bg-[#EAF7EF] px-3 py-2 text-[12px] font-semibold text-[#1B7F4B]">{msg}</p>}
      <StatusTabs value={tab} onChange={setTab} testIdPrefix="bank-rules-tab" tabs={[
        { key: "rules", label: "Aturan Pembelajaran", count: suggested || undefined },
        { key: "formats", label: "Template Bank", count: formats.length },
      ]} />
      <div className="mt-3">
        {tab === "rules"
          ? <ReconRulesPanel rules={rules} onReload={load} onError={fail} onNotify={notify} />
          : <ReconFormatsPanel formats={formats} onReload={load} onError={fail} onNotify={notify} />}
      </div>
    </div>
  );
}
