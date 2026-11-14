/**
 * DeskEmptyQueues — antrean meja kerja yang KOSONG, dilipat menjadi SATU baris ringkas.
 *
 * Perapian Meja Finance (14 Nov 2026): 11 dari 13 kartu bernilai 0 tampil sebesar kartu berisi, sehingga
 * antrean yang benar-benar perlu ditindak tenggelam. KN_08 (progressive disclosure): yang kosong tetap
 * TERSEBUT (tidak ada antrean yang "hilang" diam-diam — pengguna bisa memastikan antrean X memang bersih),
 * tetapi hanya sebagai satu baris "N antrean kosong: …" yang bisa dibuka.
 *
 * Status = ikon + teks + warna (KN_37 §1.3): centang hijau + "antrean kosong/bersih" + angka 0.
 * Data apa adanya dari server — komponen ini tidak menghitung apa pun selain banyaknya antrean kosong.
 */
import { useId, useState } from "react";
import { CheckCircle2, ChevronDown } from "lucide-react";
import Collapse from "../../components/Collapse";

export default function DeskEmptyQueues({ queues, allEmpty = false, testPrefix = "desk", defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const listId = useId();
  const list = Array.isArray(queues) ? queues : [];
  if (!list.length) return null;

  const n = list.length;
  const names = list.map((q) => q?.label || q?.id).join(" · ");

  return (
    <section className="section-card" data-testid={`${testPrefix}-empty-fold`}
             data-all-empty={allEmpty ? "true" : "false"}>
      <div className="flex items-start gap-2.5 px-3 py-2.5">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-kn-success-soft">
          <CheckCircle2 size={16} className="text-kn-success-text" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-fs-13 font-bold text-kn-text" data-testid={`${testPrefix}-empty-fold-title`}>
            {allEmpty ? `Semua ${n} antrean bersih` : `${n} antrean kosong`}
            <span className="font-normal text-kn-text-2"> — tidak ada yang perlu ditindak</span>
          </p>
          {!open && (
            <p className="line-clamp-2 text-fs-12 text-kn-text-2 sm:line-clamp-1" title={names}
               data-testid={`${testPrefix}-empty-fold-summary`}>
              {names}
            </p>
          )}
        </div>
        <button type="button" className="ghost-button btn-sm shrink-0"
                aria-expanded={open} aria-controls={listId}
                onClick={() => setOpen((v) => !v)}
                data-testid={`${testPrefix}-empty-fold-toggle`}>
          {open ? "Sembunyikan" : "Tampilkan"}
          <ChevronDown size={14} aria-hidden="true"
                       className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
        </button>
      </div>

      <Collapse open={open}>
        <ul id={listId} data-testid={`${testPrefix}-empty-fold-list`}
            className="grid grid-cols-[minmax(0,1fr)] gap-x-6 border-t border-kn-divider px-3 py-1 xl:grid-cols-2">
          {list.map((q) => (
            <li key={q.id} className="flex items-start gap-2 py-2" data-testid={`${testPrefix}-empty-item-${q.id}`}>
              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-kn-success-text" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-fs-13 font-semibold text-kn-text">{q.label || q.id}</p>
                {q.hint && <p className="line-clamp-2 text-fs-12 text-kn-text-2">{q.hint}</p>}
              </div>
              <span data-testid={`${testPrefix}-count-${q.id}`} title="Tidak ada dokumen di antrean ini"
                    className="shrink-0 rounded-full bg-kn-success-soft px-2 text-fs-12 font-bold tabular-nums text-kn-success-text">
                {Number(q.count) || 0}
              </span>
            </li>
          ))}
        </ul>
      </Collapse>
    </section>
  );
}
