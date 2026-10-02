import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { toast } from "../../hooks/use-toast";
import { downloadXlsx } from "./tanyaApi";
import { formatValue } from "./tanyaFormat";

export function TanyaTable({ result, spec = {} }) {
  const [busy, setBusy] = useState(false);
  const cols = (result?.columns || []).filter((c) => !spec.columns || spec.columns.includes(c.key));
  const rows = result?.rows || [];
  const onDownload = async () => {
    setBusy(true);
    try {
      await downloadXlsx(result.result_id, result.title);
    } catch {
      toast({ title: "Gagal mengunduh Excel", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="tanya-table" data-testid={`tanya-table-${result.result_id}`}>
      <div className="tanya-table-head">
        <div className="tanya-block-title">{spec.title || result.title}</div>
        <Button size="sm" variant="outline" onClick={onDownload} disabled={busy || !rows.length}
          data-testid={`tanya-download-${result.result_id}`}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Unduh Excel
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="tanya-empty" data-testid="tanya-table-empty">Tidak ada data pada periode ini.</div>
      ) : (
        <div className="tanya-table-scroll">
          <Table>
            <TableHeader>
              <TableRow>{cols.map((c) => <TableHead key={c.key} className={c.unit ? "text-right" : ""}>{c.label}</TableHead>)}</TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i}>
                  {cols.map((c) => (
                    <TableCell key={c.key} className={c.unit ? "text-right tabular-nums" : ""}>{formatValue(c.unit, r[c.key])}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {result.truncated && <div className="tanya-note">Menampilkan {rows.length} dari {result.row_count} baris — unduh Excel untuk semua.</div>}
    </div>
  );
}

export function TanyaSummaryCards({ result }) {
  const metrics = (result?.columns || []).filter((c) => c.type === "metric" && !c.key.endsWith("_prev"));
  const cmp = result?.compare;
  const source = Object.keys(result?.totals || {}).length ? result.totals : result?.rows?.[0] || {};
  return (
    <div className="tanya-cards" data-testid={`tanya-cards-${result.result_id}`}>
      {metrics.map((c) => {
        const dp = cmp?.delta_pct?.[c.key];
        return (
          <div key={c.key} className="tanya-card" data-testid={`tanya-card-${c.key}`}>
            <div className="tanya-card-label">{c.label}</div>
            <div className="tanya-card-value tabular-nums">{formatValue(c.unit, source[c.key])}</div>
            {cmp && (
              <div className={`tanya-card-delta ${dp > 0 ? "up" : dp < 0 ? "down" : ""}`}>
                {dp === null || dp === undefined ? "Pembanding: " + formatValue(c.unit, cmp.totals?.[c.key]) : `${dp > 0 ? "+" : ""}${formatValue("pct", dp)} vs pembanding`}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
