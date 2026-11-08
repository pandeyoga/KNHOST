# Hardware identity & capabilities (reader "U300/UR300", antenna "Ant-RC12-455/455", tag "R6P") and Indonesian UHF RFID regulation

Researcher notes, 27 Oct 2026. Notes are in English; the final report is in Indonesian.
Labels used below: **[VERIFIED]** means a primary or vendor source states it. **[SECONDARY]** means only a reseller or consultant states it. **[SNIPPET]** means it was seen only in a search-result excerpt, because the page could not be fetched. **[ASSUMED]** means it is my inference.

---

## Q1. Which reader is "U300" / "UR300", and what can it do?

### Takeaway
The likely match is the **Chainway U300 Fixed RFID Reader (Android 11)**. Resellers sell the same unit as "Chainway UR300". The antenna code "Ant-RC12-…" is also a Chainway code, so the whole kit is probably Chainway. The U300 has 4 or 8 RP-TNC ports, an Impinj E-series engine with Gen2X, 5–30 dBm output, RSSI, antenna ID, 4 isolated GPI and 4 GPO, and an on-device Java/Android SDK. LLRP, phase, Doppler, per-antenna power, session/target control and dwell control are **not documented** anywhere I could reach.

### Cited Findings
**Identity / naming**
- Chainway sells a product called "U300 Fixed RFID Reader (Android 11)" on its own site [VERIFIED] — [Chainway U300 product page](https://www.chainway.net/Products/Info/146)
- A reseller (IDCRAFT) uses "U300" in the product title and "UR300" in the description and URL for the same Chainway unit. Its SKUs are **U34-U7E-R2A11** (4 ports, tied to EU 865–868 MHz) and **U38-U7C-R2A11** (8 ports, tied to FCC 902–928 MHz). The 8-port option costs €10 more [SECONDARY] — [IDCRAFT Chainway UR300](https://idcraft.shop/en/shop/chainway-ur300-fixed-rfid-reader-269)
- A 4-port U300 SKU is sold with "4 x RP-TNC female connectors (50Ω)" [SNIPPET] — [autoidstore Chainway U300 4-Port](https://autoidstore.com/product/chainway-u300-4-port-version-high-performance-fixed-uhf-rfid-reader/?v=7885444af42e). Another kit listing has 8 antenna ports [SNIPPET] — [barcode-arena U300 kit](https://www.barcode-arena.com/chainway-u300-fixed-mount-rfid-reader.html)
- Chainway's support page for the U300 links a "U300 User Manual" and SDK packages: "UHFAPP for JAVA (Windows/Linux)", "UHF for Android Studio" and a dated API package for Android Studio [SNIPPET] — [Chainway support U300](https://www.chainway.net/support/Info/36)
- Other "U300"-like names exist. RFIDLabel sells a "UHF RFID Reader AZ-U300" (4-port), which may be a rebadge from the same supplier family as the AZ-12dBi antenna below [SNIPPET; not checked] — [rfidlabel AZ-U300](https://www.rfidlabel.com/product/uhf-rfid-reader-az-u300/). Unitech sells an "RM300", a different product [SNIPPET] — [logiscenter Unitech RM300](https://www.logiscenter.us/unitech-rm300-rfid). Searches for "U300/UR300" turned up **no** reader of that name from Hopeland, Chafon, Invengo, Senrui, Jietong or Fonkan. That is absence of evidence, not proof.

**Official U300 spec (datasheet "Model: U300 / Update Date: 2025-09-15") [VERIFIED]** — [U300 datasheet (Osiris copy)](https://www.osiris.co.za/web/content/18049?unique=70a6a0e2a478c6b6df99a7a082d7829c361e1f22&download=true); same values on the [Chainway product page](https://www.chainway.net/Products/Info/146)
- OS Android 11, quad-core 2.0 GHz, 2 GB + 16 GB. The product page says 2 GB + 32 GB, so the two sources conflict on storage.
- RFID engine: "Based on Impinj E Series chips". Impinj Gen2X: "Supported". Protocol: EPCglobal Class 1 Gen 2 / ISO 18000-6C.
- Frequency: "865-868 MHz / 920-925 MHz / 902-928 MHz".
- Output power: "1W (30dBm, support +5~+30dBm adjustable, POE/DC power)", with an optional 2 W (33 dBm, +10~+33 dBm, "for Latin America"). Output power precision ±1 dB, flatness ±0.2 dB. **The step size is not stated.**
- Receive sensitivity "< -84dBm". Fastest read rate "1300+ tags/sec". RSSI "Supported". Antenna Detector "Supported". Ambient Temp Monitor "Supported".
- Antenna port: "4 / 8 Channel 50Ω RF Connector RP-TNC Female". Supported antennas include "6dBic, 9dBic, etc."
- GPIO: "4 x input optocouplers, 4 x output optocouplers, with isolation".
- Interfaces: 10/100 Ethernet RJ45, 1× RS-232, 1× USB Host, 1× USB Device, HDMI (720p), Wi-Fi 802.11 b/g/n 2.4 GHz, Bluetooth 4.0. Baud rate 115200.
- Power: DC 10–24 V, PoE 802.3af 13 W, PoE+ 802.3at 25.5 W. Operating temperature −25 to 65 °C. Size 247×151×35 mm.
- SDK: "Support Software Development Kit", language Java, tools Eclipse/Android Studio. **The datasheet does not mention LLRP, phase, session/target or dwell.**

**Which Impinj E-series chip? (conflicting)**
- A Cisper copy of the U300 datasheet reportedly says "based on the Impinj E710/ R2000 chip" [SNIPPET; domain unreachable] — [Cisper U300 datasheet](https://www.cisper.com/datasheets/Chainway/Chainway_U300_datasheet.pdf). IDCRAFT says "Impinj E710" [SECONDARY] — [IDCRAFT](https://idcraft.shop/en/shop/chainway-ur300-fixed-rfid-reader-269).
- Impinj's E-family spec table lists receive sensitivity of −103 / −98 / −93 / −84 dBm for E910 / E710 / E510 / E310, and an E710 maximum of 700 tags/s [SNIPPET] — [Impinj E Family spec table](https://www.impinj.com/getmedia/a05f7254-1433-4a54-bd04-9eaa3cb387d6/Impinj-ProductBrief-E-Family-SpecTable-010225.pdf). Chainway's "< −84 dBm" figure matches the E310 row, not the E710 row, and Chainway's "1300+ tags/s" is higher than the E710 brief figure. The exact chip is unconfirmed.

**Behaviour of the sister product URA4 (Android fixed 4-port reader; the manual Chainway links is titled "URA4 User Manual") [VERIFIED for URA4, ASSUMED similar for U300]** — [Chainway URA4 user manual](https://www.chainway.net/upload/download/c213d762-d356-412b-8e76-35604dc6ca3d.pdf)
- The demo app shows "EPC or TID, Count, RSSI and Ant. number" per tag. That is the report-field set visible in the vendor UI.
- Filter: "user could setup address, data length to filter tags. EPC, TID and USER areas can be selected". This is a Gen2 Select mask.
- "User could setup different frequency band for different countries" (Set/Get Frequency).
- "User could select different output power from 5 to 30dBm" (Set/Get Power). The UI shows **one** power setting. Per-antenna power is not shown.
- "Select ANT1-ANT8 to setup antenna, selected antenna will start functioning, unselected antenna will in OFF". This is per-port enable/disable.
- There are "two protocols" to choose from, an "RF link" setting with four selectable parameters, and ON/OFF toggles for **tagFocus** and **FastID** ("Open the EPC and TID").
- Session (S0–S3), target (A/B), Q, dwell time and phase are **not mentioned** in the manual.
- Its EU declaration lists the RFID 865–868 MHz ERP as 27.65 dBm, which is the URA4 test result.

**Other Chainway fixed readers (for comparison)**
- Chainway UR4 is a non-Android 4-port fixed reader whose "core module adopts the Impinj E710 / R2000 chip" [SNIPPET] — [Cisper UR4](https://www.cisper.com/en/chainway-ur4-fixed-uhf-reader). It has RS-232 and RJ45 [SNIPPET] — [Cleverence Chainway RFID](https://www.cleverence.com/hardware/rfid/stationary-rfid-readers/chainway-rfid/).
- An open-source Python library for the Chainway UR4 was "tested with a UR4 running UHF module firmware 7.40.1 over RS-232 and TCP", using `socket://host:8888`. Its example prints `tag.epc` and `tag.rssi` [VERIFIED for UR4] — [DaanVervacke/chainway-serial](https://github.com/DaanVervacke/chainway-serial). A search snippet said it supports "phase reporting", but the fetched README did not show this. The two disagree.
- A middleware vendor (Cleverence) maps Chainway reads to `TagId`, `PeakRSSI`, `AntennaId` and says "configure session and target tag count in the RFID profile". This refers to handhelds, not the U300 [SECONDARY] — [Cleverence Chainway docs](https://www.cleverence.com/platform/docs/auto-id/vendors/chainway)

### Inferences
- [ASSUMED, strong] The user's "U300/UR300" is the Chainway U300. The antenna part number (Ant-RC12-…), the "UR300" alias used by resellers and the RP-TNC/Android form factor all point to one Chainway kit.
- [ASSUMED] The U300 is an **Android computer with an internal UHF module**. ERP integration will probably mean an Android app on the reader built with the Chainway Java SDK, which then pushes reads to the ERP over HTTP/MQTT/WebSocket. The alternative is the "UHFAPP for JAVA (Windows/Linux)" package talking to the module from a PC. **No LLRP is documented**, so a generic LLRP client (Impinj Octane-style) should not be assumed.
- [ASSUMED] Capabilities the hardware family supports (E-series and Gen2X: TagFocus, FastID, Select filters) are confirmed only at the demo-app level. Whether the **SDK** exposes per-antenna power, session/target, dwell time, phase or channel per read must be checked in the SDK javadoc.
- [ASSUMED] The "920–925 MHz" region on the U300 is likely the China plan. Part of it (923–925 MHz) is outside Indonesia's current 920–923 MHz allocation (see Q4), so a region/hopping table limited to 920–923 MHz is needed.

### Gaps
- Exact SKU, firmware and region lock of the user's unit. **The user must check:** the label on the device (model and SKU, e.g. U34-U7E-R2A11 = EU), the "About" screen or UHF module firmware version, the list of selectable frequency regions, and whether a custom 920–923 MHz hopping table can be set.
- Not confirmed from any source: per-antenna power, power step size (probably 1 dB, unverified), dwell/sequence control, session/target/Q settings, and per-read phase, Doppler, channel or timestamp. Fully documented in sources: RSSI, antenna number and read count. Needs the SDK javadoc or the U300 user manual, which I could not retrieve.
- Whether the U300 supports an over-the-network host protocol (TCP port, MQTT, HTTP push) without a custom Android app.
- Which E-series chip is inside (E310, E510 or E710). This matters for sensitivity and for Gen2X features.

---

## Q2. Antenna "Ant-RC12-455/455-CA(EU)": vendor, pattern, band variants

### Takeaway
"Ant-RC12-455/455-EU" is a **Chainway** 12 dBi panel antenna, 445×445×30 mm, N-type, IP67, now listed as discontinued at a UK reseller. A rebadged datasheet with the same mechanical codes gives right-hand circular polarisation, 40° H / 38° V beamwidth, 17 dB front-to-back ratio, VSWR 1.3, 50 Ω, 20 W maximum input and an **860–960 MHz** band. That suggests the radiator may be broadband, but the vendor sells region-labelled SKUs (EU 865–868; an Indonesian listing shows 902–928). Performance at 920–923 MHz for the EU SKU is unverified.

### Cited Findings
- "Chainway Ant-RC12-455/455-EU": "UHF RFID Antenna 865-868MHz (EU)", 12 dBi, 445 × 445 × 30 mm (the title says 455×455), 2.66 kg with bracket, IP67, "N-type male connecting cable required", "Low Front to back Ratio, narrow Sidelobe", marked "THIS PRODUCT IS NOW DISCONTINUED". No beamwidth, VSWR or polarisation is stated [SECONDARY] — [Global Barcode UK](https://www.globalbarcode.co.uk/product/chainway-ant-rc12-455-455-eu-12dbi-antenna-455x455mm)
- Rebadged datasheet "AZ-12dBi" (PDF title "Ant-RC12-RC", pole bracket "Ant-MOT-RC12-455/455-P", cables "Ant-CA-SMA.M/N.M-LMR2-1M / -5M / -15M, LMR4-5M / -15M") [SECONDARY] — [rfidcard.com AZ-12dBi datasheet](https://www.rfidcard.com/wp-content/uploads/2025/02/UHF-RFID-Antenna12dBi-datasheet-AZ-12dBi.pdf):
  - Operating frequency 860–960 MHz; ISO/IEC 18000-6C
  - Horizontal beamwidth 40°, vertical 38°
  - Polarisation: "Circular Polarization (right-handed)"
  - VSWR 1.3; gain 12 dBi; front-to-back ratio 17 dB; impedance 50 Ω; max input 20 W
  - −40 to +60 °C; DC-grounded lightning protection; wind 60 m/s; pole mount on a 30–50 mm rod
  - 445×445×30 mm, 2.66 kg, ABS radome, aluminium radiating plate, **N female** connector, IP67
  - (The PDF text extracts as two misaligned columns. I paired labels and values by their order. The search engine independently returned the same pairing: "40° horizontal and 38° vertical beamwidths, front-to-back ratio of at least 17 dB … 860-960 MHz".)
- An Indonesian marketplace listing, "12dBi Panel Antenna UHF RFID Ant-RC12 – ORIGINAL Chainway RC12", gives right-hand circular polarisation, **902–928 MHz** and 455×455 mm, and links a vendor datasheet named "12dBi-Ant-RC12-455-EN.pdf" [SNIPPET; page timed out] — [Tokopedia Warehouse Electronic](https://www.tokopedia.com/warehouseelectronic/12dbi-panel-antenna-uhf-rfid-ant-rc12-original-chainway-rc12-antena-panel-1730990266465290047)
- In Chainway's accessory naming, "Ant-CA-…" is the **cable** prefix (e.g. "Ant-CA-SMA.M/N.M-LMR2-1M") [SECONDARY] — [rfidcard.com AZ-12dBi datasheet](https://www.rfidcard.com/wp-content/uploads/2025/02/UHF-RFID-Antenna12dBi-datasheet-AZ-12dBi.pdf)
- The U300's antenna ports are **RP-TNC female** [VERIFIED] — [U300 datasheet](https://www.osiris.co.za/web/content/18049?unique=70a6a0e2a478c6b6df99a7a082d7829c361e1f22&download=true). The URA4 manual says the feeder cable is "SMA male side connects with device" [VERIFIED for URA4] — [URA4 manual](https://www.chainway.net/upload/download/c213d762-d356-412b-8e76-35604dc6ca3d.pdf)
- The market has both dual-region and single-region panels. Examples: RFMAX S9028PCR/S8658PCR is sold as separate FCC and ETSI SKUs; Green Futurz LM750-ETSI is 865–868 MHz only, 6.5 dBi, F/B 22 dB, VSWR 1.40:1 [SNIPPET] — [atlasRFIDstore RFMAX](https://www.atlasrfidstore.com/rfmax-s9028pcr-s8658pcr-rhcp-indoor-rfid-antenna-fcc-etsi/), [everythingRF LM750-ETSI](https://www.everythingrf.com/products/rfid-antennas/green-futurz/828-2495-model-lm750-etsi)

### Inferences
- [ASSUMED] "-CA(EU)" in the user's brief probably merges the antenna SKU "Ant-RC12-455/455-EU" with Chainway's cable prefix "Ant-CA-…". The user should check the antenna label and the cable separately.
- [ASSUMED, important] The listed Chainway cables are SMA-to-N (made for URA4-type SMA ports). The **U300 needs RP-TNC (male) to N (male)** cables. A wrong adapter chain adds loss and mismatch. Real cable loss is also needed for the EIRP calculation in Q4.
- [ASSUMED, engineering expectation, not sourced] 920–923 MHz is about 6.4% above the 866.5 MHz centre of the EU band. If the EU SKU is a narrow-band patch tuned to 865–868 MHz, expect higher VSWR (more reflected power, which some readers flag as an antenna fault), lower gain and a worse axial ratio at 920–923 MHz. The 860–960 MHz / VSWR 1.3 rebadge sheet suggests the RC12 radiator may be broadband. Even so, the antenna should be **measured with a VNA or the reader's reflected-power/antenna-detector readout at 920–923 MHz**, or swapped for a 902–928 / 920–925 SKU.
- [ASSUMED] For stray-read control, the useful pattern facts are: 40°/38° half-power beamwidth (a fairly narrow beam for a gate), 17 dB F/B (energy behind the panel is only ~17 dB down, so tags behind a side panel can still be read at high power), and RHCP (orientation-tolerant but no polarisation discrimination). A 12 dBi side-pair facing each other across the gate will also reach well beyond the opposite panel unless power is cut.

### Gaps
- Chainway's own datasheet for "Ant-RC12-455/455" (any region) was not retrieved, so axial ratio, regional VSWR curves, sidelobe level and whether "12 dBi" is really dBic are unknown.
- Whether Chainway sells an Indonesia/920–925 SKU of the RC12 (a "-CN"/"-US"/"-JP" suffix) is not confirmed.
- No measured gain or VSWR for the EU SKU at 920–923 MHz exists in any source.

---

## Q3. Tag "R6P": Impinj Monza R6-P and ~70×20 mm inlays

### Takeaway
"R6P" is common shorthand for the **Impinj Monza R6-P** tag chip (label SKUs use it, e.g. "RS-R6P-…"). Its datasheet gives read sensitivity up to −22.1 dBm and write sensitivity up to −17.3 dBm with a dipole antenna, up to 128-bit EPC, 96-bit serialized TID and 32/64-bit user memory. It supports AutoTune, Integra, Enduro, TagFocus and FastID, plus a **short-range mode bit**. The exact 70–73×20 mm inlay was not identified. The closest published R6-P inlay is the Beontag E62 (die-cut 74×20 mm, antenna 70×14 mm).

### Cited Findings
- Monza R6-P datasheet (IPJ-W1710-K00, Version 2.0, © 2016) [VERIFIED] — [Impinj Monza R6-P datasheet (rfidfuture copy)](https://www.rfidfuture.com/wp-content/uploads/2020/12/Monza-R6-P.pdf):
  - "read sensitivity of up to -22.1 dBm with a dipole antenna"; "write sensitivity of up to −17.3 dBm with a dipole antenna"; memory write 1.6 ms per 32 bits.
  - Memory: up to 128-bit EPC (default profile 128-bit EPC with 32-bit user; max-user profile 96-bit EPC with 64-bit user); 96-bit serialized TID with a 48-bit serial number; 32-bit kill and access passwords.
  - Features: Integra (encoding diagnostics), AutoTune ("maintains performance across different dielectrics"), Enduro, FastID ("2x to 3x faster EPC+TID inventory"), and TagFocus ("suppresses previously read tags to enable capture of more tags").
  - Carrier frequency 860–960 MHz (Gen2).
  - **Short range:** "When a reader writes the S bit to a one the tag will only respond when it is near the reader." The bit can be changed only in the secured state (with the access password).
- Third-party listing: read −22.1 dBm, write −17.3 dBm [SECONDARY] — [everythingRF Monza R6-P](https://www.everythingrf.com/products/rfid-tag-ics/impinj/829-670-monza-r6-p). A v7.0 (2021) R6-P datasheet exists; a search excerpt quotes a test-condition table value "Chip Read Sensitivity −20 dBm" at 25 °C [SNIPPET] — [Impinj Monza R6-P datasheet v7.0 (wontec copy)](https://www.wontec.com.tw/wp-content/uploads/2023/07/Impinj-Monza-R6-P-Tag-Chip-Datasheet-V7-20210514.pdf). An older R6 datasheet lists write sensitivity −18.8 dBm, which conflicts with −17.3 dBm [SNIPPET].
- Impinj's Monza R6 series brief lists the R6-P with 96/128-bit EPC, 32/64-bit user memory, AutoTune, Integra, Enduro, TagFocus and FastID [SNIPPET] — [Impinj Monza R6 Series](https://impinj.com/products/tag-chips/impinj-monza-r6-series), [R6 Series Product Brief 2021](https://support.impinj.com/hc/article_attachments/4412854668051/Impinj-Monza-R6-Series-Product-Brief-121421.pdf). A later (2024) Impinj brief surfaced in search reportedly carries an **end-of-life notice** for Monza R6. The excerpt was truncated [SNIPPET, unverified].
- Converters use "R6P" as a label SKU token, e.g. "RS-R6P-PP-3221" (Impinj Monza R6-P, 32×21 mm) and "RS-R6P-CP-4B2" [VERIFIED as naming practice] — [rfidsolution R6-P label 32×21](https://rfidsolution.com/wp-content/uploads/2026/01/UHF-RFID-Label-PP-Synthetic-Paper-Impinj-Monza-R6-P-32-21-mm-datasheet-RS-R6P-PP-3221.pdf), [rfidsolution R6-P label 4×2 in](https://rfidsolution.com/wp-content/uploads/2026/01/UHF-RFID-Label-Coated-Paper-Impinj-Monza-R6-P-4-2-inch-datasheet-RS-R6P-CP-4B2.pdf)
- Beontag E62 wet inlay (Monza R6-P): die-cut 74×20 mm, antenna 70×14 mm. "RF Sensitivity: -84 dBm" looks like a reader value, not a tag value. "Max Read Distance: Testing recommended" [SNIPPET] — [atlasRFIDstore Beontag E62](https://www.atlasrfidstore.com/beontag-e62-rfid-wet-inlay-monza-r6-p/)
- Avery Dennison's Bling (Monza R6-P) datasheet gives performance as graphs and notes they are indicative [SNIPPET] — [Avery Dennison Bling R6-P](https://rfid.averydennison.com/content/dam/rfid/en/products/rfid-products/data-sheets/datasheet-Bling-Monza-R6-P.pdf)

### Inferences
- [ASSUMED] A label of about 70–73×20 mm is a common ~70×14 mm "belt"-type R6-P inlay (E62-class) converted to a ~74×20 mm label face. Read range depends on the inlay antenna and on the fabric roll (dielectric and stacking). AutoTune helps only partly.
- [ASSUMED, relevant to stray reads] Chip features usable for mitigation:
  - **TagFocus** cuts repeated reads of strong tags in session 1, so read count is less informative as a proximity cue.
  - **FastID** returns the TID alongside the EPC, which gives a unique key for de-duplication.
  - The **short-range bit** would shrink read range for *all* readers, including the gate, so it is generally unsuitable for gate pass-through. Mentioned only for completeness.
  - **Higher chip sensitivity** (−22.1 dBm) means tags wake up at low field strength, which makes stray reads at distance *more* likely at high reader power.

### Gaps
- The exact inlay vendor and model behind the user's "R6P" ~70–73×20 mm label, and its datasheet sensitivity and read range. **The user must check:** the label supplier's datasheet. Or read the TID with the reader: the TID model number identifies the chip as R6-P, and the label supplier identifies the inlay.
- Impinj's current lifecycle status for the R6-P (possible EOL) is unverified.

---

## Q4. Indonesian regulation for UHF RFID (band, power, certification) and implications of EU-variant gear

### Takeaway
UHF RFID in Indonesia is a **Short Range Device under class licence (izin kelas)** in **920–923 MHz**, limited to **≤ 400 mW EIRP (≈26.02 dBm EIRP)**. Every device type must carry an **SDPPI type-approval certificate**. The 2019 technical rule (Perdirjen SDPPI 161/2019) also allowed >400 mW to ≤2 W EIRP under a station licence (ISR), but only for electronic road pricing. The current technical standard (Kepmen Kominfo 260/2024, effective 11 Aug 2024) reportedly **removed that ISR RFID category** and keeps 920–923 MHz at ≤26.02 dBm EIRP. A 30 dBm reader into a 12 dBi antenna (~40+ dBm EIRP) is **far above** this limit.

### Cited Findings
**Framework (primary)**
- Permenkominfo No. 2 Tahun 2023 (izin kelas) [VERIFIED] — [JDIH Komdigi page](https://jdih.komdigi.go.id/produk_hukum/view/id/862/t/peraturan+menteri+komunikasi+dan+informatika+nomor+2+tahun+2023), [PDF](https://jdih.komdigi.go.id/produk_hukum/unduh/id/862/t/peraturan+menteri+komunikasi+dan+informatika+nomor+2+tahun+2023):
  - Ditetapkan 21 March 2023, diundangkan 12 April 2023, status Berlaku. It revokes Permenkominfo 1/2019 and 16/2016.
  - Pasal 5: the SRD group includes "c. Radio Frequency Identification (RFID)".
  - Lampiran I: "920 – 923 MHz — SRD, RLAN, IMT Berbasis Izin Kelas".
  - Lampiran II §III (SRD): for 920–923 MHz, maximum transmit power is "Sesuai dengan Standar Teknis yang berlaku", i.e. deferred to the technical standard.
  - Pasal 11: devices traded or used in Indonesia "wajib memenuhi Standar Teknis". The standard is set by Keputusan Menteri, and compliance "dibuktikan dengan Sertifikat". Users must follow the operational terms in Lampiran II.
  - For comparison, LPWAN at 920–923 MHz is 400 mW (26 dBm) for a gateway and 100 mW (20 dBm) for an end node.
- A draft amendment (Permen Komdigi "Perubahan atas Permenkominfo 2/2023") still lists 920–923 MHz as SRD [VERIFIED draft] — [JDIH Komdigi draft](https://jdih.komdigi.go.id/dokumen-pembentukan-puu/unduh/52). Permen Komdigi No. 2 Tahun 2025 amends Permen 2/2023 [SNIPPET] — [Klaussa](https://www.klaussa.com/peraturan/permen-no-2-tahun-2025-peraturan-menteri-komunikasi-dan-digital-nomor-2-tahun-2025-tentang-perubahan)

**Technical standard 2019 (primary, now superseded)** — [Perdirjen SDPPI No. 161 Tahun 2019 (postel.go.id)](https://postel.go.id/downloads/42/20210510125749-perdirjen_2019-161_SRD.pdf) [VERIFIED]
- Tabel 2.4 (RFID): "920 – 923 MHz: ≤ 400 mW EIRP". Test standards: "FCC Part 15 §15.249 and ANSI C63.10-2013; atau EN 300 220-1 atau EN 302 208".
- "Alat dan/atau Perangkat Telekomunikasi RFID yang menggunakan kuat medan/daya pancar > 400 mW EIRP dan ≤ 2 000 mW EIRP pada pita frekuensi radio 920-923 berbasis Izin Stasiun Radio (ISR)". Tabel 2.5 lists the application as "Jalan Berbayar Elektronik".

**Technical standard 2024 (current)**
- Kepmen Kominfo No. 260 Tahun 2024, "Standar Teknis Short Range Devices", is listed on the regulator site with a PDF. The PDF is a **scanned image**, so its text could not be extracted here [VERIFIED listing] — [postel.go.id Keputusan Menteri list](https://www.postel.go.id/regulasi-keputusan-menteri-39), [Kepmen 260/2024 PDF](https://www.postel.go.id/downloads/39/20250208102841-kepmen_2024-260_Standar_Teknis_SRD.pdf)
- Issued 13 May 2024; effective and mandatory 11 August 2024 [SECONDARY] — [CAICT GMA](https://gma.caict.ac.cn/en/update/57/534). It supersedes Perdirjen 161/2019 and became enforceable 90 days after issuance [SNIPPET] — [TÜV SÜD e-ssentials 5/2024](https://www.tuvsud.com/en-gb/e-ssentials-newsletter/consumer-products-and-retail-essentials/e-ssentials-5-2024/indonesia-technical-standards-for-telecommunications-equipment-and-short-range-radio-devices)
- RFID limits under Kepmen 260/2024: **"920–923 MHz: ≤ 26,02 dBm EIRP"**, test standards FCC 15.247/15.249/15.209, ANSI C63.10, EN 300 220, EN 302 208. It also adds 433–434.79 MHz at ≤20 dBm ERP and 2400–2483.5 MHz at ≤20 dBm EIRP. It replaces Kepdirjen 214/2005, 221/2007 and Perdirjen 161/2019 [SECONDARY, test-lab consultant] — [Narmadi: Standar Pengujian RFID](https://narmadi.co.id/standar-pengujian-rfid/)
- Changes for RFID: "penambahan pita frekuensi 433-434,79 MHz dan 2 400–2 483,5 MHz" and "**penghapusan RFID dengan ISR**" [SECONDARY] — [sertifikatsdppi.id](https://sertifikatsdppi.id/2024/06/28/standar-teknis-srd-dalam-kepmen-kominfo-nomor-260-tahun-2024/)
- Conflicting secondary source: Alphabet Compliance reportedly lists ≤20 dBm EIRP for 920–923 MHz. A search summary called that table garbled (WPT row) [SNIPPET; site certificate expired] — [Alphabet Compliance](http://www.alphabetcompliance.com/sys-nd/2234.html). CAICT's summary lists 920–923 MHz under WPAN and 433/2400 MHz under "RFID". That reads as a list of *additions*, not a removal of 920–923 MHz from RFID — [CAICT GMA](https://gma.caict.ac.cn/en/update/57/534)

**Certification evidence (primary)**
- An example SDPPI certificate for a UHF RFID head (Pepperl+Fuchs IUH-F190-V1-FR2-16) has **No. 96692/SDPPI/2024**, dated 15 Jan 2024. It is issued through OSS as a PB-UMKU to the Indonesian importer, references Perdirjen SDPPI 161/2019, and states "RFID: 920 MHz – 923 MHz; Daya Pancar: < 400 mW EIRP" [VERIFIED] — [Pepperl+Fuchs SDPPI certificate](https://files.pepperl-fuchs.com/webcat/navi/productInfo/cert/cert6014a.pdf)
- Testing is done at a Kominfo-designated lab. A passing product gets an SDPPI certificate allowing legal sale in Indonesia [SECONDARY] — [Narmadi](https://narmadi.co.id/standar-pengujian-rfid/)

**Historical (no longer current)**
- GS1's 2013 table: "Indonesia: 923-925 MHz @ 2 W ERP" [SNIPPET] — [GS1 UHF regulations](https://www.gs1.org/docs/epc/uhf_regulations.pdf). 221/DIRJEN/2007 gave 923–925 MHz at < 2000 mW ERP [SNIPPET] — [InCompliance](https://incompliancemag.com/rfid-regulations-and-certification-procedures-in-emerging-asian-markets/). RFID Journal also cites 923–925 MHz at 2 W ERP [SNIPPET] — [RFID Journal](https://www.rfidjournal.com/?p=183059). These are superseded by the 920–923 MHz / 400 mW EIRP regime above.

### Inferences
- [ASSUMED, arithmetic] EIRP ≈ conducted power (dBm) − cable loss (dB) + antenna gain (dBi). With a 12 dBi antenna, staying at ≤ 26.02 dBm EIRP requires conducted power ≤ 14 dBm + cable loss. For example, with 2 dB loss the setting must be ≤ ~16 dBm. The U300 range of 5–30 dBm allows this. At the default 30 dBm, EIRP is about 40 dBm (~10 W), roughly 25× the limit. If the gain is really 12 dBic (circular), the linear-equivalent dBi figure is ~3 dB lower. Use the vendor's dBi figure to stay conservative.
- [ASSUMED] Regulatory compliance and stray-read mitigation point the same way: **lower per-antenna power**. Power reduction is the first lever before any software filter.
- [ASSUMED] Implications of EU-variant equipment:
  1. An EU-region reader SKU (e.g. U34-U7E-R2A11) must be reconfigured to a 920–923 MHz hopping plan. The U300's "920–925 MHz" plan may hop into 923–925 MHz, which is not allowed now.
  2. An EU antenna may be detuned at 920–923 MHz (see Q2).
  3. The **device type** (Chainway U300) must hold an SDPPI certificate obtained by an Indonesian importer/distributor. An EU CE declaration does not count.

### Gaps
- Primary text of Kepmen 260/2024 (scanned PDF, not OCR'd). The ≤26.02 dBm EIRP figure and the "ISR removed" statement come from secondary sources. A reviewer should open the PDF's RFID table directly.
- No Indonesian guidance on duty cycle, channel spacing or listen-before-talk for RFID at 920–923 MHz was found.
- Whether a Chainway U300 SDPPI certificate exists (and under which importer) was not checked. **The user must check** sertifikasi.postel.go.id or ask the supplier for the certificate number.

---

## Q5. Which capabilities does stray-read filtering need, and which candidate provides them?

### Takeaway
Software stray-read mitigation at a 3-antenna gate mainly needs: **antenna ID per read, RSSI per read, a reader timestamp, per-antenna power, GPI triggers (photo-eye), session/target control and EPC/TID filtering**. Phase, Doppler and channel per read help with direction and motion but are optional. On the Chainway U300, the documented items are antenna ID, RSSI, read count, GPI/GPO (4/4), global power 5–30 dBm, per-port enable, Select filters, TagFocus and FastID. Per-antenna power, session/target, dwell, timestamp granularity, phase, Doppler and channel are **unconfirmed**.

### Cited Findings
- U300: RSSI "Supported"; GPIO "4 x input optocouplers, 4 x output optocouplers, with isolation"; power "+5~+30dBm adjustable"; Gen2X "Supported"; antenna detector "Supported" [VERIFIED] — [U300 datasheet](https://www.osiris.co.za/web/content/18049?unique=70a6a0e2a478c6b6df99a7a082d7829c361e1f22&download=true)
- URA4 (Chainway Android fixed reader): the demo shows "EPC or TID, Count, RSSI and Ant. number"; EPC/TID/USER mask filter; ANT1–ANT8 enable/disable; one power setting of 5–30 dBm; tagFocus and FastID toggles; RF link profile [VERIFIED for URA4] — [URA4 manual](https://www.chainway.net/upload/download/c213d762-d356-412b-8e76-35604dc6ca3d.pdf)
- UR4 (Chainway non-Android): TCP/RS-232 host protocol used by an open-source client; EPC and RSSI shown. Phase reporting was claimed in a search snippet but is not visible in the README [VERIFIED/UNCLEAR] — [chainway-serial](https://github.com/DaanVervacke/chainway-serial)
- Monza R6-P supports TagFocus (strong tags suppressed after first read in S1) and FastID (EPC+TID in one reply) [VERIFIED] — [R6-P datasheet](https://www.rfidfuture.com/wp-content/uploads/2020/12/Monza-R6-P.pdf)
- Antenna: 40°/38° beamwidth, F/B 17 dB, RHCP [SECONDARY] — [AZ-12dBi datasheet](https://www.rfidcard.com/wp-content/uploads/2025/02/UHF-RFID-Antenna12dBi-datasheet-AZ-12dBi.pdf)

Capability matrix (what is known for the U300; other candidates had no confirmed "U300" product):

| Capability (why it matters) | Chainway U300 status | Evidence |
|---|---|---|
| Antenna ID per read (which side or overhead saw the tag) | Yes (demo "Ant. number"; URA4) | URA4 manual |
| RSSI per read (near vs far, gate vs staging area) | Yes | U300 datasheet |
| Read count / first-seen–last-seen | Count yes; timestamp unconfirmed | URA4 manual |
| Phase angle / Doppler (motion and direction) | **Unconfirmed** | none |
| Channel / frequency per read | **Unconfirmed** | none |
| Per-antenna power (shrink side vs overhead fields) | **Unconfirmed** (UI shows one global power setting) | URA4 manual |
| Antenna enable/sequence/dwell | Enable yes; dwell/sequence unconfirmed | URA4 manual |
| Session S0–S3 / target A/B / Q | **Unconfirmed** (only "RF link" and "protocol" seen) | URA4 manual |
| GPI photo-eye triggers, GPO stack light | Yes, 4 in / 4 out, isolated | U300 datasheet |
| Select / mask filter (EPC prefix of company items) | Yes (EPC/TID/USER) | URA4 manual |
| TagFocus / FastID (Gen2X) | Yes (toggles) | URA4 manual, U300 datasheet |
| LLRP standard host interface | **Not documented** (Java/Android SDK only) | U300 datasheet |
| Power floor low enough for Indonesia EIRP (≈14–16 dBm conducted with 12 dBi) | Yes (min 5 dBm) | U300 datasheet |

### Inferences
- [ASSUMED] A minimum viable software filter on this hardware can be built from what is documented:
  - Arm or disarm the inventory with a GPI photo-eye.
  - Use per-antenna RSSI thresholds plus **antenna-ID patterns**: a real pass-through should show reads on both side antennas and/or the overhead antenna within a short window, while stray reads tend to appear on one side only, near threshold.
  - Use first-seen/last-seen over a time window, the EPC Select mask and TID de-duplication.
  - Set conducted power to stay within Indonesian EIRP. This also shrinks the read zone.
- [ASSUMED] Direction-of-travel and "tag moving through gate vs static nearby" checks that use phase or Doppler are possible only if the SDK exposes phase. That must be confirmed before such logic is designed. If it is not exposed, direction must come from GPI sequencing (two photo-eyes) or antenna-order heuristics.
- [ASSUMED] If session/target cannot be set, the reader's default session determines whether a static tag near the gate keeps reporting (S0) or goes quiet (S1/S2/S3 with TagFocus). This changes how the ERP should interpret read counts and should be measured on site.

### Gaps
- The Chainway U300 SDK javadoc (for the Android UHF API) was not retrieved. **This is the key open item:** confirm per-antenna power, session/target/Q, dwell, and the per-read timestamp, phase and channel fields, and how GPI events reach the app.
- No independent field measurements (read-zone size versus power) exist for this exact reader, antenna and tag combination. An on-site test at 920–923 MHz with power at or below the legal limit is needed.
