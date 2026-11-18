// Di dalam kontainer uji: localhost:3000 → frontend:3000 dan localhost:8001 → backend:8001 (jaringan compose kn-dev).
// Frontend dev memanggil backend di http://localhost:8001 (REACT_APP_BACKEND_URL) dan dev server menolak Host asing —
// jadi peramban di kontainer harus melihat keduanya di localhost, persis seperti di mesin pengembang.
//   KN_TERUSKAN="3000=frontend:3000,8001=backend:8001" node teruskan_port.js
const net = require("net");
const peta = (process.env.KN_TERUSKAN || "3000=frontend:3000,8001=backend:8001").split(",").map((x) => x.trim()).filter(Boolean);
for (const p of peta) {
  const [lokal, tujuan] = p.split("=");
  const [host, port] = tujuan.split(":");
  net.createServer((c) => {
    const s = net.connect(Number(port), host);
    c.pipe(s); s.pipe(c);
    const tutup = () => { c.destroy(); s.destroy(); };
    c.on("error", tutup); s.on("error", tutup);
  }).listen(Number(lokal), "127.0.0.1", () => console.log(`teruskan 127.0.0.1:${lokal} → ${host}:${port}`));
}
