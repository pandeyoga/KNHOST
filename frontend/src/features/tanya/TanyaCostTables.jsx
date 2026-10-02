import { fmtInt, fmtUsd } from "./tanyaFormat";

/** Rincian biaya per fitur / pengguna / model dalam rentang terpilih. */
export function TanyaCostTable({ title, nameLabel, rows, testId }) {
  return (
    <section className="tanya-cost-card section-card" data-testid={testId}>
      <div className="tanya-block-title">{title}</div>
      {!rows?.length ? (
        <div className="tanya-note">Belum ada data.</div>
      ) : (
        <div className="tanya-table-scroll">
          <table className="tanya-cost-table">
            <thead>
              <tr><th>{nameLabel}</th><th className="num">Biaya</th><th className="num">Porsi</th><th className="num">Panggilan</th><th className="num">Token</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} data-testid={`${testId}-row-${r.key}`}>
                  <td>{r.label}</td>
                  <td className="num">{fmtUsd(r.usd)}</td>
                  <td className="num">{r.share_pct == null ? "—" : `${r.share_pct.toLocaleString("id-ID")}%`}</td>
                  <td className="num">{fmtInt(r.calls)}</td>
                  <td className="num">{fmtInt(r.tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
