package id.kainnusantara.handheld.core;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Form Daftar Awal di C72 — field LENGKAP sama dengan form HP/desktop (`MobileRegistration.jsx` → `RegLineIn`):
 * bin, produk (atau "produk belum dikenali" + keterangan + foto), panjang + satuan, panjang dari label, lot, dye lot,
 * grade, PT pemilik, nomor roll lama, label mentah. Validasi lokal = cermin aturan server
 * ({@code initial_registration_lines.build_line}); server tetap memvalidasi ulang saat sinkron.
 */
public final class RegistrationForm {
    public String binId = "", binCode = "", productId = "", productLabel = "", note = "", qty = "", unit = "", lot = "",
            dyeLot = "", grade = "", ownerEntityId = "", oldRollNo = "", labelRaw = "", photoPath = "";
    public boolean unrecognized, lengthFromLabel;

    public List<String> validate(boolean needsEpc, String epc) {
        List<String> e = new ArrayList<>();
        if (binId.isEmpty()) e.add("Bin wajib dipindai/dipilih (alamat rak tempat roll ditemukan).");
        if (ownerEntityId.isEmpty()) e.add("PT pemilik wajib dipilih.");
        if (unrecognized) {
            if (note.trim().length() < 3) e.add("Produk belum dikenali: isi keterangan (warna/motif/kode di kain) minimal 3 huruf.");
        } else if (productId.isEmpty()) e.add("Produk wajib dipilih (atau tandai 'produk belum dikenali').");
        Double q = Parse.decimal(qty);
        if (!unrecognized && q == null) e.add("Panjang roll wajib diisi.");
        if (q != null && (q <= 0 || q > 100000)) e.add("Panjang roll wajib > 0 (dan masuk akal).");
        if (q != null && unit.isEmpty()) e.add("Satuan panjang wajib dipilih.");
        if (needsEpc && (epc == null || !Epc.valid(epc))) e.add("EPC tag belum ada — baca tag (24 hex).");
        return e;
    }

    /** Baris untuk batch `registration`. {@code written}=true: EPC sistem sudah ditulis & diverifikasi baca ulang. */
    public JSONObject toLine(String clientLineId, String epc, boolean written, String capturedAt) {
        Double q = Parse.decimal(qty);
        JSONObject o = Json.obj("client_line_id", clientLineId, "epc", epc, "written", written, "captured_at", capturedAt,
                "bin_id", binId, "owner_entity_id", ownerEntityId, "length_from_label", lengthFromLabel && q != null,
                "lot", lot.trim(), "dye_lot", dyeLot.trim(), "old_roll_no", oldRollNo.trim(), "label_raw", Parse.clip(labelRaw, 500));
        if (q != null) { Json.put(o, "qty", q); Json.put(o, "unit", unit); }
        if (!grade.trim().isEmpty()) Json.put(o, "grade", grade.trim().toUpperCase(java.util.Locale.ROOT));
        if (unrecognized) { Json.put(o, "unrecognized", true); Json.put(o, "note", note.trim()); }
        else { Json.put(o, "product_id", productId); if (!note.trim().isEmpty()) Json.put(o, "note", note.trim()); }
        return o;
    }

    /** Roll berikutnya di rak yang sama: bin, produk, satuan, PT, lot tetap; panjang & roll lama dikosongkan. */
    public void nextRoll() {
        qty = ""; lengthFromLabel = false; oldRollNo = ""; labelRaw = ""; photoPath = "";
        if (unrecognized) note = "";
    }
}
