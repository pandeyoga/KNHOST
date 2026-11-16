// Jest (CRA) tidak membaca peta `exports` bersyarat paket. `@radix-ui/react-use-controllable-state` (dipakai cmdk →
// KNSelect/Combobox) mengimpor "@radix-ui/primitive/is-development" yang hanya ada lewat peta itu, sehingga setiap
// suite yang memuat KNSelect versi Combobox gagal dimuat ("Cannot find module"). Isinya sama dengan berkas aslinya.
exports.IS_DEVELOPMENT = process.env.NODE_ENV !== "production";
