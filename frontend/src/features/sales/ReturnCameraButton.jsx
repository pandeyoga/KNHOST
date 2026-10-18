import { useRef, useState } from "react";
import { Camera, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";

// Ambil foto langsung dari kamera HP (capture=environment) → tersimpan sebagai lampiran retur.
export default function ReturnCameraButton({ returnId, uploadUrl, onUploaded, testId = "return-camera-btn" }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const upload = async (file) => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file, file.name || `kamera-${Date.now()}.jpg`);
      const { data } = await axios.post(uploadUrl || `${API}/sales-returns/${returnId}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      onUploaded?.(data);
    } catch (e) { setErr(e.response?.data?.detail || e.message); } finally { setBusy(false); }
  };
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" data-testid={testId} disabled={busy} onClick={() => ref.current?.click()}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[#0058CC] px-3 py-1 text-xs font-semibold text-[#0058CC] hover:bg-[#0058CC0d] disabled:opacity-50">
        {busy ? <Loader2 size={12} className="spin" /> : <Camera size={12} />} Ambil foto
      </button>
      <input ref={ref} type="file" accept="image/*" capture="environment" className="hidden" data-testid={`${testId}-input`}
        onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
      {err && <span className="text-[11px] text-[#C62828]" data-testid={`${testId}-error`}>{err}</span>}
    </span>
  );
}
