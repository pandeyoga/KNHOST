/**
 * RoleBaseControls — PR-T6: dua kontrol terpisah yang menggantikan "Salin dari peran" di editor peran, dan dua
 * dialognya.
 *  · **Peran dasar** (hanya peran kustom): nilai awal halaman awal, data yang terlihat, kategori kerja, dan menu warisan.
 *    Tidak menyalin hak akses. Mengganti peran dasar peran yang sudah ada meminta konfirmasi berisi daftar sifat yang
 *    mengikuti peran dasar sebelum dan sesudah.
 *  · **Salin hak akses dari…**: hanya menyalin centang; boleh diubah setelahnya.
 */
import { Copy, GitBranch } from "lucide-react";

import ConfirmModal from "../../../components/ConfirmModal";
import KNSelect from "../../../components/KNSelect";
import { HelpTip } from "../../../components/ListPageParts";

export const NO_BASE = "__tanpa__";
export const baseOptions = (roles) => [
  { value: NO_BASE, label: "Tanpa peran dasar" },
  ...(roles || []).filter((r) => !r.custom && !r.locked && r.id !== "admin").map((r) => ({ value: r.id, label: r.label })),
];
export const baseLabelOf = (roles, id) => (id ? ((roles || []).find((r) => r.id === id)?.label || id) : "tanpa peran dasar");

// Pola UI 16 Nov (M43) — dua pemilih dalam satu baris; kalimat penjelasnya pindah ke ikon ? (dulu paragraf di bawahnya).
export default function RoleBaseControls({ custom, roleId, baseRole, roles, disabled, onChooseBase, onCopy }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2" data-testid="role-editor-tools">
      {custom && (
        <div className="flex min-w-0 items-center gap-1.5" data-testid="role-editor-base">
          <span className="inline-flex shrink-0 items-center gap-1 text-fs-12 font-semibold text-kn-text"><GitBranch size={12} className="text-kn-action" /> Peran dasar</span>
          <HelpTip text="Menentukan nilai awal halaman awal, data yang terlihat, kategori kerja, dan menu warisan. Tidak menyalin hak akses."
                   testId="role-editor-base-help" label="Tentang peran dasar" />
          <KNSelect className="field min-w-0 flex-1" data-testid="role-editor-base-select" disabled={disabled}
                    value={baseRole || NO_BASE} options={baseOptions(roles)} aria-label="Peran dasar"
                    onValueChange={(v) => onChooseBase?.(v === NO_BASE ? "" : v)} />
        </div>
      )}
      {!disabled && (
        <div className="flex min-w-0 items-center gap-1.5" data-testid="role-editor-copy">
          <span className="inline-flex shrink-0 items-center gap-1 text-fs-12 font-semibold text-kn-text"><Copy size={12} className="text-kn-action" /> Salin dari</span>
          <HelpTip text="Salin hak akses dari peran lain: hanya menyalin centang tingkat & aksi; boleh diubah setelahnya."
                   testId="role-editor-copy-help" label="Tentang salin hak akses" />
          <KNSelect className="field min-w-0 flex-1" data-testid="role-editor-copy-from" value="" placeholder="pilih peran…"
                    onValueChange={onCopy} aria-label="Salin hak akses dari"
                    options={(roles || []).filter((r) => r.id !== roleId && r.id !== "admin").map((r) => ({ value: r.id, label: r.label }))} />
        </div>
      )}
    </div>
  );
}

/** Konfirmasi "Ganti peran dasar ke {label}?" — daftar `follows_base` sebelum & sesudah (dari pratinjau server). */
export function BaseChangeDialog({ ask, roles, onCancel, onConfirm }) {
  const list = (xs) => ((xs || []).length ? xs : ["Tidak ada — semua sifat diisi sendiri."]);
  const message = (
    <>
      <span className="block">Hak akses tidak berubah. Sifat yang belum diisi sendiri dan menu warisan ikut peran dasar baru.</span>
      <span className="mt-1 block font-semibold" data-testid="role-editor-base-confirm-before">Sebelum: {list(ask.before).join("; ")}</span>
      <span className="block font-semibold" data-testid="role-editor-base-confirm-after">
        Sesudah: {ask.after === null ? "memuat…" : list(ask.after).join("; ")}
      </span>
    </>
  );
  return (
    <ConfirmModal open title={`Ganti peran dasar ke ${baseLabelOf(roles, ask.to)}?`} message={message}
                  confirmLabel="Ya, ganti" testId="role-editor-base-confirm" onCancel={onCancel} onConfirm={onConfirm} />
  );
}

/** Sesudah lintas PT dimatikan: akun peran ini yang masih ditugaskan ke lebih dari satu PT (tidak diubah otomatis). */
export function AccountsReviewDialog({ accounts, onClose, onOpenAccounts }) {
  const message = (
    <>
      <span className="block">Peran ini tidak lagi membuka semua PT. Akun berikut masih ditugaskan ke lebih dari satu PT —
        penugasannya tidak diubah otomatis.</span>
      {accounts.map((a) => (
        <span key={a.id} className="mt-0.5 block" data-testid="role-editor-review-item"><b>{a.name}</b> — {(a.allowed_entities || []).join(", ")}</span>
      ))}
    </>
  );
  return (
    <ConfirmModal open title="Tinjau penugasan PT" message={message} cancelLabel="Tutup"
                  confirmLabel={onOpenAccounts ? "Buka Akun & Akses" : "Selesai"} testId="role-editor-review"
                  onCancel={onClose} onConfirm={onOpenAccounts || onClose} />
  );
}
