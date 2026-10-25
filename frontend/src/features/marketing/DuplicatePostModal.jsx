/** DuplicatePostModal — salin konten (caption, hashtag, platform, bahan) jadi ide baru dengan jadwal baru. */
import { useState } from "react";
import apiErrorText from "../../utils/apiError";
import { Copy } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNDateTimePicker from "../../components/KNDateTimePicker";
import { Field } from "../rnd/RndField";
import { mktApi, shiftDays } from "./marketingShared";

export default function DuplicatePostModal({ post, onClose, onDone }) {
  const nextWeek = post.publish_at ? `${shiftDays(post.publish_at.slice(0, 10), 7)}${post.publish_at.slice(10)}` : "";
  const [when, setWhen] = useState(nextWeek);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try { onDone(await mktApi.duplicate(post.id, { publish_at: when })); }
    catch (e) { setErr(apiErrorText(e, "Gagal menduplikat konten.")); } finally { setBusy(false); }
  };

  return (
    <FormModal open title={`Duplikat · ${post.title}`} subtitle="Caption, hashtag, platform, PIC & bahan disalin. Status kembali ke Ide; lampiran, performa & riwayat tidak ikut." icon={Copy}
      onClose={onClose} onSubmit={submit} busy={busy} error={err} submitLabel="Buat salinan" testId="mkt-duplicate-form" submitTestId="mkt-duplicate-submit" cancelTestId="mkt-duplicate-cancel">
      <Field label="Jadwal tayang salinan (boleh dikosongkan)">
        <KNDateTimePicker className="w-full" value={when} onChange={setWhen} data-testid="mkt-duplicate-publish-at" />
      </Field>
    </FormModal>
  );
}
