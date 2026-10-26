/**
 * Fase 4 (26 Okt) — Esc menutup lapisan TERATAS walau pop-up induk diberi `onClose` inline.
 * Dulu `useEscapeClose` mendaftar ulang tiap identitas `onClose` berubah → induk naik ke atas anaknya.
 */
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { escapeLayerCount, useEscapeClose } from "../escapeLayers";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function Layer({ name, open, onClose, children }) {
  useEscapeClose(open, onClose);
  return open ? <div data-testid={name}>{children}</div> : null;
}

function Harness() {
  const [parent, setParent] = useState(true);
  const [child, setChild] = useState(false);   // anak dibuka BELAKANGAN (seperti pop-up di dalam pop-up)
  const [tick, setTick] = useState(0);
  return (
    <>
      <button type="button" data-testid="rerender" onClick={() => setTick(tick + 1)}>{tick}</button>
      <button type="button" data-testid="open-child" onClick={() => setChild(true)}>anak</button>
      {/* onClose INLINE: identitas baru di setiap render induk */}
      <Layer name="parent" open={parent} onClose={() => setParent(false)}>
        <Layer name="child" open={child} onClose={() => setChild(false)} />
      </Layer>
    </>
  );
}

const esc = () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
const q = (id) => document.querySelector(`[data-testid="${id}"]`);

test("Esc menutup anak dulu meski induk dirender ulang dengan onClose inline", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<Harness />); });
  await act(async () => { q("open-child").click(); });
  expect(escapeLayerCount()).toBe(2);

  await act(async () => { q("rerender").click(); });          // induk dirender ulang → onClose baru
  await act(async () => { q("rerender").click(); });
  expect(escapeLayerCount()).toBe(2);

  await act(async () => { esc(); });
  expect(q("child")).toBeNull();                               // lapisan teratas (anak) yang tertutup
  expect(q("parent")).not.toBeNull();

  await act(async () => { esc(); });
  expect(q("parent")).toBeNull();
  expect(escapeLayerCount()).toBe(0);
  act(() => root.unmount());
  host.remove();
});
