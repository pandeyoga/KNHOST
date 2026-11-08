# Fisika RF unintended read di gate UHF RFID dan mitigasi fisiknya (RF physics of stray reads at UHF RFID dock-door gates & physical mitigation)

> Scope: this note covers only **(1) RF reads of non-target tags** (stray, cross and back reads) and the physical/RF-design side. It does **not** cover **(2) wrong IN/OUT transactions** created from those reads, which are a software/process topic.
> Evidence labels used below: **[REG]** regulation text · **[DS]** datasheet/spec · **[MEAS]** measurement · **[SIM]** ray-tracing/simulation · **[MODEL]** simple analytical calculation done for this note (formula and assumptions shown) · **[VENDOR]** vendor/marketing claim · **[PATENT]** patent text · **[SNIPPET]** seen only in a search-result summary, full text not read (treat as lower confidence).
> Calculation script: free-space Friis, two-ray bound, slot leakage, knife-edge and dielectric attenuation. Assumptions are listed inline with each result.

## Q1. Link budget: how far can a 12 dBi panel read a passive label at 14–30 dBm, what are the EIRP limits (ETSI, Indonesia), is the link forward- or reverse-limited, and how far beyond the portal can a tag still be read?

### Takeaway
At the Indonesian class-licence cap (≤400 mW EIRP = 26 dBm EIRP, for which ~14–15 dBm conducted into a 12 dBi antenna is already the maximum), a Monza R6-P label on boresight is powered out to about **3–5 m in free space**. Constructive multipath can push that to about **6–9 m**. At the ISR cap (≤2 W EIRP, 33 dBm) the corresponding figures are about 6.5–10 m in free space and about 13–20 m with constructive multipath. Passive UHF links are **forward-link (tag-power) limited**, so "where can a stray tag be read" ≈ "where does the tag receive ≥ its sensitivity". Reflections both extend coverage beyond the free-space volume and create holes inside it.

### Cited Findings
**Tag IC**
- [DS] Impinj Monza R6-P: read sensitivity **up to −22.1 dBm** and write sensitivity up to −17.3 dBm (datasheet v7.0, 2021), both "with a dipole antenna", which is a best case. Impinj's series comparison sheet rounds these to −22 / −17 dBm and notes that performance is "based on Impinj's modeling and test data". Sources: [Impinj R6-P datasheet (support.impinj.com)](https://support.impinj.com/hc/article_attachments/1500019253682), [everythingRF listing](https://www.everythingrf.com/products/rfid-tag-ics/impinj/829-670-monza-r6-p), [Impinj Monza R6 series sheet](https://www.impinj.com/getmedia/37a372ee-8875-49db-9788-75b0c7ffdaa8/Impinj-Monza-R6-Tag-Chip-Series.pdf). [SNIPPET for exact wording; the −22 dBm figure agrees across 3 sources]
- [SNIPPET] A newer Impinj comparison sheet reportedly notes that the Monza R6 family is in an end-of-life process, with R6-P still listed at −22 dBm — [Impinj attachment](https://support.impinj.com/hc/article_attachments/40805008872723). This affects supply only, not the physics; verify.

**Read-range physics**
- [MODEL basis, peer-reviewed overview] Nikitin & Rao (Intermec), "Performance Limitations of Passive UHF RFID Systems", IEEE APS 2006:
  - Chip sensitivity is "the most important tag limitation".
  - Using a circularly polarised reader antenna with a linearly polarised tag "removes sensitivity to polarization but incurs additional 3 dB loss".
  - Path loss in a multi-reflection environment is PL = (λ/4πd)²·|1 + Σ Γn (d/dn) e^(−jk(dn−d))|².
  - In cluttered environments the path-loss exponent "may vary between 1 and 4" (free space = 2).
  - In waveguide-like environments (pipes, tunnels) path loss "may be smaller than in free space" up to some distance.
  - "Typically, reader sensitivity is high, and the tag limitation prevails." Their example: reader EIRP 36 dBm, reader sensitivity −80 dBm, chip −10 dBm, 2 dBi tag at 915 MHz. Range is tag-limited at **20 ft** versus a reader limit of **120 ft**.
  - Source: [Nikitin & Rao, APS 2006 (PDF)](https://people.ece.uw.edu/nikitin_pavel/papers/APS_2006.pdf)
- [SIM + MEAS] Dimitriou, Bletsas, Polycarpou, Sahalos, "Theoretical Findings and Measurements on Planning a UHF RFID System inside a Room", *Radioengineering* 20(2), 2011, pp. 387–397:
  - In free-space conditions coverage is a continuous volume around the antenna and no tag outside it can be identified. In real multipath, "the phase-sum of multipath components creates covered-regions even beyond the bounded volume under 'FS' conditions (constructive sum), but also introduces 'holes' of coverage inside the bounded volume (destructive sum)".
  - "Coverage-holes" occur "even at the vicinity of the antenna".
  - Model inputs: concrete walls εr = 6.5, tanδ = 0.287; transmit power 30 dBm at 865 MHz.
  - Tag gain loss on mounting material ranges from about 1 dB (paper, acrylic) to >10 dB (aluminium).
  - EU limit quoted as 3.28 W EIRP.
  - Source: [Dimitriou et al. 2011 (PDF)](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)

**Regulation: Europe**
- [REG] CEPT/ETSI EN 302 208, lower band. Interrogators at 2 W e.r.p. may use only **four channels centred at 865.7, 866.3, 866.9 and 867.5 MHz** (≤200 kHz each). The upper band is 915–921 MHz at 4 W e.r.p. on 916.3, 917.5 and 918.7 MHz only. Tags reply at about −10 dBm e.r.p. Continuous transmission on one channel is limited to ≤4 s, followed by ≥100 ms off. Source: [CEPT EFIS annex (EN 302 208 summary)](https://efis.cept.org/adhoc_grabber.jsp?annex=14) [SNIPPET]
- [REG-overview] GS1 "Overview of UHF frequency allocations for RAIN RFID" (29 Sep 2025) lists EU/CEPT countries at **865.6–867.6 MHz, 2 W ERP**. It also confirms that 4 W ERP in 915–921 MHz is allowed only at 916.3, 917.5 and 918.7 MHz under (EU) 2018/1538 and 2022/172. Source: [GS1 uhf_regulations.pdf](https://www.gs1.org/docs/epc/uhf_regulations.pdf). 2 W ERP = 35.15 dBm EIRP (ERP + 2.15 dB).

**Regulation: Indonesia**
- [REG] Perdirjen SDPPI No. 161/2019 (SRD technical requirements):
  - Table 2.4 lists UHF RFID **only at 920–923 MHz, ≤400 mW EIRP**. The test standards are FCC Part 15 §15.249 / ANSI C63.10-2013, EN 300 220-1, or EN 302 208.
  - Table 2.5: RFID at 920–923 MHz with **>400 mW and ≤2 000 mW EIRP** requires an **Izin Stasiun Radio (ISR)**, which is a paid licence.
  - No 865–868 MHz RFID entry appears in the RFID table. Other RFID bands listed are LF/HF only: 16–150 kHz, 6.765–6.795 MHz, 7.4–8.8 MHz and 13.553–13.567 MHz.
  - Source: [Perdirjen SDPPI 161/2019 (postel.go.id PDF)](https://postel.go.id/downloads/42/20210510125749-perdirjen_2019-161_SRD.pdf)
- [REG-adjacent] An Indonesian SDPPI device certificate (No. 96692/SDPPI/2024, issued 15 Jan 2024, for a Pepperl+Fuchs UHF read/write head) states "RFID: 920 MHz – 923 MHz, Daya Pancar: < 400 mW EIRP" and references Perdirjen 161/2019. Source: [P+F certificate PDF](https://files.pepperl-fuchs.com/webcat/navi/productInfo/cert/cert6014a.pdf)
- [REG, CONFLICT] Kepdirjen SDPPI No. 260/2024 (dated 13 May 2024, enforceable 11 Aug 2024) **replaced** Perdirjen 161/2019. The CAICT summary lists 920–923 MHz under low-rate WPAN and lists RFID at 433–434.79 and 2400–2483.5 MHz. It does not show a UHF-RFID power limit. Source: [CAICT: Indonesia SDPPI publishes SRD regulations](https://gma.caict.ac.cn/en/update/57/534) [SNIPPET]
  - Secondary Indonesian test-lab pages give conflicting limits for 920–923 MHz (≤26.02 dBm EIRP vs ≤20 dBm): [narmadi.co.id](https://narmadi.co.id/standar-pengujian-rfid/) [SNIPPET].
  - GS1 (2025) still lists "Indonesia 923–925, 2 W ERP", which appears outdated against Perdirjen 161/2019 — [GS1](https://www.gs1.org/docs/epc/uhf_regulations.pdf).

**[MODEL] Free-space forward-link range table**

Formula: d_max = (λ/4π)·10^((EIRP − L_pol + G_tag − S_tag)/20).

Assumptions:
- G_reader = 12 dBi (nominal; treated as 12 dBic on a circularly polarised panel).
- L_pol = 3 dB (circular reader to linear tag, per Nikitin & Rao).
- G_tag = 0 dBi (label on a fabric roll end; a 2.15 dBi ideal dipole minus some detuning).
- S_tag = −22 dBm (R6-P best case) or −18 dBm (assumed derated label-level value; there is no datasheet for the "R6P" label itself).
- Cable/connector loss 1 dB or 3 dB (assumed).
- f = 922 MHz (Indonesia) unless noted. At 866 MHz all ranges are ×1.065.

| Conducted P (dBm) | Cable loss (dB) | EIRP (dBm) | d_max at −22 dBm | d_max at −18 dBm | Regulatory status (Indonesia / ETSI) |
|---|---|---|---|---|---|
| 14 | 1 | 25 | 4.1 m | 2.6 m | within the 400 mW class licence |
| 14 | 3 | 23 | 3.3 m | 2.1 m | within class licence |
| 17 | 1 | 28 | 5.8 m | 3.7 m | needs ISR in Indonesia |
| 20 | 1 | 31 | 8.2 m | 5.2 m | ISR |
| 20 | 3 | 29 | 6.5 m | 4.1 m | ISR |
| 24 | 1 | 35 | 13.0 m | 8.2 m | above the ISR cap (33 dBm); ≈ ETSI cap |
| 27 | 1 | 38 | 18.3 m | 11.6 m | above all caps |
| 30 | 1 | 41 | 25.9 m | 16.3 m | above all caps |

**[MODEL] Ranges at the regulatory caps**

| Cap | EIRP | Free-space boresight range | With constructive multipath (+6 dB, ×2) |
|---|---|---|---|
| Indonesian class licence | 26.0 dBm | 4.6 m (−22) / 2.9 m (−18) | 9.2 / 5.8 m |
| Indonesian ISR | 33.0 dBm | 10.3 / 6.5 m | 20.6 / 13.0 m |
| ETSI, at 866 MHz | 35.15 dBm | ≈14.1 / 8.8 m | — |

- The +6 dB figure is the upper bound of the two-ray model when |Γ| → 1: field ×2 means power +6 dB, which doubles range under a 1/d² law. Basis: Nikitin & Rao eq. (2) with N = 1, |Γ| = 1.
- The **14 dBm early assumption** in the brief corresponds almost exactly to the Indonesian ≤400 mW EIRP class-licence limit with a 12 dBi antenna: 14 + 12 = 26 dBm EIRP. Allowed conducted power with 1 dB of cable is ≈15 dBm (class licence) or ≈22 dBm (ISR).

**[MODEL] EIRP needed to just power a boresight tag at distance d** (922 MHz, L_pol 3 dB, G_tag 0 dBi)

| d | −22 dBm tag | −18 dBm tag |
|---|---|---|
| 0.8 m | 10.8 dBm | 14.8 dBm |
| 2.5 m | 20.7 dBm | 24.7 dBm |
| 3 m | 22.3 dBm | 26.3 dBm |
| 5 m | 26.7 dBm | 30.7 dBm |
| 10 m | 32.7 dBm | 36.7 dBm |

Implication: a near-face tag about 0.6–0.8 m from a recessed side antenna already has **~11–15 dB of margin at 26 dBm EIRP**.

**[MODEL] Reverse-link check.** P_reader ≈ S_tag − L_bs + G_tag − FSPL(d) − L_pol + G_reader − L_cable, evaluated at the forward-link limit distance. Assumptions: backscatter/modulation loss L_bs = 8 dB, cable loss 1.5 dB.

| EIRP | Forward-limit distance | Received backscatter |
|---|---|---|
| 26 dBm | 4.6 m | ≈ −67.5 dBm |
| 33 dBm | 10.3 m | ≈ −74.5 dBm |
| 35 dBm | 13.2 m | ≈ −76.7 dBm |

All three are above the −80 dBm reader sensitivity in Nikitin & Rao's example, so the system is **forward-link limited**, consistent with that paper's conclusion.

### Inferences
- The stray-read radius is set mainly by **EIRP × antenna gain in the direction of the stray tag × multipath**. Reader receive sensitivity rarely protects you. Lowering reader receive sensitivity or using an RSSI threshold is a software/firmware filter, not an RF containment measure.
- Regulatory power in Indonesia (≤26 dBm EIRP without ISR) naturally limits boresight stray range to single-digit metres. With ISR power (up to 33 dBm EIRP), boresight stray reads at 10–20 m become physically possible, so a 3 m clear zone cannot be an RF boundary on any boresight path.
- Free-space numbers are a **central estimate, not an upper bound**. Constructive multipath (×2 range for one perfect reflector) and waveguide-like channelling in a metal-lined tunnel (path loss lower than free space, per Nikitin & Rao) can extend reads. Destructive multipath creates in-gate holes that drive operators to raise power, which enlarges the stray zone.
- Frequency/antenna mismatch. The brief's antenna is the **EU (865–868 MHz) variant**, but Indonesian UHF RFID is at **920–923 MHz** (Perdirjen 161/2019). The antenna will run about 55 MHz above its specified band. Mismatch loss itself is modest — VSWR 1.5 → 0.18 dB, 2 → 0.51 dB, 3 → 1.25 dB, from ML = −10·log(1−|Γ|²) [MODEL]. Gain, beamwidth, axial ratio and front-to-back ratio outside the specified band are unknown. The 902–928 MHz variant (listed for the same Ant-RC12 family) covers 920–923 MHz. See Q2.
- Whether the regulator counts a circular antenna's dBic gain fully against EIRP is a compliance detail. The model above conservatively assumes it does.

### Gaps
- The current (Kepdirjen 260/2024) Indonesian limit for UHF RFID at 920–923 MHz could not be confirmed from primary text; secondary sources conflict (≤400 mW / 26 dBm vs 20 dBm). Read the official decree annex or ask SDPPI before fixing the power.
- No datasheet exists for the "R6P" label itself (inlay/antenna gain, label-level sensitivity, performance on textile). The −18 dBm derating used here is an assumption; measure label sensitivity on an actual roll end (e.g., with a Voyantic-type tester or a power-ramp test).
- Reader model and its receive sensitivity are not specified. The reverse-link check uses an assumed 8 dB backscatter loss and Nikitin & Rao's −80 dBm example.

## Q2. What do 12 dBi panel patterns imply for reads behind and beside the gate, and how does recessing the antenna in a metal (ACP/aluminium) enclosure change it?

### Takeaway
A 12 dBi panel with a ~38–40° half-power beam still radiates outside that beam. Every 10 dB of pattern suppression divides range by ~3.2, and 20 dB divides it by 10. Back and side lobes therefore give stray reads at metre scale rather than tens of metres. The bigger leak paths are the main beam spilling out of the gate's open ends and reflections from metal surfaces. A recessed metal cavity can help or hurt: it narrows and cleans the pattern only if the antenna is not detuned and the front cover is RF-transparent.

### Cited Findings
- [DS, SNIPPET] Chainway "Ant-RC12" 12 dBi panel:
  - Frequency variants 902–928 MHz / 865–868 MHz, right-hand circular polarisation.
  - 3 dB beamwidth **40° (H-plane) / 38° (E-plane)**.
  - VSWR ≤1.3, maximum input 20 W, IP67.
  - RS datasheet lists the 12 dBi model at **445×445×30 mm, 2.66 kg**, with bracket part number "Ant-MOT-RC12-455/455-P". One listing shows input impedance "500 Ohms", probably a typo for 50 Ω.
  - Sources: [Asset Infinity store listing](https://store.assetinfinity.com/product/ant-rc12-12dbi-panel-antenna) (my direct fetch of this page confirmed only "12 dBi" and IP67), [neotech.ae listing](https://neotech.ae/products/8-397) (also described as a Wi-Fi antenna there, so unreliable).
  - **Front-to-back ratio and axial ratio were not found.**
- [DS, SNIPPET] For comparison, a TE Connectivity 902–928 MHz RFID panel (S9028PCL12NFMO) lists front-to-back ratio **20 dB** and axial ratio 1 dB typical. This is a different antenna, given only as a typical industry value — [Farnell-hosted datasheet](https://www.farnell.com/cad/3980802.pdf).
- [DS, peer-reviewed] Commodity 10 dBic CP panel, 37×37 cm: 3 dB beamwidth 60° azimuth / 48° elevation (MTI MT-242017/NRH, as used in Dimitriou et al.). Smaller apertures give wider beams. Source: [Dimitriou et al. 2011](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)
- [SIM + MEAS] When two antennas are fed **simultaneously** (via a splitter), they form an array with destructive-interference minima "at predictable locations", so a tag can be missed "despite of its small distance from the two antennas". Same source: [Dimitriou et al. 2011](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)
- [PATENT, SNIPPET] Metal near a reader antenna detunes it: it lowers input impedance and shifts resonance. One patent reports that a reader on a metal mullion lost up to **50% of read range**, reduced to ~10% when a compensating metal plate was designed in — [US 6,377,176 "Metal compensated RFID reader"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6377176). This was an HF/near-field reader, so it is indicative only for UHF panels.
- [MEAS, SNIPPET] In a metal-cluttered room, UHF read patterns were inconsistent because of multipath. Removing reflective objects near the antennas made readings more consistent — [ASEE 2011, "Location identification using passive UHF RFID system"](https://peer.asee.org/location-identification-using-passive-uhf-rfid-system.pdf).

**[MODEL] Geometry of this gate** (simple ray/cone, far-field beamwidth applied)

Side antennas firing across the 2.5 m gate:
- The −3 dB footprint on the opposite wall is 2·d·tan(θ/2): 40° → **1.82 m**, 38° → **1.72 m**.
- This is wider than the **1.5 m** gate depth, so even the half-power beam spills ~0.1–0.15 m past each open end. Lower-level beam energy spills further.

Overhead antenna at ~2.75–2.8 m above the floor:
- The −3 dB footprint on the floor is ≈2.0 m (40°) against a 1.5 m depth, so the floor illumination extends ~0.25 m beyond each opening.

Off-axis range scaling (range × 10^(−ΔG/20)):

| Pattern suppression ΔG | Range factor |
|---|---|
| 3 dB | ×0.71 |
| 6 dB | ×0.50 |
| 10 dB | ×0.32 |
| 15 dB | ×0.18 |
| 20 dB | ×0.10 |
| 25 dB | ×0.056 |

Example: with an assumed 20 dB front-to-back ratio, the back-lobe range at the 26 dBm EIRP class-licence cap is ≈0.3–0.46 m. At the 33 dBm ISR cap it is ≈0.65–1.0 m (free space).

Near field:
- Fraunhofer distance 2D²/λ for D = 0.445 m (side length) is **≈1.22 m at 922 MHz** (1.14 m at 866 MHz). Using the 0.63 m diagonal gives ≈2.4 m. This is a standard antenna formula, not otherwise sourced here.
- Tags on the near face of a load (≈0.6–0.8 m from a recessed side antenna) are in the radiating near field. Datasheet beamwidth and gain do not describe the field there precisely.

**[MODEL] Aluminium skins**
- Skin depth of aluminium at 922 MHz is δ = 503·√(ρ/f) ≈ **2.8 µm** (ρ = 2.82×10⁻⁸ Ω·m). The typical ACP skin thickness of about 0.2–0.5 mm (assumption, not sourced) is roughly 70–180 δ.
- Any ACP or aluminium sheet in front of the antenna is effectively opaque. The antenna window in the gate body **must be non-metallic** (e.g., polycarbonate, ABS, FRP or the ACP core without skins).

### Inferences
- **Behind and beside the gate (back and side lobes).** With ≥15–20 dB front-to-back ratio (typical for panels, but not verified for the Ant-RC12), direct back-lobe stray range at legal Indonesian power is sub-metre to ~1 m. Back lobes are not the main threat. The main threats are:
  1. main-beam spill out of the open ends (the beam is wider than the 1.5 m depth);
  2. specular and diffuse reflections from the opposite ACP wall, the metal stacker and the load;
  3. floor reflections from the overhead antenna (see Q3).
- **Recessing in the 25 cm ACP-clad body** (cavity-backed mounting) is generally beneficial for containment *if*:
  - the cavity opening is at least the antenna aperture (445 mm) plus a clearance margin;
  - the metal side walls are not right at the antenna's radiating edges (suggested ≥λ/4 ≈ 8 cm; assumption, not sourced);
  - the window is RF-transparent;
  - the antenna is re-checked in situ (VSWR/return loss at 920–923 MHz with the cavity and cover in place).

  Benefits: the cavity walls block wide-angle radiation and reduce side and back radiation. Risks: detuning (resonance shift, gain loss) and cavity resonances. Measure the read-zone edge after installation; do not assume the datasheet pattern holds.
- **ACP body as a shield between adjacent gates.** If the gate's outer side faces are continuously aluminium-skinned and the antenna windows face only inward, the gate body is already a strong barrier on the direct boresight path toward a neighbouring gate. Coupling to a neighbour then happens mainly through the open ends: out of one gate, around the ends, into the next. This is relevant to Options A and B.
- **Out-of-band EU antenna at 920–923 MHz.** Pattern, gain and axial ratio may degrade, and the front-to-back ratio is unknown. Prefer the 902–928 MHz variant or require measured S11/pattern data at 920–923 MHz.
- **Reader multiplexing.** If the reader multiplexes its 3 ports (one antenna transmitting at a time), the Dimitriou splitter-array null effect does not apply between antennas. Verify that the chosen reader does not drive antennas simultaneously; this is reader-specific.

### Gaps
- No measured pattern (front-to-back ratio, side-lobe level, axial ratio) for the Ant-RC12, and none at 920–923 MHz for the EU variant.
- No published measurement found of a UHF panel recessed in a metal cavity, quantifying how pattern, front-to-back ratio or VSWR change with cavity depth and clearance. Would need EM simulation (CST/HFSS/FEKO) or an on-site measurement.
- ACP skin thickness for the chosen panel brand was not verified.

## Q3. How do reflective surfaces (aluminium partitions, ACP, steel racks, metal stacker, concrete floor) create stray reads and nulls; is power reduction an effective separator; and how much do 6-high fabric stacks attenuate?

### Takeaway
Metal surfaces near the gate act as mirrors. They create image sources that illuminate zones the antenna does not face directly (stray reads), and they create standing-wave nulls inside the gate (missed reads). Concrete reflects less at steep angles but strongly at grazing angles. Power reduction separates targets from stray tags only by a few dB of geometric advantage, while target tags need 10–20+ dB of margin for fades, orientation and textile loss. **Power alone cannot cleanly separate them.** Cotton-rich rolls attenuate roughly 10 dB per metre of fabric (simple model), so tags not on the face toward an antenna are effectively unreadable from that antenna.

### Cited Findings
- [PEER-REVIEWED MODEL] Path loss with reflections: PL = (λ/4πd)²·|1 + Σ Γn(d/dn)e^(−jkΔn)|². The reflection coefficient of each object, including the ground, adds or subtracts depending on the path-length difference. Path-loss exponent 1–4 in cluttered environments. — [Nikitin & Rao, APS 2006](https://people.ece.uw.edu/nikitin_pavel/papers/APS_2006.pdf)
- [SIM + MEAS] Multipath creates coverage beyond the free-space volume and holes inside it, even near the antenna. Careful antenna placement and **tilting** "must be performed to control destructive interference effects". Material constants used: concrete εr = 6.5, tanδ = 0.287. — [Dimitriou et al. 2011](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)
- [SIM + MEAS] Tag gain loss from the mounting substrate: ~1 dB for paper/acrylic up to >10 dB on aluminium. — [Dimitriou et al. 2011](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)
- [SURVEY] UHF portal designers face a fundamental trade-off: configurations that raise in-zone read accuracy "also increase the reader range … it will affect cross reading problem in multi portal systems". — [Borisenko & Li, "Survey on UHF RFID portals", Univ. Ottawa 2010](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- [VENDOR] Tag backscatter varies greatly across tags on different materials, so "one reader power level" rarely gives 100% for every material. — [RFID Journal, "UHF RFID's Key Constraints"](https://www.rfidjournal.com/?p=76991) [SNIPPET]
- [PATENT, SNIPPET] "Due to multipath effects in UHF … RFID systems, it is not typically possible to control or prevent the reading of stray or 'background' tags." Portal stations "are typically operated at a fairly high level of effective isotropic radiated power" and so are "prone to sensing stray RFID tags positioned in locations not associated with the corresponding loading bay". — [US patent "RFID portal targeting" (12,218,715)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12218715); [US patent "RFID tag stray alarm mitigation" (12,700,292)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12700292). Attribution of each quote to a specific patent is per the search summary.
- [MEAS] Textile dielectric data. Pérez-Campos et al., "Dielectric Characterization of Fabric Aggregates around the 2.45 GHz ISM Band under Various Humidity, Density, and Temperature Conditions", *Materials* 16(12):4428, 2023, measured at ~2.0–2.5 GHz:
  - Fitted values: cotton ε′ ≈ 2.05, ε″ ≈ 0.20; polyester ε′ ≈ 1.64, ε″ ≈ 0.043; polyamide ε′ ≈ 1.65, ε″ ≈ 0.06.
  - Moisture content is the most influential factor. For cotton (at 0.98 g/cm³) going from 0 to 100% moisture (dry basis), ε′ rose ~259% and ε″ ~564%.
  - Higher density raised cotton ε′ by 36% and ε″ by 175%.
  - Sample moisture contents were cotton 6.1%, polyester 0.75%.
  - Source: [PMC10305466](https://pmc.ncbi.nlm.nih.gov/articles/PMC10305466/)
- [REVIEW, SNIPPET] At 1 MHz, plain-weave cotton ε′ was 5.59 at 40% RH and 7.08 at 80% RH (tanδ 0.063 → 0.102). Cotton twill at 2.45 GHz had tanδ ≈ 0.020. Values from different setups are not directly comparable. — [MDPI *Textiles* 2(1):4, "Dielectric Properties of Textile Materials … A Review"](https://mdpi.com/2673-7248/2/1/4)
- [MEAS, SNIPPET] Field tests of item-level apparel tagging reported read rates at or near 100% with suitable tag/reader combinations, with garment type not appearing to matter. These were single-layer garments, not dense rolls. — [Univ. of Arkansas / Auburn RFID Lab apparel feasibility study](https://htmlscript.auburn.edu/under-development/rfid/papers/pages/RFIDItem-LevelTaggingforApparelFootwearFeasibilityStudy.php)

**[MODEL] Attenuation through fabric**

Low-loss plane wave: α(dB/m) = 8.686·(π/λ₀)·ε″/√ε′. Uses the 2.45 GHz-band values above, applied at 922 MHz as an assumption.
- **Cotton ≈ 11.7 dB/m** (tanδ ≈ 0.098)
- **Polyester ≈ 2.8 dB/m** (tanδ ≈ 0.026)
- **Polyamide ≈ 3.9 dB/m**

Caveats:
- Water's dielectric loss is generally lower at 0.9 GHz than at 2.45 GHz, so these may overstate the loss for a given moisture.
- Tropical humidity (higher regain) and high winding density push cotton's loss up. Treat the figures as order-of-magnitude.
- Effect on range: one metre of cotton-rich fabric (~11 dB) cuts forward-link range ×0.28. Reading a far-face tag through a 1.8 m-wide load (~21 dB) would need ~42 dBm EIRP for a 2.5 m path, which is far above any legal limit.

**[MODEL] Concrete floor reflection**
- Normal-incidence |Γ| for εr = 6.5, tanδ = 0.287 is ≈ **0.45 (−6.9 dB)**.
- At grazing incidence the reflection coefficient of any dielectric tends to |Γ| → 1. Floor reflections are therefore weak straight down under the overhead antenna but strong for shallow paths running along the floor out of the gate.

**[MODEL] Margin arithmetic for "separate by power"**
- Near-face target tag at ~0.8 m needs ≈10.8 dBm EIRP (−22 dBm tag) or ≈14.8 dBm (−18 dBm tag).
- A boresight stray tag at 2.5 m needs 20.7 / 24.7 dBm; at 3 m, 22.3 / 26.3 dBm.
- So between a target at 0.8 m and a stray tag at 2.5–3 m on the same bearing the free-space power difference is only **~10–11.5 dB**.
- Typical target-side losses each consume comparable margin:
  - multipath holes (several to >10 dB);
  - CP→LP polarisation (3 dB, already included) plus label rotation on the roll end;
  - substrate/detuning (~1 dB on paper-like substrates per Dimitriou; unknown on fabric);
  - ±4 dB uncertainty in label sensitivity.

### Inferences
**Reflectors and stray paths**
- Each large flat metal surface near the gate behaves like a mirror with |Γ| ≈ 1: aluminium partitions, ACP faces, the steel stacker frame and mast, and steel racks.
- A side antenna aimed across the gate creates an image source behind the opposite ACP wall. For parallel walls the specular return goes back across the gate rather than out of the ends. Beam-edge energy hitting the walls obliquely bounces along the tunnel and exits the open ends, which is the waveguide-like channelling that Nikitin & Rao describe.
- A stand-alone aluminium partition placed beside or between gates (Option B) **adds new mirrors**. It can redirect main-beam spill toward storage areas that previously had no line of sight to the antenna. See also the "metallic screens suffer from stray reflections" finding in Q4.
- Steel racks loaded with tagged rolls are both stray targets and reflectors. Rack tags near a reflective surface can sit in constructive-interference spots well beyond free-space range.

**Nulls inside the gate**
- The parallel ACP walls, the ACP ceiling and the concrete floor form a partially closed metal box with standing-wave patterns. Some positions inside the gate will see deep fades.
- The usual reaction ("raise the power until the missing tags read") enlarges the stray zone. Better levers:
  - antenna diversity: three antennas looking from different angles, time-multiplexed;
  - frequency hopping across the 920–923 MHz channels, which moves nulls;
  - motion of the load through the gate, which sweeps tags through nulls;
  - avoiding parallel metal surfaces directly facing each other, e.g., by tilting antennas or lining part of a wall with absorber (Q4).

**Lowest roll (~20 cm above the floor)**
- This roll lies in the floor-reflection interference zone. Whether it is in a peak or a null depends on antenna height, distance and frequency (two-ray), and cannot be predicted reliably without measurement. Test the bottom layer explicitly.

**Six-high stack**
- Given ~11 dB/m in cotton, each side antenna can practically read only tags on the stack face that points toward it. Tags whose roll end faces the far side must be read by the opposite side antenna.
- The overhead antenna sees only the top layer, and sees roll-end labels edge-on: a label in a vertical plane illuminated from above couples only if its long axis is horizontal. It therefore adds little coverage for lower layers but contributes floor-reflection stray risk.
- If any rolls are loaded with their tagged end toward the interior (e.g., two rolls end-to-end across the 2.4 m stacker width), those tags are effectively shielded by fabric from all three antennas. This is a load-pattern / tagging-rule issue, not a power issue.

**Power reduction**
- It is useful for trimming the long tail of the stray zone, especially on boresight. It cannot by itself guarantee "read every target, never read a rack tag 3 m away", because the target-vs-stray power gap (~10 dB on a common bearing) is comparable to the fading margin targets need.
- It works best combined with:
  - directivity, i.e., aiming away from storage;
  - physical blocking of direct paths (metal body, fins), with absorber where reflections matter;
  - software discrimination (RSSI, antenna sequence, dwell time).

**Moisture**
- In humid Indonesian warehouses, cotton rolls will be at or above standard regain. Expect higher loss than dry-lab data suggests, and variation between seasons and lots. Calibrate power in the wet season, with the densest and most cotton-rich product.

### Gaps
- No UHF (860–960 MHz) measurement found of attenuation through **wound fabric rolls** (cotton, polyester, blends) versus moisture regain. The model extrapolates from 2.45 GHz aggregates. A simple on-site test would close this gap: tag behind 0.3 / 0.6 / 1.2 m of roll and a reader power ramp to find the activation threshold.
- No measured reflection data for the specific metal stacker, racks or ACP panels; no measured null map of a 2.5 × 2.75 × 1.5 m metal-clad gate.
- Exact roll orientation on the stacker (which ends face which side, single or double row) is not specified in the brief, but it determines whether tags are face-exposed.

## Q4. Effectiveness and limits of RF shielding for portals: shielding paint, metal partitions, absorbers vs reflectors, strip curtains, aperture leakage at λ ≈ 32.5–34.6 cm, and why material dB figures cannot be summed or applied to openings

### Takeaway
A shield is only as good as its biggest hole and its edges. At 920 MHz (λ ≈ 32.5 cm) any opening or slot longer than ~16 cm (λ/2) leaks essentially unattenuated. The gate's own 2.5 × 2.75 m openings, the gaps between curtain strips, and the paths around the ends and tops of partitions therefore dominate. Edge diffraction around a finite partition gives only ~6–20 dB, so a paint rated 37–43 dB cannot deliver 37–43 dB to the warehouse. Metal (and conductive paint) reflects rather than absorbs, so it can create new stray paths. Absorber (Salisbury/carbon-loaded) is the tool for killing reflections, at about −18 dB for commercial UHF plates.

### Cited Findings
**Aperture leakage**
- [EMC REFERENCE, SNIPPET] Worst-case shielding effectiveness of a single slot in a conducting sheet is commonly SE ≈ 20·log₁₀(λ/2L) dB, where L is the longest slot dimension. It falls to ~0 dB at L = λ/2. Design guidance keeps apertures below λ/20 (some sources say λ/50).
  - For N identical apertures, sources give SE_array ≈ SE_single − 10·log N, or −20·log n (n apertures within λ/2), so the two disagree.
  - "Enclosure SE is almost always limited by the apertures."
  - Within λ/2π of the slot, near-field coupling dominates and the simple formula underestimates leakage.
  - Sources: [RF Essentials – aperture coupling](https://rfessentials.com/rf-knowledge-base/how-do-i-calculate-the-aperture-coupling-through-a-slot-or-opening-in-a-shielded/), [Electronic Design – "Shielding: The Hole Problem"](https://www.electronicdesign.com/home/article/21200214/shielding-the-hole-problem), [Interference Technology – large-aperture effects](https://interferencetechnology.com/design-considerations-for-minimizing-large-aperture-effects-in-shielding/) (the last notes the constant can be 20–40 depending on shape, and that a slot behaves like a complementary dipole)
- [MODEL] Applying SE = 20·log(λ/2L), clipped at 0 dB:

| Slot length L | SE at 922 MHz (λ = 0.325 m) | SE at 866 MHz (λ = 0.346 m) |
|---|---|---|
| 3 mm | 34.7 dB | 35.2 dB |
| 1 cm | 24.2 dB | 24.8 dB |
| 2 cm | 18.2 dB | — |
| 5 cm | 10.2 dB | 10.8 dB |
| 10 cm | 4.2 dB | 4.8 dB |
| 15 cm | 0.7 dB | 1.2 dB |
| ≥ λ/2 (16.3 / 17.3 cm), incl. 0.5 m, 1 m, 2 m | ≈0 dB | ≈0 dB |

**Diffraction around partition edges**
- [STANDARD MODEL] Single knife-edge diffraction loss (ITU-R P.526 approximation): J(ν) ≈ 6.9 + 20·log₁₀(√((ν−0.1)²+1) + ν − 0.1) dB, with ν = h·√((2/λ)(1/d₁ + 1/d₂)); valid for ν > ≈ −0.7. Sources: [GaussianWaves – single knife-edge model](https://www.gaussianwaves.com/2019/04/modeling-diffraction-loss-single-knife-edge-diffraction-model/), [ITU-R P.526](https://www.itu.int/rec/R-REC-P.526). Formula seen via search summaries; the ITU text was not opened in this session.
- [MODEL] At 922 MHz:
  - Grazing the edge (ν = 0): **6.0 dB**.
  - Edge 0.25 m above line of sight with d₁ = 2 m, d₂ = 3 m: ν ≈ 0.57, **≈10.8 dB**.
  - Edge 0.5 m above line of sight: ν ≈ 1.0–1.1, **≈14–15 dB**.
  - Edge 1.0 m above line of sight: ν ≈ 2.0–2.3, **≈19–20 dB**.

**Reflectors vs absorbers**
- [PATENT] "Metallic screens suffer from stray reflections … while loaded rubber screens tend to be bulky and expensive." — [US 2011/0089239 "Radio Frequency Absorption"](https://patents.justia.com/patent/20110089239)
- [PATENT, SNIPPET] Multi-read portal design:
  - RF energy reflects between metal-skinned walls and repeatedly meets a **Salisbury-screen damping layer** (lossy sheet spaced in front of a conductive backplane; the metal skin can serve as the ground plane). This gives attenuation of "10 dB or more" so the antennas have "limited if any interaction" with external tagged items.
  - Design target: exclude stray tags "within a reasonable distance of one or two meters".
  - Absorber placement "must be designed in such a way that the desired illumination … is unaffected".
  - Sources: [US 10,783,339 "RFID multi-read portal"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10783339), [US 12,099,892](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12099892)
- [PATENT, SNIPPET] A fully enclosed shielded portal lets reader power and sensitivity be raised "without producing sufficient signal amplitude outside the reading zone" to wake external tags. — [US 9,760,826 "Shielded portal for multi-reading RFID tags"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9760826)
- [VENDOR, SNIPPET] A UHF absorber plate for "RFID recognition tunnels and truck docking stations", where unwanted reflections arise "from steel building structures or adjacent RFID reading systems", is rated about **−18 dB at 800 MHz–1 GHz**. — [FHI / ABS Technics "RFID signaal absorber"](https://fhi.nl/en/news/rfid-signaal-absorber)
- [VENDOR, SNIPPET] A commercial RFID shielding curtain (MWT Materials) uses a metal-infused outer layer that **reflects** (blocks) external tags and **absorptive** interior panels. — [RFID Journal on MWT Materials](https://www.rfidjournal.com/?p=71930). Direct fetch blocked (403).

**Tunnel tests and practitioner views**
- [MEAS, abstract only] Bertolini, Rizzi, Romagnoli, Volpi, "Testing an RFID receiving gate for improving process accuracy in fashion and apparel retail", IEEE RTSI 2017 (DOI 10.1109/RTSI.2017.8065916):
  - 4-antenna tunnel gate; varied antenna type, RF-absorbing material at the tunnel exit, and reader power.
  - Measured false reads (tags read outside the tunnel).
  - Concluded that optimal settings maximise accuracy "at the minimum reading power", minimising false reads.
  - Source: [IRIS Unimore record](https://iris.unimore.it/handle/11380/1188667) (access 403; figures not obtained).
- [VENDOR] Fraunhofer IFF tunnel gates: power density, field homogeneity and polarisation are the key bulk-reading parameters; the gate is claimed to eliminate false positives. — [Fraunhofer IFF](https://iff.fraunhofer.de/en/business-units/material-handling-engineering/rfid-tunnel-gates-fiege.html). Vendor claim.
- [SURVEY] Commercial portals use shielding approaches, e.g., a conveyor portal "framed with RF reflective mesh panels to contain RF field", or "an enclosed space, protected by metal shielding". — [Borisenko & Li 2010](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- [PRACTITIONER, SNIPPET] Some companies installed shielding to stop readers picking up adjacent doors' tags, but software was described as "cheaper, faster and easier". — [RFID Journal, "Tips for Setting Up Portal Interrogators"](https://www.rfidjournal.com/news/tips-for-setting-up-portal-interrogators/76293/). Dock-door guides list shielding panels as optional, to "reduce stray reads from adjacent lanes or doors". — [RFID4U dock door guide](https://rfid4u.com/enabling-your-dock-doors-with-rfid/)
- [PROJECT BRIEF] YShield PRO54 is ≈37 dB single layer and ≈42–43 dB double layer at ~866 MHz, per the manufacturer's material test. This is a far-field, plane-wave **material** figure, not a figure for an installed partition.

### Inferences
**Why the dB figures cannot be summed or applied to openings**
- A material SE (paint 37–43 dB) describes transmission **through an infinite, seamless sheet**. The field reaching a tag behind a partition is the sum of all paths:
  - through the sheet (−37…−43 dB);
  - around the edges (diffraction, only −6…−20 dB);
  - through seams, gaps at floor and ceiling, and cable holes (slot law; ≈0 dB for any slot ≥16 cm long);
  - reflected off other surfaces such as floor, roof steel and racks (no attenuation from the partition at all).
- The weakest path dominates. Powers add, so the result is roughly 10·log(Σ 10^(−Li/10)), which is close to the smallest loss.
- Two coats raising material SE from 37 to 43 dB change nothing if edge diffraction is 10–15 dB.
- Material SE values also cannot be "stacked" across separate barriers (e.g., partition + curtain) as if in series, unless every bypass path is closed.

**Paint on aluminium partitions (Option B)**
- Bare aluminium sheet already has intrinsic SE far above 43 dB at 920 MHz (skin depth ≈2.8 µm; see Q2). Painting aluminium with conductive shielding paint adds essentially nothing to through-transmission loss.
- The paint is meant for non-conductive substrates (gypsum, wood, plastic, the core of a cut ACP). It is also a conductive reflector, not an absorber, so it does not reduce reflections.
- Whether aluminium-plus-paint or bare aluminium, the partition's effectiveness is set by its **size relative to the paths** (how far it extends beyond the gate ends and above the antenna and tag line of sight) and by gaps.

**Partitions as reflectors**
- A metal partition beside a gate is a mirror: energy spilling from a gate opening can be reflected toward areas that previously had no line of sight to the antenna.
- If partitions are used, place **RF absorber on the surfaces that face antennas or openings**. A metal backer with absorber facing in follows the Salisbury/curtain designs above; a reflective skin outside with absorber inside follows the MWT curtain concept. Extend the partitions well beyond the opening edges (fins), because diffraction loss grows with how far the edge sits above the line of sight. Even 1 m of clearance only gives ~20 dB.

**Strip curtains on warehouse-facing openings**
- Strips hanging vertically form **long vertical slots** (L ≈ curtain height ≫ λ/2) unless adjacent strips overlap and touch electrically. Per the slot law, a non-overlapping strip curtain gives ≈0 dB for polarisation components across the slot.
- When the stacker pushes through, the curtain opens exactly while the reader is active. That is when stray reads of warehouse-side tags are most likely, because the load and stacker also act as reflectors in the opening.
- Curtains help between passes (e.g., against parked loads read while idle). They are weak during a pass. Motion-triggered RF (reader on only during a pass, see Q5) mitigates the idle case more cheaply.

**The gate openings cannot be shielded**
- The 2.5 × 2.75 m openings are ≫ λ, so SE is ≈0 dB. Physical containment can only come from:
  - pattern control (aiming and tilting away from openings, recessing, narrow-beam antennas);
  - power;
  - extending the "tunnel": absorber-lined vestibule walls or fins beyond the 1.5 m depth, so that energy leaving the openings must diffract or attenuate. This follows Bertolini et al.'s use of absorber at the tunnel exit.

**Option A vs B vs C from the RF side**
- B's partitions add value only if they (i) block a **direct** line of sight from a gate opening to the other gate's tags or storage, (ii) extend far enough for ≥15–20 dB of diffraction loss, and (iii) are absorber-faced so they do not create new reflections. Paint on aluminium adds nothing. Curtains add little during passes.
- A and C depend entirely on distance, power and pattern. C's physical separation (two doors) removes the neighbouring-gate path.

### Gaps
- No primary measurement found of installed shielding performance (partition, curtain or paint) at a dock-door portal.
- YShield PRO54's intended substrate and the test method behind the 37–43 dB figure (ASTM D4935? IEEE 299?) are not documented here.
- Commercial "RFID shielding curtain" specs (overlap, conductive strip material, measured insertion loss with gaps) were not obtained; the MWT article was blocked.
- Bertolini et al. 2017 quantitative false-read results (with vs without exit absorber, by power) were not obtained; full text inaccessible.

## Q5. Antenna orientation/tilt, placement in the tunnel, read-zone shaping, circular vs linear polarisation, and vendor/integrator best practice for dock-door portals

### Takeaway
Industry practice for limiting dock-door cross-reads is:
1. aim antennas into the load and away from neighbouring doors and storage;
2. use the lowest power that reliably reads the target;
3. turn RF on only when a load is present (motion or photo-eye triggers);
4. avoid simultaneous transmission from adjacent readers (time-slotting / dense-reader mode).

Circular polarisation is the default for randomly oriented labels and costs 3 dB. It gives no inherent stray-read protection against linear tags.

### Cited Findings
- [VENDOR] Venture Research dock-door portal:
  - Antennas on articulated arms "rotate the antennas into the truck, reducing dock to dock cross reads".
  - A high-gain array "allows the RF power required to be turned down yet still retain adequate coverage".
  - Built-in motion sensors activate RF only when there is dock activity; an optional truck-in-position sense ensures "RF is not turned on until the truck door is open".
  - Source: [Venture Research – Interior RFID/BLE dock door portals](https://ventureresearch.com/?p=3162)
- [SURVEY] Portal practice:
  - Most solutions use two free-standing antenna towers on opposite sides of the door facing each other, with 2–4 antennas each. Some use enclosed, metal-shielded spaces.
  - Impinj xPortal used dual-linear phased-array antennas alternating vertical and horizontal polarisation, with a low duty cycle that limits operation to times when tags are detected.
  - Cross-reading mitigations: TDMA (readers in different time slots); motion-sensor on/off control so "only one dock door is active at any one time"; time thresholds to ignore tags that appear briefly; stray-tag elimination by triggering (Sirit); RSSI plus phase-based motion detection (Intermec).
  - Raising read accuracy also raises range and cross-reading.
  - Source: [Borisenko & Li 2010](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- [PEER-REVIEWED] A circular reader antenna with a linear tag costs 3 dB but removes orientation sensitivity. — [Nikitin & Rao 2006](https://people.ece.uw.edu/nikitin_pavel/papers/APS_2006.pdf)
- [SIM + MEAS] Careful selection of antenna placement **and tilting** is required to control destructive interference.
  - Several antennas should be rotated "so that they illuminate different parts of the room" (different angular segments of their 3 dB beamwidths), to avoid array nulls when fed together.
  - Tag polarisation diversity (three orthogonal tags) raised aggregate coverage by ~10 percentage points, to 89% at −14 dBm.
  - Source: [Dimitriou et al. 2011](https://www.radioeng.cz/fulltexts/2011/11_02_387_397.pdf)
- [PATENT] A dock-door portal example spaces portals about 10 ft (±2 ft) apart, within 2 ft of the dock edge. Staging-area tags that the reader detects are ignored when below an RSSI threshold. — [US 10,157,337 "Pre-notification with RFID dock door portals"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10157337) [SNIPPET]
- [VENDOR, SNIPPET] SLS dock-door products claim "very minimal power" with "99.99%" accuracy and no cross-readings between sites. Unverified marketing — [SLS RFID dock door (barcodesinc)](https://www.barcodesinc.com/sls/part-1000d510-c-sls.htm)
- [PRACTITIONER, SNIPPET] "It is common to read tags on products on adjacent conveyors or through adjacent dock doors." Filtering by which door read the tag first and how often is recommended. — [RFID Journal, "Dealing with False-Positive Reads"](https://www.rfidjournal.com/news/dealing-with-false-positive-reads-2/175988/)

### Inferences
**Aim (pattern control)**
- For this gate the threat directions are the open ends (storage and racks on the warehouse side, parked loads, the neighbouring gate). Side antennas should fire **across** the gate, which they already do, ideally with a slight **inward/downward tilt** so the main beam lands on the load and the floor inside the gate footprint rather than spilling out of the ends.
  - "Inward" here means toward the gate centre-plane, away from the open ends.
  - Tilting toward the outdoor/truck side, as Venture Research does with "into the truck", is the analogue if one side of the gate has no tags.
- Keep the −3 dB footprint (~1.7–1.8 m at 2.5 m) inside the 1.5 m depth as much as possible. Options: narrower-beam antennas, recessing (Q2), or placing antennas at the gate's depth centre-line.
- For the overhead antenna, consider whether it is needed. It sees only the top layer edge-on (Q3), and its downward beam produces floor reflections that travel out along the floor. If kept, tilt it toward the gate centre and possibly reduce its power relative to the side antennas.

**Polarisation**
- Labels at the centre of roll ends rotate with the roll, so their dipole axis is random within the end-face plane. CP (as specified, RHCP) or dual-linear switching is appropriate.
- CP handedness reversal on reflection (RHCP → LHCP after a single bounce) does **not** prevent a linear tag from being powered by a reflected wave. CP gives no stray-read immunity with linear tags. This follows from the polarisation-matching argument in Nikitin & Rao; it is an inference.

**Time domain**
- Three antennas per gate and two gates should be time-multiplexed/scheduled so that only one antenna (or one gate) transmits at a time. Alternatively use dense-reader mode with frequency separation within 920–923 MHz.
- RF on only while a load is in the gate (photo-eyes or presence sensors) removes stray reads of parked loads and racks during idle time, which is likely the largest share of stray-read volume. Strictly this is a control measure, but it is physical/RF in effect.

**Power**
- Set per antenna by a ramp test: the lowest power reading 100% of the hardest target (bottom roll, far end, wettest cotton), plus a margin.
- Then map the stray zone at that setting (walk-test with reference tags at 1, 2, 3, 5 and 8 m from each opening and at rack heights).

### Gaps
- No Impinj/Zebra/Times-7/Keonn/Avery Dennison dock-door application note with explicit tilt angles, power settings or stray-distance data was retrieved in this session. Searches returned only general guides, and RFID Journal pages were blocked (403).
- No vendor guidance specific to fabric rolls on stackers was found.

## Q6. How large must a clear zone be in practice (published guidance or measured stray-read distances at dock doors)?

### Takeaway
No standard or peer-reviewed measurement giving a "required clear-zone distance" for UHF dock doors was found. Published design targets for engineered (shielded or absorber-lined) portals are on the order of **1–2 m of stray-tag exclusion**, and dock-door examples space portals about 3 m (10 ft) apart *together with RSSI filtering*. Physics says an unshielded gate at the Indonesian class-licence power (≤26 dBm EIRP) can power a boresight R6-P label at ~3–5 m in free space and ~6–9 m with constructive multipath. A 3 m clear zone is therefore plausible only if antennas do not boresight toward the zone, power stays at or below the class-licence level, reflectors near the openings are controlled, and RF is gated by presence sensors. With ISR power it is not sufficient as an RF boundary.

### Cited Findings
- [PATENT, SNIPPET] Enclosed multi-read portal design target: still exclude stray tags "within a reasonable distance of one or two meters (3 to 6 feet)". Another target is attenuation beyond 3–4 ft (1.0–1.3 m). — [US 12,099,892 "RFID multi-read portal"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12099892), [CA 3096197C](https://eureka.patsnap.com/patent-CA3096197C)
- [PATENT, SNIPPET] Dock-door example: portals spaced 10 ft (±2 ft); staging-area tags detected but ignored below an RSSI threshold. — [US 10,157,337](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10157337)
- [SURVEY] "Extensive experimentations with RFID portal systems, in order to analyze cross reading problems, are sparse." — [Borisenko & Li 2010](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- [FIELD DATA, abstract only] Keller, Thiesse & Fleisch (ICIS 2014): false-positive reads (tags unintentionally detected) are a key problem in a European retailer's distribution centre and were filtered by time-series analysis. No distances or rates in the abstract. — [AIS eLibrary](https://aisel.aisnet.org/icis2014/proceedings/DecisionAnalytics/14). A related ML study (NTNU 2018) separated true and false reads at up to 95.3% accuracy (SVM, using RSSI and phase features), illustrating that the residual RF stray reads are routinely handled in software — [NTNU Open](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2651195) [SNIPPET]
- [MODEL, this note] Boresight power-up ranges at 922 MHz (Q1 table):

| EIRP | Free space (−22 / −18 dBm tag) | Constructive two-ray bound |
|---|---|---|
| 26 dBm | 4.6 / 2.9 m | 9.2 / 5.8 m |
| 33 dBm | 10.3 / 6.5 m | 20.6 / 13.0 m |

  Off-boresight range scales as 10^(−ΔG/20), e.g., ×0.18 at 15 dB down and ×0.10 at 20 dB down.

### Inferences
- **The required clear zone is direction-dependent.**
  - On paths that leave through the gate's open ends at large angles from the side-antenna boresight (≥60–90° off-axis, assumed ≥15–20 dB down), free-space stray range at 26 dBm EIRP is ≲0.5–0.8 m. Multipath (×2) and reflections from the stacker, load and nearby metal can extend this to ~1–2 m and occasionally beyond.
  - Along the floor (overhead antenna + concrete at grazing angles) and through reflections off partitions, racks and the stacker, ranges of several metres are physically possible.
- **For Option A (side-by-side, no shielding, 3 m clear zone).**
  - The ACP-clad gate bodies already block the direct cross-gate path, if they are continuous metal and the antenna windows face inward only. The residual coupling is opening-to-opening around the gate ends.
  - With power at or below the class-licence level, inward-aimed antennas, sensor-gated RF and per-reader time-slotting, 3 m is in the plausible range.
  - It must be **verified by a walk-test**. It is not guaranteed, because multipath hot spots are site-specific (Dimitriou: coverage beyond the free-space volume).
- **For Option C (separate doors, 3 m clear zone, no storage).** This removes the neighbouring-gate path entirely. The same per-gate stray radius applies toward storage, and the same verification is needed.
- **For Option B.** Partitions and curtains can reduce specific line-of-sight paths by ~6–20 dB (diffraction-limited), but they do not shrink the clear zone in proportion to the 37–43 dB material rating. Unless absorber-faced, they add reflection paths.
- **Practical sizing method** (synthesis; no source prescribes it):
  1. Fix the per-antenna power by the hardest-target ramp test (Q5).
  2. Map stray reads with reference tags on a grid out to ~8–10 m from each opening, at heights 0.2, 1.0 and 1.8 m, across all hopping channels, with the stacker and a loaded rack in place.
  3. Set the clear zone at the outermost distance where reference tags are read, plus a margin. Alternatively, accept residual stray reads and rely on software filtering, which is out of scope here.

### Gaps
- No published measured stray-read distance distribution for UHF dock-door portals (with antenna, power and environment stated) was found. This is the single most important missing input; only an on-site walk-test can supply it.
- Bertolini et al. (RTSI 2017) and Keller et al. (ICIS 2014) likely contain quantitative false-read data, but full texts were not accessible in this session.
- No vendor (Impinj/Zebra/Times-7/Keonn/Avery Dennison) published clear-zone guidance was retrieved.
