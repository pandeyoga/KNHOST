# Industry practice & case studies: UHF RFID dock-door / warehouse-gate deployments (stray reads, cross-reads, direction, accuracy)

Scope note for the report writer: research date 27 Oct 2026. RFID Journal pages (rfidjournal.com) and urgentcomm.com block automated fetching (HTTP 403 / Cloudflare bot check), so facts attributed to those URLs come from search-engine excerpts of those pages, not a full read. Vendor statements are labelled **[VENDOR]**; academic or third-party measurements are labelled **[INDEPENDENT]** or **[ACADEMIC]**. Context (from the brief): IN gate + OUT gate (possibly side by side), 3 antennas per gate, passive labels on fabric-roll ends, stacker loads up to 6 rolls high, racks near the gates.

## 1. Real-world case studies: accuracy achieved, stray/cross-read problems, and the fixes applied

### Takeaway
Few public case studies publish both read rates and cross-read rates. The independent numbers that do exist show three things. Multi-door sites reach about 98–99% read rates (METRO 2007). A commercial "read-or-not" portal (Impinj xSpan) measured about 6% misses and about 2% cross-reads at a real logistics dock door (Alibaba/Peking Univ., 2022). Fully loaded pallets of cases historically read far worse (66% in the 2005 Walmart era). Vendor claims of 99.5–99.99% are rarely backed by a published method. The fixes seen in practice are layered: aim antennas and reduce power, add motion or photo-eye triggers, shield or absorb where needed, apply software filtering, and verify against the order or ASN.

### Cited Findings
**Independent / academic measurements**
- **[ACADEMIC/INDEPENDENT, 2022] RF-CHORD paper (Peking Univ., Alibaba, MIT, UCSD, Tsinghua).** The paper reports: "Our previous deployment experiments in the same scenario show that commercial read-or-not solution Impinj xSpan has ~6% miss-reading rate and ~2% cross-reading rate in the similar scene." The scene is the dock door of a warehouse distributing food and daily necessities to city delivery stations. — [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
  - The authors' own research system, RF-CHORD (8 antennas, 200 MHz bandwidth, localization-based), recorded 0% misses and 0.0025% cross-reads at the warehouse dock door. The test used more than 10,000 tags on crates, bottles, cans and rice, a 2 × 1 m region of interest between the two door poles, and 50–100 tags per trailer passing in 1–4 s. At a fresh-food store it recorded 0% misses and 0.0154% cross-reads. Caveat: this is a research prototype, not a product, and the authors are promoting it against the xSpan baseline. — [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
  - The paper frames the requirement as: 100–200 packages per pallet arrive in a burst, verification must finish within 2–3 s, and the range must be at least 3 m. Its comparison table describes a commercial reader as having about 10 m range, about 185 tags/s, and "Low" reliability (about 6% misses, about 2% cross-reads). — [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
- **[INDUSTRY TRIAL, Jan 2007] METRO Group DC near Hamm, Germany.** Checkpoint designed and installed 36 RFID dock-door portals to test simultaneous operation under ETSI EN 302 208, using a "four-channel synchronized approach". The tests reached a read rate of 98.5% or higher from multiple pallets wheeled through the doors at once, and about 4.5 million individual reads were recorded. No cross-read figure was published. — [Field Technologies Online, 16 Jan 2007](https://www.fieldtechnologiesonline.com/doc/checkpoint-systems-partners-with-metro-group-0001); [BakeryAndSnacks, 22 Jan 2007](https://www.bakeryandsnacks.com/Article/2007/01/22/Metro-s-RFID-tests-mark-milestone-for-Europe-company-says); [Urgent Comms](https://urgentcomm.com/?p=4408)
- **[INDUSTRY, about 2005, dated] Walmart early pallet/case program (secondhand summary).** Case-level read rates exceeded 90% on carts, 95% on DC conveyors and 98% at store trash compactors. Cases on fully loaded pallets averaged only 66%. — [IDTechEx / Printed Electronics World](https://www.printedelectronicsworld.com/articles/161/rfid-progress-at-wal-mart). The University of Arkansas RFID Research Center lab replicated dock doors, conveyors, impact doors, forklifts and pallet wrappers for this kind of testing. — [same source](https://www.printedelectronicsworld.com/articles/161/rfid-progress-at-wal-mart)
- **[ACADEMIC, 2017] Bertolini, Rizzi, Romagnoli, Volpi (Univ. Parma / UNIMORE).** The paper is motivated by dock-door warehouses where "many readers are usually installed in close proximity, each one monitoring a specific dock door". It proposes a software algorithm that discriminates cross-reads and detects direction "without the need for hard metal shields". The authors self-report reliability (correct direction plus elimination of cross-reads) of more than 90%. — [UNIMORE IRIS](https://iris.unimore.it/handle/11380/1188652); [UniPR](https://air.unipr.it/handle/11381/2839342)
- **[ACADEMIC, about 2010] Univ. of Ottawa survey of UHF portals.** The survey names two core problems: (1) read accuracy, meaning the reader misses tags inside the zone or reads tags outside it, and (2) cross-reading between portals. It notes "extensive experimentations with RFID portal systems, in order to analyze cross reading problems, are sparse". — [uOttawa RFID book chapter "Portal" (PDF)](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)

**Industry case studies (mostly vendor- or trade-press-reported)**
- **Klaipėdos Baldai (Lithuania, IKEA furniture supplier; trade press about 2011–2013).** Before RFID, IKEA stores filed 2–3 shipping-error claims per month. Integrator Autepra installed an interrogator at the loading ramp of each of 4 dock doors, plus onboard forklift computers that show the driver the reader data. Full deployment followed after a satisfactory test. No read or cross-read rates are given in the excerpts. — [RFID Journal](https://www.rfidjournal.com/news/rfid-helps-ikea-furniture-maker-eliminate-shipping-errors/83764/); [GeeNFC mirror, 2013-06-08](https://www.geenfc.com/en/News/Industry/2013-06-08/76.html)
- **Energy company tracking metal drums (RFID Journal).** In a crowded metallic site, the deployment built a metal-mesh shielding area around both readers. — [RFID Journal](https://www.rfidjournal.com/news/energy-company-tracks-metal-drums-via-rfid-lora/197627/)
- **Herman Kay (apparel; Cisper case study) [VENDOR].** Fixed readers at the shipping docks check cartons against the ASN "to insure that each shipment is complete and accurate". The study reports higher delivery accuracy and fewer chargebacks but gives no percentages. — [Cisper case study](https://www.cisper.com/en/case-studies/rfid-case-study-rfid-implementation-in-fashion-retail)
- **Southern Fried Cotton (apparel; Avery Dennison case) [VENDOR].** Avery Dennison reports discrepancy chargebacks down 98% and "carton unit accuracy" up "by 99.5%" (wording as published; unaudited). — [Avery Dennison case studies](https://rfid.averydennison.com/en/home/news-insights/case-studies.html), via search excerpt
- **Walmart + Hanes pilot (Packworld).** Cartons are read again at the 3PL dock door, RDC inbound and outbound, the store stockroom and the sales floor, so a read missed at one point is recovered at the next. The headline claims "100% tracking", but that comes from redundancy across read points, not from a single portal. — [Packworld](https://www.packworld.com/trends/logistics-supply-chain/article/22971183/rfid-supply-chain-pilot-walmart-hanes-achieve-100-tracking) (page returned 403; search excerpt only)
- **Unnamed "high-volume DC" [VENDOR, undated].** Mis-shipments fell from 14% to "99.7% accuracy", with 72% faster throughput and ROI in 5.5 months. Inbound portals match ASNs; outbound portals validate pallets before loading. No method is given. — [RFIDSupport.net](https://rfidsupport.net/dock-door-case-study/)
- **Textile / fabric-roll examples (thin evidence):**
  - Fabric rolls on a truck are read automatically as the truck passes an RFID "pike" (gate), and gates at stock-room exits serve as theft protection. — [ResearchGate: "The RFID technology in the textile industry"](https://www.researchgate.net/publication/260789575_The_RFID_technology_in_the_textile_industry) (attribution from search summary; full text not verified)
  - An RFID-based intra-supply-chain system for the textile industry was trialled at a distribution warehouse in Zhuhai, China. It reports better operational time, cost, lead time and inventory accuracy, with no gate-level read numbers. — [ResearchGate 220672085](https://www.researchgate.net/publication/220672085_RFID-based_intra-supply_chain_in_textile_industry)
  - **[VENDOR, iFactory, Jul 2026]** claims "99.5%" portal read accuracy for single-layer rolls through dock doors "at normal conveyor speed", and a 6–10 m typical open-air read range for a single tagged roll. It gives no figure for stacked rolls. — [iFactory blog](https://ifactoryapp.com/blog/fabric-roll-inventory-rfid-warehouse-management)
  - **[VENDOR]** Another iFactory page says dense fabric rolls cause near-field coupling that reduces read range, and recommends dual-reader portals with cross-polarised antennas to reach "98% or better". — [iFactory textile supply chain](https://ifactoryapp.com/industries/textile-manufacturing/rfid-textile-supply-chain-tracking) (via search excerpt)
  - GAO RFID mentions Milliken & Co. tagging fabric rolls, with no figures and no primary source. — [GAO RFID](https://gaorfid.com/rfid-ble-iot-drones-for-textile-and-fabric-finishing-and-fabric-coating-mills-industry/)
- **Lab vs field gap (vendor opinion).** "99% accuracy rates from perfect-world test labs" are common, but field operators report figures "closer to 96 or 97 percent in some warehouse and manufacturing environments". — [Acceliot, 29 Oct 2025](https://acceliot.com/deep-tech-rfid-a-next-generation-look-at-dock-door-discrimination/) **[VENDOR]**
- **Stationary "walls" of stray tags at dock doors (Impinj patent).** During loading, moving tags become stationary and accumulate in layers ("walls") of stray tags. In the patent's test, a 5° beam adjustment cut unique tags read from 43 to 22. — [US 12488207, "Techniques for automated beam adjustment for portal directionality"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12488207) (single test in a patent; indicative only)
- **Physical shielding cost.** A dock-door patent describes conventional metal shielding between doors as "often large and expensive", noting that cross-reads can still occur depending on how close goods are to a reader. — [US 7538676](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7538676)

### Inferences
- A realistic planning baseline for a conventional fixed-reader gate in a cluttered warehouse is a per-pass miss rate in the low single-digit percent and a cross-read or stray rate of about 1–2% before tuning (xSpan figures; Acceliot's 96–97% field figure). The ERP should therefore assume reads are incomplete and noisy, and reconcile against documents rather than treating raw reads as transactions.
- No published case reports reaching near-zero stray reads by a single measure. Sites that report good results combine tuned RF (aim and power), triggers, some shielding, and order or ASN reconciliation, which supports a layered recommendation for KNHOST.
- Stacked fabric rolls (6 high, labels on roll ends) resemble the "cases on a full pallet" problem more than single cartons. Inner and occluded tags are the hardest case, as the Walmart 66% figure shows, so worst-case stack testing is essential.

### Gaps
- No independent, published case study was found specifically for fabric-roll gates with stacked rolls on a stacker or forklift, with measured read, stray and direction rates.
- No public before/after cross-read rates for a specific fix (for example "shielding reduced cross-reads from X% to Y%") were found, apart from the patent's 43→22 unique-tag example.
- The METRO 2007 trial's cross-read results (EPCglobal TG34 / IBM analysis) were not located.
- Full texts of RFID Journal case studies could not be retrieved (bot protection), so details come from excerpts only.

## 2. Commercial portal products and their stray-read / direction features (claims vs validation)

### Takeaway
Every major vendor markets stray-read suppression and direction. Their techniques are beam steering, multi-antenna sequencing, RSSI and phase, and focused or "multilinear" antennas. Independent validation is almost non-existent. The one third-party figure found (xSpan: about 6% misses, about 2% cross-reads) is far from vendor claims of 99%+. Keonn's own documentation candidly calls RF-only direction a "best-effort estimate" that systems must be prepared to get wrong.

### Cited Findings
- **Impinj xSpan [VENDOR].** Phased array with 13 beams in 3 sectors; an on-board processor controls beam direction, orientation and polarisation. Marketed as able to identify the direction of tagged boxes or pallets when wall-mounted at dock doors. — [Impinj xSpan datasheet](https://rfid4ustore.com/content/data_sheet/Impinj_xSpan_Datasheet.pdf); [RFID Journal launch article](https://www.rfidjournal.com/?p=71128)
  - **Independent result:** about 6% misses and about 2% cross-reads at a real logistics dock door. — [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
- **Impinj xArray / ItemSense [VENDOR].** Location accuracy is "85% within 5 ft (1.5 m)" and "66% within 3.3 ft (1 m) in ideal conditions"; direction is "proven accurate even in difficult, real world environments", but no test is named. — [xArray product brief](https://rfid4ustore.com/content/data_sheet/Impinj_xArray_productbrief_110415-2.pdf). One Impinj document says xArray is in the end-of-life process and the gateway portfolio is "NOT RECOMMENDED FOR NEW DESIGNS". — [Impinj support attachment](https://support.impinj.com/hc/article_attachments/31850354064787)
- **Impinj xPortal (about 2010) [VENDOR].** Dual-linear phased-array antennas; Octane firmware offers a tag-direction estimate that needs 2 or 4 antennas; list price $2,495 in May 2010. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Impinj Gen2X [VENDOR].** Marketed to "reduce stray tag reads and improve verification accuracy as items move through dock doors". — [Atlas RFID Store](https://www.atlasrfidstore.com/rfid-insider/introducing-impinj-gen2x/)
- **SLS D-Series dock door (Impinj R700-based) [VENDOR].** Claims reader sensitivity allows low transmit power, which "minimizes the risk of cross-reads between adjacent read points", and a "99.99% scan rate accuracy". — [Impinj partner page](https://www.impinj.com/library/partner-solutions/sls-d-series); [Barcodesinc](https://www.barcodesinc.com/sls/d-series.htm)
- **Zebra ATR7000 [VENDOR].** Uses multiple antennas to detect whether a tag is moving into or out of a read zone, for example into or out of a truck. It must run in Zebra IoT Connector (ZIOTC) mode to deliver direction to third-party software. — [Zebra ATR7000 spec sheet](https://www.zebra.com/content/dam/zebra_dam/en/spec-sheets/atr7000-spec-sheet-en-us.pdf); [ClearStream integration note](https://support.clearstreamrfid.com/hc/en-us/articles/33802844552087). An integrator says the ATR7000 typically mounts 15–20 ft (about 4.5–6 m) high. — [EMPTech](https://emptechgroup.com/?p=29219)
- **Zebra FX9600 / Transition portal [VENDOR].** Positioned for pallets and cases through dock doors; the Transition portal's "specialized antennas tune out cross-talk, reducing erroneous reads". — [FX9600 spec sheet](https://www.zebra.com/content/dam/zebra_dam/en/spec-sheets/fx9600-specification-sheet-en-us.pdf); [Barcodesinc Zebra Transition](https://www.barcodesinc.com/zebra/transition-rfid-portal.htm/page=2/)
- **Zebra patent family (software cross-read arbitration).** Compares parameters from competing read events at adjacent readers, normalising one reader's readings against the neighbour's to decide which zone holds the item. — [US 10121031](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10121031); [US 9734368](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9734368)
- **Avery Dennison Dock Door Portal (2025 sell sheet) [VENDOR].** Two antenna towers (5 antennas each, about 2.5 m tall) and a reader in a NEMA enclosure. Optional light assembly and photo-eye kit "to interact with a user and help capture successful events". Publishes EPCIS events to atma.io. No accuracy figure. — [Avery Dennison Dock Door Portal PDF](https://supplychain.averydennison.com/assets/media/pdfs/Avery_Dennison_Dock_Door_Portal_USA.pdf)
- **Keonn AdvanNet direction (vendor documentation, unusually candid).** Requires more than one antenna with minimal pattern overlap, aimed in opposite directions or separated about 0.5–1.5 m along the travel axis; Gen2 Session 0, Target A/AB (may reduce read rate). Parameters include `minSamples` (e.g. 5), `inactivityPeriod` (e.g. 5000 ms) and `maxTime` (e.g. 20 s). The documentation says it worked in some scenarios and failed in others, is "a general-purpose, best-effort estimate", "is an estimate", and that systems must handle incorrect directions. — [Keonn wiki: Tag Direction AdvanNet 2.5.x](https://wiki.keonn.com/software/advannet/advanced-features/tag-direction-advannet-2-5-x). Keonn AdvanFlow-200 flags events as undetermined ("limit-type") when tags pass too fast, linger at an antenna, or move back and forth. — [Keonn wiki: AdvanFlow 200](https://wiki.keonn.com/rfid-systems/automatic-inventory-and-tracking/advanflow-200). AdvanPortal is marketed for DCs and small warehouses ("hundreds of tags in a few seconds"). — [Keonn AdvanPortal](https://keonn.com/systems-product/advanportal/)
- **PervasID Flow Ranger / Dock Door Ranger [VENDOR, about 2020].** Patented "virtual RF boundaries" set a read-area limit to cut cross-reads and determine direction; claims ">99%" direction accuracy and 400 tags/s. The company contrasts this with 80% accuracy levels as a framing; that is not a measured competitor figure. — [RFID Journal](https://www.rfidjournal.com/news/rfid-reader-detects-direction-to-enable-logistics-shrink-reduction/187352/); [RFID Journal webinar PDF](https://www.rfidjournal.com/wp-content/uploads/2020/07/RFID_Journal_Webinar_PervasID_Printronix_AutoID.pdf)
- **Turck UHF RFID gate [VENDOR].** Software "calculates where tags are located, filters out stray reads and identifies the direction of goods". — [RFID Journal](https://www.rfidjournal.com/?p=188185)
- **Intermec ARX (older) [VENDOR].** Used motion data, RSSI plus phase angle, to screen out tags near a reader that are not moving through the portal. — [RFID Journal](https://www.rfidjournal.com/news/intermec-releases-software-that-targets-tags-of-interest/82707/); [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Sirit "Stray Tag Elimination" (older) [VENDOR].** A tag must first be triggered at the portal; otherwise the portal reader ignores it as a stray. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Venture Research interior dock door portal [VENDOR, datasheet 2020-07].** Articulated mounts rotate antennas into the truck; a high-gain array allows lower RF power; built-in motion sensors switch RF on; an optional truck-in-position sensor keeps RF off until the truck door is open. These are presented as the three cross-read reducers. — [Venture Research](https://ventureresearch.com/?p=3162); [datasheet PDF](https://www.ventureresearch.com/wp-content/uploads/2020/07/Dock-Door-Portals-1.pdf)
- **"Multilinear" focused-beam antenna (RFID Journal product news) [VENDOR].** Designed to "prevent stray reads from neighboring dock doors or staging areas"; notes that in "a long bank of portal readers, stray tag reads and reliability problems can result". — [RFID Journal](https://www.rfidjournal.com/news/new-rfid-reader-aims-at-flexible-warehouse-roll-outs/202752/)
- **IDRO Glowfly (2018) [VENDOR].** Visible-light-plus-RFID tag chip marketed to resolve UHF stray reading. — [Newswire / Frost & Sullivan](https://www.newswire.ca/news-releases/idro-lauded-by-frost--sullivan-for-its-multi-application-visible-rfid-system-687985581.html)
- **Forklift-mounted readers as an alternative to fixed portals.** Readers mounted on MHE avoid fixed-portal bleed. — [RFID Journal](https://www.rfidjournal.com/news/companies-deploy-rfid-solution-leveraging-forklift-mounted-readers/202515/). The Klaipėdos Baldai case combined fixed readers with forklift displays. — [RFID Journal](https://www.rfidjournal.com/news/rfid-helps-ikea-furniture-maker-eliminate-shipping-errors/83764/)
- **Academic direction results (non-pallet).** A machine-learning method using per-antenna RSSI changes is cited at more than 98% direction accuracy (conditions unverified). — [ResearchGate: "Detecting Movement and Direction of Tags for RFID Gate"](https://www.researchgate.net/publication/343666800_Detecting_Movement_and_Direction_of_Tags_for_RFID_Gate). Tilted and phased-array approaches reached 100% direction of pass for passively labelled objects in a small experiment. — [ResearchGate: "RFID-based People-object Direction of Pass Detection"](https://www.researchgate.net/publication/308043199_RFID-based_People-object_Direction_of_Pass_Detection). RF motion detection (HMM) reached 89.5% with people moving around, while earlier algorithms reached only 40–65% for moving objects. — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S221418041730017X)

### Inferences
- Direction from RF alone should be treated as a secondary signal. KNHOST already has physically separate IN and OUT gates, so "which gate plus photo-eye sequence" gives direction more reliably than RF phase or RSSI inference. RF direction can serve as a consistency check.
- Expensive beam-steering readers (xSpan-class) do not by themselves solve cross-reads in a real dock scene, as the independent 2% figure shows. Product choice matters less than tuning, triggers and reconciliation logic.
- Software arbitration between adjacent gates (Zebra patent: compare RSSI or read counts of the same EPC at both gates and assign it to the stronger one) is a well-established idea that KNHOST can implement in middleware or ERP if both gates' raw reads, with antenna and RSSI, are retained.

### Gaps
- No independent validation of Zebra ATR7000 direction accuracy, Keonn AdvanPortal, Mojix, Times-7, Nedap, SML or Checkpoint dock-door stray-read performance was found. Searches for Mojix, Times-7 and Nedap dock-door products returned nothing specific.
- ARC/Auburn has no published test of portal direction accuracy (see section 5).

## 3. Sensors and triggers (photo-eyes, light curtains, motion/radar, door/forklift detection, stack lights)

### Takeaway
The most widespread industry approach is to turn the reader on only while a load is physically in the gate, and to use two sequential photo-eyes (A→B vs B→A) for direction. Motion sensors and truck-present sensors are common variants. Stack lights or light-plus-buzzer kits give the operator feedback, and some sites run only one door's RF at a time to eliminate cross-reads.

### Cited Findings
- "The most widespread solution" for direction of movement is photo eyes or electric-eye sensors. Alternatives are a second set of antennas further down the portal, or RSSI and angle-of-arrival alone. Examples: Gaotek, where a photo eye turns the reader on and two photo eyes give direction; Autocrib, with photo-beam sensors at the entrance; Alvin, with photoelectric motion sensors. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Two-sensor direction state machine (patent).** Inputs A and B; whichever beam breaks first gives the direction; if B is not blocked before a timeout, the state resets. — [US 8203427 "RFID direction trigger driver"](https://patents.google.com/patent/US8203427)
- Photo-eyes mounted relative to the portal trigger the reader when an object breaks the line of sight and passes through, which reduces reads of tags passing near but not through the portal. — [US 10096218](https://patents.google.com/patent/US10096218)
- **Forklift traffic management (Soylemezoglu et al., cited in the uOttawa survey).** Portals with antennas, light stacks and motion sensors. A "read it when you need it" on/off power-control protocol switches antennas on according to motion sensors, "making sure that only one dock door is active at any one time, so that the cross-reading problem is avoided". Light stacks synchronise forklift movements with antenna power. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Reader-coordination alternative.** METRO ran 36 doors simultaneously using a synchronised four-channel ETSI scheme rather than time-slicing. — [Field Technologies Online](https://www.fieldtechnologiesonline.com/doc/checkpoint-systems-partners-with-metro-group-0001). The simplest multi-reader fix is TDMA, where readers operate in different time slots. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Pitfall: fixed-duration triggers.** In one software (ClearStream), a tripped photo-eye turns the reader on for a fixed 10 s; it cannot stay on while the sensor is blocked or switch off when it clears. A slow stacker could outlast the window. — [ClearStream support](https://support.clearstreamrfid.com/hc/en-us/articles/33387576584983)
- Motion sensors switch RF on only when there is motion at the dock; a truck-in-position sensor keeps RF off until the trailer door is open. — [Venture Research](https://ventureresearch.com/?p=3162) **[VENDOR]**
- Trigger types listed by an Asian reader vendor: photoelectric sensors, ground loops, PLC signals, vehicle detectors. — [IFAST rfid-life, about 2023](https://industrial.rfid-life.com/news/RFID-dock-door-reader.html) **[VENDOR]**
- Two GPIO sensors define direction (first then second = check-in; reverse = check-out) and can start inventory when an item is detected. — [RFID4U Store, Nov 2024](https://rfid4ustore.com/rfid-blog/implementing-rfid-in-dock-door-comprehensive-guide/) **[VENDOR]**
- Avery Dennison offers an optional light assembly and photo-eye sensor kit with audible cues for operator feedback. — [Avery Dennison Dock Door Portal PDF](https://supplychain.averydennison.com/assets/media/pdfs/Avery_Dennison_Dock_Door_Portal_USA.pdf)
- Forklift-mounted readers accept an external photo eye or user-triggered switch to control reading. — [Venture Forklift datasheet](https://gatewayrfidstore.com/product_images/Venture%20Forklift.pdf)
- Surgere publishes a photo-eye and reflector-tape alignment guide for its portals, which shows that alignment is a maintenance item. — [Surgere PDF](https://go.surgere.com/hubfs/Photo%20Eye%20and%20Tape%20Alignment%202021_12_20.pdf)
- **Costs (dated, May 2010).** Basic portals start around $1,000; sophisticated portal enclosures run about $2,000–3,000. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)

### Inferences
- For KNHOST: put two photo-eyes, or a short light curtain, per gate along the travel axis so the ERP or middleware receives (a) a read window that is open only while the stacker is in the gate and (b) a hardware direction. Use "sensor-state-controlled" windows (on while blocked, plus a short tail) rather than fixed timers.
- If the IN and OUT gates are side by side, an interlock that prevents both gates' RF being active at once is the cheapest proven cross-read eliminator (Soylemezoglu). The cost is throughput when both gates are busy simultaneously, so it should be configurable.
- A stack light (green = matched to document, red/amber = exception) plus an ERP screen for confirmation is standard practice and inexpensive.

### Gaps
- No published comparison of photo-eye vs light-curtain vs radar triggers for forklift or stacker gates, and no current cost data, was found. 2010 prices are the only figures.
- No source quantified how much triggers alone reduce stray reads.

## 4. Process controls: manifest reconciliation, staging rules, clear zones, lanes, operator confirmation, exceptions

### Takeaway
Industry practice treats gate reads as evidence to be reconciled against an expected document (ASN, PO, picking list or delivery order), not as self-standing transactions. Unexpected tags become exceptions, not postings. Staging too close to portals is a recognised cause of false events, but no published standard distance ("no storage within X m") was found. Exclusion zones are set per site by survey and validated with negative tests.

### Cited Findings
- Inbound portals capture tags and match ASNs automatically; outbound portals validate pallets before loading so the correct shipment reaches the correct trailer. — [RFIDSupport.net case](https://rfidsupport.net/dock-door-case-study/) **[VENDOR]**
- Outbound verification compares cartons to the manifest or ASN before the truck leaves; a carton from another order, or a missing carton, is flagged before the truck is sealed. — [Clustag](https://clustag.com/rfid-solution/dock-shipping-validation/); [Barcoding Inc.](https://www.barcoding.com/blog/rfid-outbound-shipment-verification-at-dock-door-benefits) **[VENDOR]**
- Edge or middleware software filters stray and duplicate reads, groups tag activity into movement events, and checks them against ASN or manifest data before posting to the WMS or ERP. — [RFID4U, Dec 2025](https://rfid4u.com/enabling-your-dock-doors-with-rfid/); [Rocket RFID](https://www.rocketrfid.com/dock-doors) **[VENDOR]**
- **Pallet association.** Item tags are tied to a pallet-level tag so software can disregard tags whose IDs are not "married" to the pallet being processed. — [RFID Journal on IDRO](https://www.rfidjournal.com/news/to-thwart-stray-rfid-reads-idro-develops-glowfly/75348/)
- **Time-threshold rules.** Ignore tags that appear for only about a second and then disappear. These thresholds "must be set with care" because they reject data. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- **Gen2 session choice** affects whether tags read at one door "re-present themselves at the next door a few seconds later"; when duplicate reads spike, sessions are often part of the diagnosis. — [RFID Journal expert view](https://www.rfidjournal.com/expert-views/uhf-rfid-sessions-the-hidden-flag-that-makes-or-breaks-your-read-performance/224994/)
- **Acceptance-oriented process rules [VENDOR, RFIDSolution 2026].**
  - Define whether each portal is inbound, outbound or both.
  - Detect reversals and delay final status until movement is confirmed.
  - Define the minimum event condition (single read, repeated reads, or a movement sequence).
  - Record "valid read boundary and exclusion zones" at commissioning, and retest whenever reader power changes.
  - The article warns that staging too close to a portal causes false events, but gives no distance. "The exact numbers should be set by project risk."
  - Source: [RFIDSolution: RFID Read Zone Acceptance Criteria for Warehouse Portals](https://rfidsolution.com/?p=58980)
- No published rule sets a staging distance from an RFID portal; the guides found discuss staging only qualitatively. — [RFID4U](https://rfid4u.com/enabling-your-dock-doors-with-rfid/); [rfrain doorway guide](https://rfrain.com/how-to-install-a-fixed-rfid-reader-on-a-30x20-doorway-for-maximum-read-accuracy/)
- **Parallel-pass stray reads.** Tags passing along and parallel to a portal within tag range, without passing through, get read. Reducing transmit power helps only if all tags have similar read range. — [US 8717145](https://patents.google.com/patent/US8717145)
- **Read-range context.** A single tagged roll reads at 6–10 m in open air with a standard UHF reader [VENDOR]. — [iFactory](https://ifactoryapp.com/blog/fabric-roll-inventory-rfid-warehouse-management). A commercial dock reader's range is about 10 m. — [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
- **Redundant read points.** Walmart/Hanes re-read cartons at successive nodes so a missed read is caught downstream. — [Packworld](https://www.packworld.com/trends/logistics-supply-chain/article/22971183/rfid-supply-chain-pilot-walmart-hanes-achieve-100-tracking)
- **Operator in the loop.** Klaipėdos Baldai put reader results on onboard forklift computers so drivers see what was read. — [RFID Journal](https://www.rfidjournal.com/news/rfid-helps-ikea-furniture-maker-eliminate-shipping-errors/83764/)

### Inferences
- Because open-air tag range (6–10 m) exceeds 3 m, a 3 m clear zone alone does not guarantee rack tags will not be read; reflections off metal racks can also bring in tags from further away. The clear zone works only together with reduced power, down-tilt or aimed antennas, an RSSI floor and trigger windows. Its size should come from a site survey: measure the farthest distance at which rack tags still read at the chosen power, then add margin. A zone set without that measurement is guesswork in both directions; it may be too small, or it may waste rack capacity.
- **Strongest software control for KNHOST:** every gate event must be tied to an open document (OUT: the delivery order or picking list being loaded; IN: the expected receipt, PO or transfer).
  - Matched EPCs post automatically.
  - Unexpected EPCs (for example a roll still sitting in a rack) go to an exception queue for operator confirmation and are never auto-posted.
  - Expected but unread EPCs require a manual or handheld rescan before closing.
- One-direction lanes (IN gate used only for IN, OUT gate only for OUT), plus a "no parking or no staging inside the gate zone" floor marking, are low-cost process rules consistent with the negative test cases vendors recommend.

### Gaps
- No industry-standard or published "clear zone" distance (in metres or feet) was found from GS1, Auburn, vendors or integrators.
- No GS1 implementation guide covering dock-door process rules was retrieved; the relevant GS1 documents were not found within the search budget.

## 5. Acceptance criteria, KPIs and test methodology for pilots

### Takeaway
No published standard sets pass or fail thresholds for dock-door portals. The practitioner consensus is to measure at least three things separately: the capture or read rate of intended tags, the false-event rate (stray or cross-reads) with adjacent gates and staged goods present, and door or direction assignment accuracy. Vendor guidance suggests thresholds of a read rate above 99% and a false-read rate below 0.1% of events. Formal test-method standards exist (ISO/IEC 18046-1, ASTM D7434 for pallets) but are behind paywalls.

### Cited Findings
- **Suggested KPIs [VENDOR].**
  - Read rate above 99% for expected tagged units, and a false-read rate below 0.1% of event volume, with miss and false-read rates measured separately.
  - Prototype at operating speed with real goods, representative packaging and realistic tag placement, then tune power, angles, RSSI thresholds and trigger logic.
  - Confirm that events reach the WMS or ERP within the required window.
  - Source: [IFAST rfid-life, about 2023](https://industrial.rfid-life.com/news/RFID-dock-door-reader.html)
- **Acceptance metrics [VENDOR, 2026].**
  - Metrics are "intended read capture", "false movement rate" and "door assignment accuracy". A portal that "reads 99% of tags can still fail if it creates false shipment records".
  - Negative test cases: tagged pallets parked beside the portal; returns near receiving; a forklift pausing at the portal edge; reversing pallets; tags visible to two portals; product left near the portal after movement; and adjacent doors active.
  - Commissioning record: reader model and firmware, antenna type and position, power settings, product groups tested, read boundary and exclusion zones, false-event results, WMS rules, exception process and retest triggers.
  - Source: [RFIDSolution](https://rfidsolution.com/?p=58980)
- **ISO/IEC 18046-1:2011** defines test methods for RFID system performance (item management), to help select devices for an application. — [ISO 18046-1](https://www.iso.org/standard/46150.html). Part 2 (interrogators, 2020) and Part 3 (tags, 2020) also exist. — [ISO 18046-2](https://www.iso.org/standard/74387.html); [ISO 18046-3](https://www.iso.org/standard/75900.html). The 2006 predecessor calls its methods "a basic framework… not exhaustive", defined for single-antenna devices. — [ISO 18046:2006](https://www.iso.org/standard/43174.html)
- **ASTM D7434** is a test method for the performance of passive RFID transponders on palletised or unitised loads, listed with D7435 (loaded containers) and D7580 (stretch-wrapper readability). Content was not verified. — [Gialer standards overview](https://www.gialer.com/blogs/news-and-blogs/rfid-standards-and-protocols-you-must-know)
- **Auburn University RFID Lab.** It describes itself as having pioneered most modern retail RFID testing practices. Its dock-door demo setup uses 4 antennas and 1 reader; no protocol or metrics were published in the source. — [Atlas RFID Store: Auburn RFID Lab Part 3](https://www.atlasrfidstore.com/rfid-insider/auburn-rfid-lab-part-3-rfid-portals-warehouse). An Auburn paper on apparel supplier DCs projects that item-level quantity audits could cover "over 99.99% of all cartons". This is a projection, not a measured portal test. — [Auburn RFID Lab: Item-level Quantity Auditing for Apparel Supplier DCs](https://rfid.auburn.edu/papers/pages/RFIDItem-levelQuantityAuditingforApparelSupplierDistributionCenters.php) (site certificate error on fetch; via search excerpt)
- **Academic portal test design (Cal Poly thesis, 2010).** Read-rate differences in a UHF doorway portal studied as a function of antenna placement, door size and composition, reader manufacturer, tag type and tag orientation, using ordinal logistic regression. — [Cal Poly Digital Commons](https://digitalcommons.calpoly.edu/theses/275)
- **Ground-truth style of measurement (RF-CHORD).**
  - More than 10,000 tagged items with a known region of interest; miss rate and cross-read rate reported separately.
  - Tested in two real sites: 0% / 0.0025% and 0% / 0.0154%.
  - Source: [arXiv 2211.00272](https://arxiv.org/pdf/2211.00272)
- **Simultaneous operation of adjacent doors** was the explicit purpose of the METRO 36-door ETSI trial. — [Field Technologies Online](https://www.fieldtechnologiesonline.com/doc/checkpoint-systems-partners-with-metro-group-0001)
- Calibrating and re-verifying portals is an ongoing need; there is a patent on "calibration and operational assurance" for RFID object-monitoring systems. — [US 8451121](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8451121)
- Site survey → install → tune → calibrate is the vendor-recommended sequence. — [RFID4U Store portal deployment checklist](https://rfid4ustore.com/rfid-blog/rfid-portal-deployment-checklist-from-site-survey-to-calibration/)

### Inferences
- **Suggested KNHOST pilot protocol, synthesised from the above (not a published standard):**
  1. Build a ground-truth EPC list for each test load.
  2. Run at least N repeated passes per configuration: 1, 3 and 6 rolls high; tags facing toward and away from the antennas; fastest and slowest stacker speed.
  3. Run each scenario with the other gate idle and then active simultaneously.
  4. Run negative tests: stacks parked 1/2/3 m beside the gate and in the nearest racks, the stacker pausing at the gate edge, and reversing out.
  5. Report separately:
     - per-tag capture rate
     - stray or false-event rate (events per pass with tags not in the load)
     - gate assignment accuracy (IN vs OUT)
     - direction accuracy
     - end-to-end document-match rate after ERP logic
- Reasonable targets drawn from vendor guidance and the METRO benchmark: capture of at least 99% after reconciliation (raw per-pass capture may be lower, at about 96–99%), with zero unconfirmed false postings into the ERP. Stray reads still occur but must be caught by the exception queue. Raw stray events per pass should be tracked as a tuning KPI rather than demanded to be zero.

### Gaps
- No ARC/Auburn or GS1 dock-door test protocol with numeric pass thresholds was found publicly. ARC focuses on tag-level performance specifications, and its portal test method is not published.
- The full texts of ISO/IEC 18046-1 and ASTM D7434 were not reviewed (paywalled).

## 6. Common pitfalls (metal racks, forklifts, multipath, tag placement, moisture, orientation) and physical mitigation materials

### Takeaway
The recurring pitfalls are:
- reflections from metal (racks, dock doors, forklifts) that create stray reads and dead zones;
- stationary tagged goods near the gate;
- simply turning power up, which creates cross-reads rather than fixing misses;
- occluded inner tags in dense stacks;
- tag orientation and placement.

Physical isolation exists in two forms. Reflective metal (mesh, partitions) blocks but also reflects energy. RF absorbers, such as foam or ferrite panels and absorber or reflector "isolation curtains", reduce reflection. Absorbers must not starve the wanted read zone. Shielding paint figures are vendor claims and require grounding.

### Cited Findings
- Portal readers often record idle pallets, adjacent conveyor traffic or "stray reflections off metal shelving"; metal dock doors, trailers, stacked pallets and moving forklifts add interference. — [Acceliot, Oct 2025](https://acceliot.com/deep-tech-rfid-a-next-generation-look-at-dock-door-discrimination/) **[VENDOR]**
- Variable reflections off moving objects such as forklifts and other metal items, and interference from readers at adjacent dock doors, complicate verification. — [US 10157337 "Pre-notification with RFID dock door portals"](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10157337)
- **Practical installation rules [VENDOR, IFAST about 2023].**
  - Mount antennas 3–6 m high and tilt them 15–30° down to focus on the lane and reduce reflections; at warehouse gates, mount on both sides at about 45°. Prefer circular polarisation.
  - Use the minimum power the distance requires, typically 18–30 dBm, and adjust receive sensitivity to filter reflected signals. "Raising power doesn't reliably fix missed reads and can create false reads in adjacent lanes."
  - Metal coverage above about 40% raises error rates. Above 85% humidity, ordinary labels can lose 12–18% of read range; PET composite labels lose under 5%.
  - Place tags at least 30 cm above the pallet base.
  - Source: [IFAST rfid-life](https://industrial.rfid-life.com/news/RFID-dock-door-reader.html)
- Read-rate drivers are tag orientation, pallet density, metal or liquid, and reader placement. — [RFID4U](https://rfid4u.com/enabling-your-dock-doors-with-rfid/) **[VENDOR]**
- Increasing read accuracy (more antennas or power) enlarges the zone and worsens cross-reading in multi-portal systems. — [uOttawa portal chapter](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- Dense fabric rolls cause near-field coupling that reduces read range. — [iFactory](https://ifactoryapp.com/industries/textile-manufacturing/rfid-textile-supply-chain-tracking) **[VENDOR]**
- Cases inside fully loaded pallets averaged 66% read rate in early Walmart-era reads. — [Printed Electronics World](https://www.printedelectronicsworld.com/articles/161/rfid-progress-at-wal-mart)
- **RF isolation curtains (MWT MAC-9101).** RF-reflective exterior panels with RF-absorbing coupled interior panels "reduce signal leakage, reflection and crosstalk" in RFID tunnels; made to size and waterproofable. A see-through safety panel can cover up to 20% of the curtain area. Users include Marel (fish processing) and McCarran International Airport (baggage tunnels). No dB attenuation figure is published. — [RFID Journal (MWT, about 2016)](https://www.rfidjournal.com/?p=71920); [RFID Journal (MWT users)](https://www.rfidjournal.com/?p=71930)
- Absorber treatment "must be designed in such a way that the desired illumination of the pallet is unaffected". — [US 7369050 "Curtain for isolating radio propagation zones"](https://patents.justia.com/patent/7369050)
- **Absorber benchmark [VENDOR].** FHI "TLF" absorber plates typically absorb -18 dB across 800 MHz–1 GHz. — [FHI](https://fhi.nl/en/news/rfid-signaal-absorber)
- **Shielding paint [VENDOR claims].**
  - YShield HSF54: about 39 dB (1 coat), 49 dB (2 coats), 59 dB (3 coats) at 1 GHz; grounding required. — [Desertcart listing](https://www.desertcart.ae/products/377650653-yshield-hsf54-paint.md)
  - Proshield: 32 dB at 900 MHz. — [Architect at Work](https://www.architectatwork.com/en/curated/innovations/proshield-radiation-shielding-paint-1810558)
  - Auro notes that ungrounded conductive coatings reflect high-frequency fields and cannot discharge accumulated voltage, so it recommends an electrician for grounding. — [Auro Thema 332](https://webedition.auro.de/downloads/pdf_e/Thema_332_e.pdf)
  - Shielding effectiveness depends on frequency; a rating measured at one frequency does not apply at another. — [MG Chemicals](https://mgchemicals.com/knowledgebase/how-is-emi-rfi-shielding-measured/)
- Absorber material choices for RFID projects include ferrite, carbon-loaded foam and specific polymers; frequency range and bandwidth are the key selection factors. — [RFID4U: Understanding RF Shielding](https://rfid4u.com/understanding-rf-shielding-in-rfid-projects/)
- Shielding between doors is "often large and expensive", and cross-reads can still occur. — [US 7538676](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7538676)
- A small beam re-aim (5°) roughly halved unique stray tags read (43→22) in one patent test. — [US 12488207](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12488207)
- Venture Research reduces cross-reads by aiming antennas into the trailer and lowering power via high-gain antennas. — [Venture Research](https://ventureresearch.com/?p=3162) **[VENDOR]**

### Inferences
- **For KNHOST's physical options:**
  - (a) Bare aluminium partitions between side-by-side gates block the direct path but are reflective. They can bounce energy toward racks or back into the gate, so they should be lined with absorber on the gate-facing side, or combined with aiming and power reduction, and validated with negative tests.
  - (b) Shielding paint has vendor-claimed attenuation of about 30–40 dB per coat near 900 MHz–1 GHz. It acts as a reflector, needs proper grounding, and has no independent dB data at UHF in the sources found. It is best treated as an optional add-on for a specific wall behind racks, not as a primary measure.
  - (c) Ordinary PVC strip curtains are dielectric and should be largely RF-transparent. This is a physics-based inference; no source measuring it was found. Only purpose-built absorber or reflector curtains (MWT-type) provide isolation, and they need a see-through safety window for stacker traffic.
- The cheapest first moves, all supported by sources: antenna down-tilt and aiming, minimum power, RSSI floor, trigger windows, and beam re-aiming. Physical shielding should follow only where post-tuning negative tests still show stray reads.
- Tag placement on the roll end matters. Labels on the end face are perpendicular to a side-mounted antenna when rolls are carried horizontally, so the three-antenna layout (for example two sides plus overhead) should be validated with worst-case roll orientation and the 6-high stack, where middle rolls are occluded.

### Gaps
- No independent measurement of shielding-paint or curtain attenuation at 860–960 MHz (or the Indonesian band, 920–923 MHz) was found.
- No published data on moisture effects specific to fabric rolls (cotton or greige vs finished) at UHF was found; the humidity figure above is a generic vendor claim.
- No source quantified the effect of 3 m vs larger clear zones on stray-read rates.
