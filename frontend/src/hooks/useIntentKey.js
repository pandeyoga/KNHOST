import { useRef } from "react";

/** Satu niat = satu Idempotency-Key. Kirim ulang isi sama (jaringan putus) memakai kunci sama; sukses, isi berubah,
 *  atau server sudah menjawab 4xx (keputusan bisnis) → kunci baru supaya percobaan berikutnya tidak membaca jawaban basi. */
export default function useIntentKey(prefix = "ik") {
  const ref = useRef({ body: null, key: "" });
  const keyFor = (payload) => {
    const body = JSON.stringify(payload);
    if (ref.current.body !== body) ref.current = { body, key: `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}` };
    return ref.current.key;
  };
  const done = () => { ref.current = { body: null, key: "" }; };
  const send = async (payload, fn) => {
    try { const r = await fn(keyFor(payload)); done(); return r; }
    catch (e) { if (e?.response && e.response.status < 500) done(); throw e; }
  };
  return { keyFor, done, send };
}
