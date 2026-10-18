from pathlib import Path
from collections import Counter
import json

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'BACKLOG.json').read_text(encoding='utf-8'))
def clean(s): return str(s).replace('|','/').replace('\n',' ')
def save(name,body): (ROOT/name).write_text(body.rstrip()+'\n',encoding='utf-8')
phases={p['id']:p for p in data['phases']}
reqs={r['id']:r for r in data['requirements']}
checks={c['id']:c for c in data['acceptance']}
counts=Counter(r['status'] for r in reqs.values())
passed=sum(c['status']=='pass' for c in checks.values())
validated=sum(r['status']=='validated' for r in reqs.values())

text=f'''# Tracker gelombang lanjutan pasca-P05

Dihasilkan dari BACKLOG.json. Ubah status pada BACKLOG, lalu render ulang; jangan mengedit angka manual.

Baseline: `{data['baseline_commit']}`. Kandidat final: `{data.get('target_commit') or 'belum ditetapkan'}`.

Requirement tervalidasi: **{validated}/{len(reqs)}**. Acceptance PASS: **{passed}/{len(checks)}**. Keputusan pending: **{sum(d['status']=='pending' for d in data['decisions'])}/{len(data['decisions'])}**.

Angka di atas adalah kemajuan implementasi/verifikasi gelombang ini. Pemetaan seluruh sumber tidak berarti code coverage 100 persen. Status awal not_started adalah sengaja, karena paket belum mengimplementasikan perubahan.

| Fase | Status | Requirement tervalidasi | Acceptance PASS | Pending terkait | Prompt |
|---|---|---|---|---|---|
'''
for p in phases.values():
    prs=[r for r in reqs.values() if r['phase']==p['id']]
    pcs=[c for c in checks.values() if c['phase']==p['id']]
    pending=sorted({did for r in prs for did in r['pending_decisions'] if next(d for d in data['decisions'] if d['id']==did)['status']=='pending'})
    text+=f"| {p['id']} {clean(p['title'])} | {p['status']} | {sum(r['status']=='validated' for r in prs)}/{len(prs)} | {sum(c['status']=='pass' for c in pcs)}/{len(pcs)} | {', '.join(pending) or '—'} | [Buka](phases/{p['id']}.md) |\n"
text+='\n## Requirement\n\n| ID | Fase | Kebutuhan | Status | Bukti |\n|---|---|---|---|---|\n'
for r in reqs.values():
    text+=f"| {r['id']} | {r['phase']} | {clean(r['title'])} | {r['status']} | {', '.join(r['evidence']) or 'belum ada'} |\n"
save('TRACKER.md',text)

text='''# Acceptance matrix

Setiap skenario required sampai ada perubahan lingkup yang disetujui owner. Not_run/blocked/fail tidak masuk PASS. File ini dihasilkan dari BACKLOG.json.

Acceptance berawalan MW adalah skenario integrasi perangkat dari spesifikasi middleware, bukan instruksi membangun APK. Detail aslinya ada pada sources/middleware/uat/UAT_SCENARIOS.md dan field source_scenario pada BACKLOG.
'''
for p in phases.values():
    text+=f"\n## {p['id']} — {p['title']}\n\n| ID | Requirement | Skenario dan hasil yang harus terbukti | Status | Perangkat nyata |\n|---|---|---|---|---|\n"
    for c in checks.values():
        if c['phase']!=p['id']: continue
        scenario=c['scenario']
        if c.get('source_scenario'): scenario+=' Detail: '+c['source_scenario']
        text+=f"| {c['id']} | {c['requirement']} | {clean(scenario)} | {c['status']} | {'wajib' if c.get('requires_hardware') else 'sesuai dampak'} |\n"
save('ACCEPTANCE_MATRIX.md',text)

text='''# Register keputusan dan kebutuhan pending

Keputusan yang belum dijawab tetap dicatat. Jangan mengisi jawaban atas nama owner/client. Semua item di sini pending pada awal paket, dengan jenis yang berbeda: kebijakan client, data, review desain, operasional, hardware, HR atau validasi owner. Tidak semuanya pertanyaan client baru.

Teks pertanyaan client lengkap dengan konteks tersedia pada [dokumen pertanyaan client](sources/09_Pertanyaan_Client_Retur_dan_Pendukung.md). Pertanyaan belum dikirim. Untuk menjawab, gunakan templates/DECISION_RECORD.md lalu isi answer, answer_ref, confirmed_by dan status resolved di BACKLOG.

Usulan desain dapat dikembangkan sebagai prototype untuk direview; belum menjadi kebijakan bisnis. Pending hanya memblok hasil akhir requirement terkait, tidak semua pekerjaan. Keputusan yang sudah jelas tidak ditanyakan ulang.
'''
for d in data['decisions']:
    text+=f"\n## {d['id']} — {d['title']}\n\nJenis: {d['type']}. Status: **{d['status']}**. Requirement: {', '.join(d['affected_requirements'])}.\n\n{d['context']}\n\n"
    for q in d['questions']: text+='- '+q+'\n'
    text+='\nDampak: '+d['blocks']+'\n'
    if d.get('answer'): text+='\nJawaban tercatat: '+d['answer']+'\n'
save('DECISIONS_PENDING.md',text)

groups=Counter(s['source'] for s in data['source_map'])
text='''# Cakupan dan pemetaan sumber

Semua ID sumber yang tercantum dipetakan ke requirement aktif. Ini ukuran traceability kebutuhan, bukan ukuran line/function/branch code coverage atau jaminan semua bug ditemukan.

Register historis dipertahankan untuk konteks; keputusan owner terbaru menang. Daftar acceptance lama tidak disalin sebagai PASS. L00 wajib menentukan apakah skenario lama dipakai ulang, diuji ulang, diganti oleh keputusan baru atau masih pending, dengan alasan per ID.

| Kelompok sumber | Jumlah ID terpetakan |
|---|---|
'''
for group,n in groups.items(): text+=f'| {group} | {n} |\n'
for group in groups:
    text+=f'\n## {group}\n\n| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |\n|---|---|---|---|\n'
    for s in data['source_map']:
        if s['source']==group: text+=f"| {s['id']} | {clean(s['title'])} | {', '.join(s['requirements'])} | {clean(s['note'])} |\n"
text+='''

## Batas dan catatan penting

- 126 statement mencakup konteks meeting, WMS, fingerprint dan middleware yang telah dirapikan sebelumnya. Statement yang dipetakan boleh menjadi reuse/validasi, tidak harus fitur baru.
- Sisa P06–P10 dan koreksi P01–P05 ditangani menurut BASELINE_DAN_PLAN_LAMA. Status implementasi lama tidak otomatis menjadi status gelombang baru.
- Kontrak middleware dan skenario perangkat dibawa sebagai referensi parity ERP dan UAT. Pembangunan adapter/APK merupakan workstream terpisah.
- Audit wave 1–3 tetap memiliki tracker tersendiri. Review seluruh kode repo tidak diklaim selesai oleh dokumen ini.
- Bukti analisis terdahulu terbatas pada snapshot dan fungsi yang diperiksa; bukan hasil uji rilis baru.
'''
save('COVERAGE.md',text)
print(json.dumps({'rendered':['TRACKER.md','ACCEPTANCE_MATRIX.md','DECISIONS_PENDING.md','COVERAGE.md'],'requirements':len(reqs),'acceptance':len(checks),'source_map':len(data['source_map'])}))
