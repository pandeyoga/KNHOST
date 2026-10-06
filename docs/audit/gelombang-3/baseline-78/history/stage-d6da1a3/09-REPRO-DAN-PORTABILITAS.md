# Menjalankan ulang bukti secara lokal

Bukti JSON/log mencerminkan commit yangdiaudit. Untuk validasi patch, salin folderrepro ke workingdirectory sementara agar hasilaudit historis tidakditimpa. RecordactualHEADbaru pada hasilrerun, bukan hanya SHAyangtertulis dalamscript historis.

Python3.12 + dependencybackend diperlukan, termasukmotor/pymongo/fastapi/httpx/coverage; frontend numericprobes memerlukanNode dan Babelparser yangtersedia melalui frontendnode_modules. Mongo test berdiri sendiri di127.0.0.1:27919, tanpa dataoperasional. Wrapperportable `repro/run_local.py` meminta pathrepo eksplisit dan mencatat actualHEAD. Jangan menjalankanseed/cleanup terhadapdatabase produksi.

Contoh, dariworkingcopyrepro:

```text
python run_local.py --repo C:/path/KNHOST --script data_lineage_probes.py
python run_local.py --repo C:/path/KNHOST --script extended_numeric_probes.py
python run_local.py --repo C:/path/KNHOST --script previous_failures.py
python run_local.py --repo C:/path/KNHOST --script additional_metric_probes.py
```

Setiapwave2_env membuat databaseUUID kosong. ServerASGI dijalankan inprocess; tidakmenggunakancredentials produksi. Test HTTPfullsuite danagentreplay memerlukanseeder/APIserver terpisah serta path/envadaptasi yangdidokumentasikan; bukan semua skrip siapdijalankan dengan commandcontohdiatas.

Faultinject berada padaclientMongo lokal dan dipulihkan difinally. Kontrolclearinglock padaV3-PROD-01 merupakan testrecovery, bukan ujiotorisasi. Hardware/browser belumdijalankan. Hasiluji yangsudahvalid tidakboleh dianggaptestotomatisPASS: banyakcounterexample sengajamencatatobserveddifference; agentharusmengassert expecteduntukacceptance setelahpatch.
