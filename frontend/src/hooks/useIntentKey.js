import { useRef } from "react";

/** Satu niat = satu Idempotency-Key: kirim ulang isi yang sama memakai kunci sama; isi berubah / sukses → kunci baru. */
export default function useIntentKey(prefix = "ik") {
  const ref = useRef({ body: null, key: "" });
  const keyFor = (payload) => {
    const body = JSON.stringify(payload);
    if (ref.current.body !== body) ref.current = { body, key: `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}` };
    return ref.current.key;
  };
  const done = () => { ref.current = { body: null, key: "" }; };
  return { keyFor, done };
}
