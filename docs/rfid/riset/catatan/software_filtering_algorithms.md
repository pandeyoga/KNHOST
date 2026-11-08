# Software / algorithmic methods to suppress stray reads and decide IN/OUT transactions at UHF RFID portals (dock doors / warehouse gates)

Scope note for the writer: this file separates (1) **RF stray reads** (a tag that should not have been heard was heard) from (2) **wrong transactions** (the system books an IN/OUT for a roll that did not pass, or misses/duplicates one). Software can only work on (2) using whatever per-read data the reader delivers; it cannot remove (1) from the air. Every accuracy figure below is tied to its test conditions. Items marked "search snippet only" were seen in search-engine abstracts but the full text could not be opened (403/paywall) — treat them as weaker evidence.

Context mapping used in the Inferences: the KNHOST gate (3 antennas: left, right, overhead, all roughly in one plane; stacker up to 6 rolls high; separate IN and OUT gates) is closest to what Keller et al. call a **"Standard Portal"** (4 antennas, 2 per side, one plane) — not to their two-plane "Satellite"/"Transition" portals.

---

## 1. Which signal features separate moving target tags from static/stray tags, and what accuracy is reported?

### Takeaway
In the largest real-world dataset (METRO DC, ~54,000 labelled pallet reads), RSSI-derived features (max, range, std-dev of RSSI over the read window) separate "moved" from "static" tags at ~94–96% per-tag accuracy with a single threshold, while first/last-seen timestamps and per-antenna read counts on a single-plane portal carry almost no information (~75–79%, i.e. barely above "everything is static"). Antenna *order* only becomes a strong feature when antennas are placed in two separated planes along the travel axis; phase/Doppler add information but require vendor-specific reader data and degrade badly when moved from lab to shop floor.

### Cited Findings
**Keller, Thiesse, Kungl, Fleisch (IEEE IoT 2010) — real production data, single-attribute thresholds**
- Setting: METRO Group Cash & Carry central distribution centre, Unna (Germany); all 70 shipment dock doors had RFID portals; a motion sensor starts the reader; a "gathering-cycle" lasts ~5 s and most tag events occur in the first 3.5 s; 4 antennas per reader. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Stray-read causes they observed: pallets buffered temporarily near the portal, another forklift passing the portal during the gathering-cycle, and a pallet being loaded at an **adjacent portal**. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Data: 7 months, students labelled every pallet read as moved or static in custom software; 53,998 pallets, of which 40,743 static and 13,245 moved (≈75% of all read tags were strays). — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Per-read tuple used: (EPC, RSSI, SinceStart timestamp, Antenna); features are aggregations per tag per cycle (RSSI min/max/diff/mean/stddev; first/last/duration of reads; read count per antenna and total). — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Overall per-tag accuracy with an information-gain-optimal single threshold: RSSI MAX 95.69%; RSSI STDDEV 94.71%; RSSI DIFF 93.95%; RSSI MEAN 91.32% (threshold −58.1 dBm, information gain 0.440); RSSI MIN 75.47% (no information). All SinceStart (first-seen, last-seen, read duration) attributes 75.47% = no discrimination. Read count total 75.47%; ANT1 count 78.62%; ANT2 count 77.26%. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- RSSI std-dev of moved tags typically 4–8 (dB), static 0–3; a large number of static tags responded only once (std-dev 0). Moved tag "best case": RSSI rises, peaks (~1.25 s), then falls as the pallet passes the antenna plane. But "normal cases" include a moved pallet read only in the first 0.5 s, a moved pallet with near-constant RSSI for 3 s, and a static pallet showing a "moved-tag-like bump". — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)

**Keller, Thiesse, Ilic, Fleisch (~2010/2012) — antenna geometry as a feature**
- Same DC, 3,500–8,000 pallet movements/day; 79 Standard, 4 Satellite and 8 Transition portals. Stray prevalence among read tags: Standard 75.47% (53,988 pallets; ≈3 static per moved), Satellite 86.66% (14,777; ≈6.5 static per moved), Transition 90.19% (13,845; ≈9.2 static per moved) — i.e. more antennas hear more strays. — [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)
- Order features with two planes: if a tag was first seen by the truck-side antennas (SeenFirst = Truck), it was static with 93.6% probability; 95.9% of moved pallets were last detected by the truck-side antennas. Tags read only by the DC-facing antennas *after* the stop trigger: all 2,122 were static; tags read by DC antennas in any combination: 3,225 of 3,247 static (99.32%). Transition portals: tags read only by DC-side or only by truck-side antennas: 10,095 of 10,154 static (99.42%). — [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)

**Phase / Doppler / trajectory features (mostly lab)**
- Ma, Wang & Wang (Expert Systems with Applications, 2017): 11 statistical features from RSS and phase rotation; logistic regression, SVM, decision tree; SVM best, "up to 95.3%" accuracy (search snippet only; another snippet cites "average accuracy of 93%" for an RSS+phase false-positive detector). — [Ma et al. 2017](https://www.sciencedirect.com/science/article/abs/pii/S095741741730622X)
- Single-antenna direction study (Sensors 2026, Zebra FX9600 + AN510 antenna, 915 MHz): the linear trend (slope) of RSSI or phase over the pass was the main direction predictor; lab conveyor (0.2/0.4/0.8 m/s, 2,400 direction samples) reached 99.8% ± 0.5% with classical ensembles; but zero-shot transfer to a shop floor (manual pallet truck, 1 m and 2 m) dropped some tags to ~8–54%, a model trained at 1 m tested at 2 m fell to ~50%, and only after domain adaptation/augmentation did accuracy recover to >96–97% (some tags 83–89%). Earlier work cited there (Faria et al.): classical classifiers on short phase+RSSI sequences, left vs right, 75–90% on a lab conveyor without shop-floor validation. — [Sensors 2026, PMC13210675](https://pmc.ncbi.nlm.nih.gov/articles/PMC13210675/)
- Doppler: a 2025 analysis states commercial-reader Doppler measurements "are currently not precise enough for the majority of applications" because of weak tag signals and short reply durations; for an Impinj R700 in Mode 290 the minimum detectable speed is ~1.1 m/s at −95.8 dBm tag signal but ~0.02 m/s at −60 dBm; 1 m/s gives only ~6 Hz Doppler at 900 MHz. — [arXiv 2505.21812](https://arxiv.org/html/2505.21812v1)
- Phase across hopping channels (Intel patent, filed 2020): motion is detected from RSSI residual/std-dev plus the linearity of the phase-vs-frequency curve across the reader's hopping channels (static tag ≈ straight line), without phase unwrapping, aimed at dense, low-read-rate populations; it states prior high-read-rate approaches were limited to <100 tags. Tested at 250–1,000 tags; numeric accuracy only in figures (not extracted). — [US11620465B2](https://patents.google.com/patent/US11620465B2/en)
- HMM-based motion detection with passive UHF tags (RSSI-based): 89.5% with four people performing real medical activities. — [ScienceDirect S221418041730017X](https://www.sciencedirect.com/science/article/pii/S221418041730017X)
- Practitioner note: phase angle "has proven difficult to analyse as it wraps around"; phase/Doppler only on Impinj readers in that project, whereas PeakRSSI works with all LLRP readers. — [CrossMgrImpinj notes](https://www.sites.google.com/site/crossmgrsoftware/project-updates/crossmgrimpinj22111greatlyimprovedrfidaccuracy)

### Inferences
- For a single-plane 3-antenna gate (KNHOST), the evidence says the most useful features are the **RSSI trajectory per tag** (peak height, rise-peak-fall shape, std-dev/range) and *relative* RSSI versus the other tags of the same load — not read count, not first/last-seen, and not per-antenna counts (which Keller found nearly useless on a one-plane portal).
- Antenna *sequence* becomes powerful (93–99% precision rules) only if read zones are separated along the travel axis (inside-facing vs outside-facing). With left/right/overhead in one plane, sequence information is weak by geometry, so software alone cannot reproduce Keller's two-plane results.
- All trajectory/phase methods need **per-read reports** (every read with timestamp, antenna, RSSI, ideally phase + channel), not one "tag seen" message per cycle. Readers or middleware that deduplicate before the ERP side destroy exactly the data these methods need.
- Lab accuracies (95–99.8%) do not transfer automatically; the Sensors 2026 result shows site- and distance-specific re-training is needed.

### Gaps
- Full text of Ma et al. 2017 (setup, dataset size, test conditions) could not be retrieved; numbers are from search snippets.
- No published study found with stacked fabric rolls / tags on roll ends / stacker trucks; all large-scale data is pallet-on-forklift.
- No source found quantifying overhead-antenna vs side-antenna RSSI differences as a classification feature.

---

## 2. Machine-learning approaches for portal stray-read / false-positive classification: features, accuracy, labelled data

### Takeaway
Supervised classifiers (decision trees with boosting, SVM, random forest, MLP) on per-tag aggregates of RSSI/time/antenna reach roughly 93–99% per-tag accuracy in published work; the only large production study (Keller) reached 97.57% with a single-plane portal and 99.04% when extra antennas were added. The price is labelled data collected at the actual site (Keller: 7 months, ~54k pallets labelled by observers), and per-tag error rates compound when a load contains many tags.

### Cited Findings
- Keller et al. (decision tree, RapidMiner, with boosting and feature generation; RSSI + SinceStart + antenna features + portal-specific order features). Per-tag results: **Standard portal** accuracy moved 94.66% / static 98.51% / overall 97.57% (errors 5.34% / 1.49% / 2.43%); **Satellite portal** 97.41% / 99.29% / 99.04% (errors 2.59% / 0.71% / 0.96%); **Transition portal** 89.62% / 99.52% / 98.55% (errors 10.38% / 0.48% / 1.45%). Authors note the extra reader + 4 antennas "almost doubles the hardware costs". — [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)
- Keller et al. 2010 baseline (single attribute, information-gain threshold): >95.5% overall; labelled set 53,998 pallets over 7 months at 70 doors. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Keller & Thiesse, ACM TMIS (2015, vol. 5 issue 4): logistic regression, decision trees and neural networks on low-level reader attributes for real-time process-event detection (accuracy figures not retrievable). — [Search result / ACM DOI 10.1145/2629449](https://dl.acm.org/ft_gateway.cfm?id=2629449&ftid=1505091&dwn=1&CFID=706484124&CFTOKEN=63505063)
- Alfian, Syafrudin, Yoon, Rhee (Applied Sciences 2019): statistical RSS features from tagged product movements + outlier detection before classification; abstract says outlier removal improved accuracy (numbers not retrievable, MDPI blocked). — [Alfian et al. 2019](https://www.mdpi.com/2076-3417/9/6/1154); [lab summary](https://ain.kookmin.ac.kr/updates/2019/03/19/False-Positive-RFID-Detection-Using-Classification-Models)
- Alfian et al. (Future Internet 2023): classes include tags going **into / out of the gate, moving close to the gate, turning around, and static**; features = statistics of RSS + timestamps; Isolation-Forest outlier removal + SMOTE + Random Forest = up to **94.251%** accuracy (best of models tested). — [Alfian et al. 2023](https://ideas.repec.org/a/gam/jftint/v15y2023i3p103-d1091017.html)
- SPIE 2025 gate paper: RSSI + phase fused, PCA, Bayesian-optimised MLP for **target-tag identification 98.62%**, Random Forest for **inbound/outbound 98.78%** (field tests); compares the sequence of RSSI-peak timestamps across the gate antennas (search snippet only; setup/dataset not verified). — [SPIE 13993](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/13993/1399329/Research-on-UHF-RFID-tags-identification-and-inbound-and-outbound/10.1117/12.3092709.full)
- A 2020 IEEE paper "Detecting Movement and Direction of Tags for RFID Gate" is reported in a search snippet as 98.39% with random forest — could not be verified. — [IEEE 9166196](https://ieeexplore.ieee.org/abstract/document/9166196/)
- Hauser, Zügner, Flath, Thiesse (ICIS 2015, retail EAS exit gate): predictors are not simple RSSI aggregates but individual reads put in temporal relation plus antenna information; test covered varied walking paths/speeds and tags hidden in bags; motivation: lowering antenna power to cut false alarms "sharply" reduces detection. Numbers not retrievable. — [Hauser et al. 2015](https://aisel.aisnet.org/icis2015/proceedings/DecisionAnalytics/11)
- Deep learning (Sensors 2025, shelf not gate): dual-path ResNet on unwrapped phase + RSSI + phase-derived Doppler (fixed 920.625 MHz, Impinj R420), 900 samples from 30 participants, ~94–95% behaviour recognition; authors list controlled settings and no heavy interference as limitations. — [Wang et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12431545/)
- Domain shift: lab-trained direction models fell to near chance on the shop floor without adaptation; labelled sets used: 2,400 lab samples; 2,320 (1 m) and 1,760 (2 m) shop-floor samples. — [Sensors 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13210675/)

### Inferences
- Illustrative arithmetic (not from a source): with Keller's best single-plane static-tag error of 1.49%, a pass that also hears 10 stray tags has 1 − 0.9851¹⁰ ≈ **14%** chance of at least one phantom transaction; with 40 strays ≈ 45%. With a 5.34% moved-tag error, a 12-roll load has ≈ 48% chance that at least one roll is wrongly dropped. Per-tag accuracy in the high 90s is therefore **not** sufficient for unattended per-roll posting; it needs load-level logic (Q4) and a human-review path.
- KNHOST would need its own labelled passes (rolls on stacker, its own racks and gate spacing). Keller-scale labelling (months) is unrealistic; a practical path is a few hundred scripted passes per scenario (pass-through IN/OUT, approach-and-back-off, parked load, rack background, neighbour-gate activity), mirroring the Alfian 2023 class set.
- Simpler, interpretable rules (thresholds on RSSI peak/range, relative-to-load RSSI) captured most of the gain in Keller's data (95.7% single feature vs 97.6% full tree), so a rules-first design with ML later is defensible.

### Gaps
- No public dataset or paper found for textile rolls / stackers; no paper reports results per *load* (all report per tag).
- Labelled-data volume and site-transfer behaviour for Alfian 2019/2023 and the SPIE 2025 paper could not be verified.
- No source found on Lehpamer, Ryu, Bekkali or Brusey giving portal stray-read classification accuracies (Brusey et al. 2003 is cited by Keller only as background on uncertainty reasoning).

---

## 3. Direction detection (IN vs OUT), passage-event windows, stop/reverse/abort, and cross-reads between adjacent gates

### Takeaway
Industry practice defines a passage with external triggers (motion sensor, photo-eye pair) and/or two separated read zones; RSSI/phase-only direction works in controlled tests (90–99%) but is sensitive to environment. Cross-reads between neighbouring doors are handled either physically/operationally (only one door active, power reduction, shielding) or by arbitration that compares per-gate evidence (read count, RSSI, number of antennas) inside a short time window — which requires both gates' raw reads in one place.

### Cited Findings
- Common direction methods (2010 survey): photo-eyes/electric-eye sensors (two photo-eyes give directionality), a second set of antennas further down the portal, or RSSI + angle of arrival; Impinj Octane 3.0 had a tag-direction option needing two or four antennas; Intermec ARX used RSSI + phase angle over time to compute tag speed and decide whether a tag is moving, near a reader, in a zone or in a portal. — [Borisenko & Li, uOttawa survey 2010](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- METRO portals: a motion sensor starts a ~5 s gathering-cycle; Keller's Transition portal logic expects a moved tag to be seen first by DC-facing then by truck-facing antennas; tags seen by only one side are classed static. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download); [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)
- Cross-reading prevention by scheduling: a testbed turned antennas on/off from motion-sensor state "making sure that only one dock door is active at any one time", synchronised with light stacks (Soylemezoglu et al. 2006, as summarised). — [uOttawa survey](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- Reader-to-reader arbitration (Symbol Technologies patent application, filed 2010, abandoned): each reader computes a metric per tag (read count in last N s, highest/average/most recent RSSI, number of distinct antennas that read it, earliest/latest read) and exchanges it with the peer; both run the same algorithm so only one reports (examples: 75 vs 50 reads → 75 wins; 2 antennas vs 1 → 2 wins); optional wait timer e.g. 50 ms or 500 ms; reads outside the time window are not considered cross-reads. It states power reduction "may … reduce read accuracy". — [US20120161930A1](https://patents.google.com/patent/US20120161930A1/en)
- Bertolini, Rizzi, Romagnoli, Volpi (2017): algorithm to separate unwanted cross readings from neighbouring dock-door readers plus direction detection; reliability (correct direction per tag + elimination of cross readings) ">90%" over tested pallet configurations, speeds and reader settings; aim is to avoid hard metal shields (search snippet only). — [Bertolini et al. 2017](https://iris.unimore.it/handle/11380/1188652)
- Alfian et al. 2023 includes "turning around" and "moving close to the gate" as explicit classes besides in/out/static (94.251% overall). — [Alfian et al. 2023](https://ideas.repec.org/a/gam/jftint/v15y2023i3p103-d1091017.html)
- Phase-difference-of-arrival direction-of-pass (people/objects, two antennas): 1×3 phased array max 95%; 2×2 and 1×1 configurations 100% in their test; uses a near-field antenna with a slightly tilted beam to create an asymmetric read volume (search snippet only; small trials). — [RFID-based People-object Direction of Pass Detection](https://www.researchgate.net/publication/308043199_RFID-based_People-object_Direction_of_Pass_Detection)
- Direction estimation accuracy "is sensitive to complex electromagnetic environment changing" (Wu Jie et al. 2010). — [ECNU record](https://pure.ecnu.edu.cn/en/publications/rfid-based-motion-direction-estimation-in-gate-systems/)
- Oikawa (InTech 2011) motivates direction detection without "optional expensive equipment such as several sensors". — [InTech chapter](https://www.intechopen.com/chapters/16535)
- Impinj xSpan "Direction" mode reports item direction as a tag passes along a single axis; 13 dual-polarised beams, 3 sectors; entrance/exit sectors configurable. — [Impinj xSpan datasheet](https://rfid4ustore.com/content/data_sheet/Impinj_xSpan_Datasheet.pdf); RFID Journal says it can tell whether an item is leaving vs "merely pausing near the door" (search snippet). — [RFID Journal on xSpan](https://www.rfidjournal.com/?p=71128)
- Impinj ItemSense 2018r2: threshold algorithm updated to identify the direction an item travels and the door it passed; supports an overhead offset xArray configuration at the dock door; only qualitative "more accurate" claims. — [Impinj blog](https://www.impinj.com/library/blog/impinj-releases-itemsense-2018r2-rain-rfid-so)
- Vendor claim: PervasID Flow Ranger ">99%" direction accuracy (vendor claim, search snippet). — [RFID Journal](https://www.rfidjournal.com/news/rfid-reader-detects-direction-to-enable-logistics-shrink-reduction/187352/)
- Practitioner anecdote: lowering sensitivity at neighbouring dock doors dropped read rates to ~75%; suggestions were middleware filtering and a motion sensor that triggers reads only on forward movement. — [SAP forum 2005](https://archive.sap.com/discussions/thread/53371)

### Inferences
- With antennas only in one plane, "approach then back off" and "pass through" produce similar RSSI rise-and-fall shapes on the same antennas; a robust IN/OUT decision needs a **second, independent piece of evidence along the travel axis**: a pair of photo-eyes/light-curtain beams (order A→B), a door/dock state, or a second read zone. Software can fuse these but cannot invent them.
- Passage window should be opened by the presence sensor, closed when the load clears the far beam (or a timeout), and only tags whose evidence falls inside that window are candidates; an aborted pass (beam B never broken, or B→A reversal) should cancel candidates rather than post them.
- Cross-gate arbitration (IN vs OUT gate) is implementable on the ERP/middleware side if both gates stream raw reads with synchronised timestamps: assign a tag to the gate with the stronger, more consistent evidence (more antennas, higher peak RSSI, read pattern inside that gate's passage window); if the two gates have overlapping windows and evidence is close, mark "needs review" instead of guessing. Simplest robust policy from the literature: interlock so only one gate's passage window is open at a time.

### Gaps
- No published accuracy for direction detection with exactly 3 antennas (L/R/overhead) in a single plane; the SPIE 2025 paper may use three antennas but this could not be verified.
- No quantitative results found for stop-and-go/reverse manoeuvres of forklifts/stackers inside the field.
- ItemSense threshold internals (confidence values, how cross-door assignment is computed) are not publicly documented in sources found.

---

## 4. Event/transaction state machines, read windows, deduplication, static-tag learning, and reconciliation against expected manifests

### Takeaway
Deployed systems turn raw reads into business events through trigger-bounded read windows, deduplication into enter/exit events, rule- or classifier-based per-tag filtering, and immediate operator feedback (green/yellow/red); "static-tag" handling is usually done by observing whether a tag is still present after the event (post-event check) or is seen continuously. Comparison against an expected list (WMS/ASN/picking list) is used operationally as a validation step, but no source was found that quantifies how much it reduces error.

### Cited Findings
- METRO operational loop: after each gathering-cycle the warehouseman gets a light signal — green if the pallet was recognised and the WMS confirms it belongs to this destination; yellow if it is not meant for this destination (unload and continue); red if unknown to the WMS; no light if nothing was read (repeat the pass). After the classifier, "red" is also shown when no moved pallet was detected, and a different signal when more than one tag is classified as moved. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Post-event presence check ("static-tag learning" by geometry): Satellite portals start DC-facing antennas **after** the stop trigger; a tag still seen inside the DC after the pass is treated as static (all 2,122 DC-only tags and 99.32% of DC-seen tags were static). — [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)
- Sliding-window filters ("a tag read less often than a threshold in the window is a false positive") are common but increase false negatives; a balance between readability and false-positive detection is needed. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- SMURF (Jeffery, Garofalakis, Franklin, VLDB 2006): a fixed smoothing window must be large enough to fill lost reads but small enough to capture movement; SMURF adapts the window per tag using binomial sampling / π-estimators. — [Berkeley tech report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-29.html)
- Time thresholds "to ignore intermittent appearances and disappearances" (e.g. tags that appear for only a second) reduce false positives/negatives but are "preemptive" because they reject data. — [uOttawa survey](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- Deferred (rule-based) cleansing: user-defined rewrite rules applied in order after capture, e.g. two reads of the same tag at the same location within one minute → second is a duplicate; weakness: ambiguous cases are ignored and rule order decides the result when rules conflict. — [SciTePress 2010](https://www.scitepress.org/Papers/2010/30157/30157.pdf)
- Middleware deduplication: thousands of repeated reads after the first read at a dock door are dropped and only entry/exit events are passed on. — [Atlas RFID](https://atlasrfidstore.com/rfid-insider/6-things-rfid-middleware-can-do-for-you)
- Set-membership cross-read detection (AssetPulse patent): reads grouped by time slice; "elements present in only one set or in a minimum number of sets are marked as cross read", plus a weighted score from normalised RSSI and read count. — [US8854190](https://patents.google.com/patent/US8854190)
- Stray-tag elimination by triggering (Sirit, as summarised): tags not "triggered" during the portal event are ignored. — [uOttawa survey](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- ASN/expected-list practice (non-RFID-specific): items not on the ASN should be blocked pending supervisor action (negative validation); exceptions (quantity variance, missing, unmatched) routed to supervisors instead of stopping processing. — [SG Systems glossary](https://sgsystemsglobal.com/?p=16360); [Racklify](https://racklify.com/encyclopedia/how-to-process-an-inbound-asn-in-your-wms-step-by-step/)

### Inferences
- A defensible transaction pipeline (not a published standard, synthesised from the above): **raw reads → passage window (trigger) → per-tag candidate with evidence score → load-level decision → state**: `candidate` → `confirmed` (strong evidence + on expected list + window closed cleanly) / `cancelled` (pass aborted, or tag still present after pass = static) / `needs_review` (conflicting gates, off-list tag with strong evidence, expected tag missing). Only `confirmed` posts stock movement; `needs_review` goes to an operator queue — the ERP analogue of METRO's yellow/red light.
- "Background inventory" for KNHOST: tags read repeatedly *outside* passage windows (racks near the gate, parked loads) can be put on a time-limited "known-static" list; a tag on that list needs stronger evidence (e.g. clear RSSI peak and post-pass disappearance) to become a candidate. This is the software equivalent of Keller's post-event DC-antenna check, but must expire, because a parked load will eventually move through the gate.
- Expected-list reconciliation is likely the single strongest software lever for OUT (picking list / delivery order) and IN (supplier DO/ASN), because it converts the open question "which of these 30 tags passed?" into "did the expected N rolls pass, and is anything extra?". It cannot help when the expected list itself is absent or wrong, and an unexpected-but-genuine roll must still be routable to review rather than silently dropped.

### Gaps
- No source found that quantifies the error reduction from manifest/ASN reconciliation at RFID portals.
- No published, vendor-neutral state machine specification for portal transactions (candidate/confirmed/cancelled) was found; the above is a synthesis.
- No source found on how long a "known-static" blacklist should persist or how to age it.

---

## 5. Middleware and standards that formalise this (ALE, LLRP, Impinj, Zebra, Mojix)

### Takeaway
GS1/EPCglobal ALE standardises *where* filtering and windowing happen (event cycles bounded by time/triggers, include/exclude filters, CURRENT/ADDITIONS/DELETIONS report sets, logical readers such as "DockDoor42"), but not *how* to tell a passing tag from a stray one; LLRP standardises per-read reports (antenna, RSSI, timestamps), while phase and Doppler are vendor extensions (Impinj). Vendor "direction/threshold" products (Impinj xSpan/xArray/ItemSense) package the logic but publish no independent accuracy figures.

### Cited Findings
- ALE: interface for clients to obtain "filtered, consolidated data capture information"; current version 1.1.1 (March 2009). — [GS1 ALE 1.1.1](https://gs1.org/standards/epc-rfid-epcis/epc-rfid-ale/1-1-1)
- Event cycle = interval over which data is accumulated and delivered as an ECReport; ECSpec specifies time boundaries for a series of event cycles, the readers, and filtering/reporting options; a trigger is an external event that signals the beginning or end of an event cycle; a logical reader is an abstract name for readers/antennas with one purpose, "for example, readers positioned around a door might be called DockDoor42"; a read cycle (single scan of an antenna field) "typically occurs several times a second". — [Oracle RFID Edge Server concepts](https://docs.oracle.com/cd/E13197_01/rfid/edge_server/docs21/overview/concepts.html)
- Report sets: Current (all EPCs read in the cycle), Additions (new vs previous cycle), Deletions (gone since previous cycle); reports have include/exclude filters and grouping (vendor implementation docs). — [Oracle Edge Server console docs](https://docs.oracle.com/cd/E13197_01/rfid/edge_server/docs20/console/reports.html)
- LLRP: GS1 standard (Release 2.0 ratified January 2021) providing control of air-protocol timing and access to air-protocol parameters. — [GS1 LLRP](https://ref.gs1.org/standards/llrp)
- LLRP report fields commonly parsed include AntennaID (16-bit), PeakRSSI, LastSeenTimestampUTC. — [Wireshark LLRP fields](https://www.wireshark.org/docs/dfref/l/llrp.html); [llrp-ts](https://classic.yarnpkg.com/en/package/llrp-ts)
- Impinj low-level data: RF phase and RSSI reporting via custom LLRP extensions (requires Octane ≥4.4); enabled through `ImpinjTagReportContentSelector` with `ImpinjRFPhaseAngle`, `ImpinjPeakRSSI`, `ImpinjRFDoppler`; Doppler report optimisations from Octane 4.8 (search snippet of the Impinj application note). — [Impinj Low Level Data Support app note](https://support.impinj.com/hc/en-us/article_attachments/200774268/SR_AN_IPJ_Speedway_Rev_Low_Level_Data_Support_20130911.pdf)
- Zebra FX9600 + AN510 delivered phase and RSSI time series sufficient for a direction classifier in a 2026 study (i.e. phase is not Impinj-only on current hardware). — [Sensors 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13210675/)
- Impinj ItemSense 2.0 improved threshold-crossing detection "commonly used in shipment verification"; 2018r2 adds direction and door identification. — [Impinj ItemSense 2.0 blog](https://www.impinj.com/library/blog/introducing-itemsense-20-strong-and-scalable); [ItemSense 2018r2 blog](https://www.impinj.com/library/blog/impinj-releases-itemsense-2018r2-rain-rfid-so)
- Middleware event shaping: define fields per antenna and report only tags that move from field to field. — [Lowry Solutions](https://lowrysolutions.com/?p=12891)

### Inferences
- ALE concepts map directly onto KNHOST: one logical reader per gate (GATE_IN, GATE_OUT), event cycle bounded by the presence sensor (start/stop trigger), ADDITIONS/DELETIONS to detect enter/leave, and include filters for the company EPC prefix. But ALE does not provide moved-vs-static classification, direction, or cross-gate arbitration — that must be built in the edge service/ERP.
- Requirement for procurement: readers must stream per-read data (antenna, RSSI, timestamp; preferably phase + channel index) to the edge service; "once per tag" or heavily filtered reader modes would block most methods in Q1–Q3.

### Gaps
- Exact ALE 1.1.1 boundary semantics (e.g. `stableSetInterval`, `whenDataAvailable`) could not be read from the GS1 PDF (403); not verified here.
- No technical documentation found for Zebra or Mojix portal direction/stray-tag logic, nor for SML or Avery Dennison dock-door notes.
- Independent accuracy evaluations of Impinj xSpan/xArray direction or ItemSense thresholds were not found (only vendor statements; an RFID Journal snippet suggested an early direction algorithm worked for up to ~10 tags — unverified).

---

## 6. Fundamental limits: what software cannot fix

### Takeaway
Software can re-classify and arbitrate reads it receives, but it cannot (a) create reads for tags that were never read, (b) separate a stray read whose RSSI/time/antenna signature overlaps a genuine pass, or (c) use features the reader does not report. Power/sensitivity reduction trades stray reads for missed reads, and models tuned in one geometry do not transfer.

### Cited Findings
- Missed reads: METRO's process explicitly handles "no tags recognised" by asking the operator to repeat the pass — the software has nothing to classify. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Overlapping signatures: real gathering-cycles included a moved pallet with near-constant RSSI over 3 s and a static pallet with a moved-like RSSI bump; even the best production classifier left 2.43% (standard portal) / 0.96% (satellite) per-tag error. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download); [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)
- Read-accuracy vs cross-read trade-off: configurations that raise read accuracy also extend range, which worsens cross-reading between portals. — [uOttawa survey](https://www.site.uottawa.ca/~mbolic/RFIDBook/Open_access/portal.pdf)
- Power reduction "may … reduce read accuracy" and there may be no single power level suitable for all tag types. — [US20120161930A1](https://patents.google.com/patent/US20120161930A1/en); anecdote of read rate falling to ~75% after reducing sensitivity. — [SAP forum](https://archive.sap.com/discussions/thread/53371)
- Retail EAS: lowering antenna power to reduce false positives sharply reduces detection rates. — [Hauser et al. 2015](https://aisel.aisnet.org/icis2015/proceedings/DecisionAnalytics/11)
- Filtering raises false negatives: sliding-window thresholding removes individual weak tags and so increases missed reads. — [Keller et al. 2010](https://www.alexandria.unisg.ch/bitstreams/a14e6030-53e3-4bc4-b7b9-59fcec18a5de/download)
- Reader-feature dependency: phase/Doppler are vendor extensions; Doppler on commercial readers is "not precise enough for the majority of applications" and slow movement of weakly-read tags (e.g. <1.1 m/s at −95.8 dBm) is undetectable by Doppler. — [arXiv 2505.21812](https://arxiv.org/html/2505.21812v1); [CrossMgrImpinj](https://www.sites.google.com/site/crossmgrsoftware/project-updates/crossmgrimpinj22111greatlyimprovedrfidaccuracy)
- Transfer limits: lab-trained direction models degraded to near chance on a shop floor and to ~50% when distance changed from 1 m to 2 m. — [Sensors 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13210675/)
- More antennas hear more strays: stray share among read tags rose from 75.47% (standard) to 86.66% (satellite) and 90.19% (transition) at the same DC. — [Keller et al., portal setups](https://cocoa.ethz.ch/downloads/2013/05/08/dec.pdf)

### Inferences
- Clear division of labour for the report: **physical design** must deliver (i) near-complete reads of the rolls that pass (overhead + side coverage for 6-high stacks), (ii) attenuation of the rack zone and the neighbouring gate, and (iii) an independent passage/direction signal (photo-eyes or a second zone). **Software** then delivers (iv) windowing, deduplication, per-tag moved/static scoring, cross-gate arbitration, static-tag lists, and (v) reconciliation against DO/picking lists with a `needs_review` path. Software cannot compensate for missing (i) and can only partially compensate for missing (ii)/(iii).
- Because per-tag errors compound over many rolls per load, the realistic target for software is "no silent wrong posting" (every doubtful case lands in review), not "100% automatic".
- Before committing to ML or phase-based methods, confirm the chosen reader streams per-read RSSI, antenna, timestamp and (if wanted) phase/channel to the edge; otherwise only RSSI-threshold + window + manifest logic is available.

### Gaps
- No quantitative published read-rate data found for tags on fabric-roll ends in 6-high stacks.
- Buettner & Wetherall (MobiCom 2008) is the standard empirical UHF reliability study, but its specific findings could not be retrieved in this session. — [BibSonomy record](https://www.bibsonomy.org/bibtex/432961db98aea30034a30e545b73e942)
