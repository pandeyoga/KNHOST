// Lingkungan jest "perangkat berzona UTC" — untuk uji tanggal bawaan WIB (15 Nov).
//
// Pakai lewat docblock di berkas uji:  /** @jest-environment <rootDir>/jest/utcDeviceEnvironment.js */
//
// Zona waktu proses worker diganti ke UTC selama berkas uji itu berjalan, lalu DIPULIHKAN saat teardown supaya
// berkas uji lain di worker yang sama tidak terpengaruh. Tujuannya: uji tetap bermakna di mesin mana pun — di mesin
// berzona WIB, kode yang (salah) memakai jam lokal kebetulan benar, sehingga regresinya tidak akan tertangkap.
// Node mengikuti perubahan `process.env.TZ` saat berjalan (Date & Intl membaca ulang zona).
/* global require, process, module */   // modul Node (CommonJS), dimuat jest-runner di luar sandbox uji
const JsdomEnvironment = require("jest-environment-jsdom");

class UtcDeviceEnvironment extends JsdomEnvironment {
  async setup() {
    this.prevTz = process.env.TZ;
    process.env.TZ = "UTC";
    await super.setup();
  }

  async teardown() {
    if (this.prevTz === undefined) delete process.env.TZ;
    else process.env.TZ = this.prevTz;
    await super.teardown();
  }
}

module.exports = UtcDeviceEnvironment;
