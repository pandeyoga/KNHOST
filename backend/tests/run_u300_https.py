"""Run actual Java Api/Config/DecisionPolicy against ERP V2 over local TLS."""
import asyncio
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI

from run_rfid_v2_integration import seed, client, router


async def run():
    agent, java, jar, dest = map(Path, sys.argv[1:5])
    dest = dest / uuid4().hex
    dest.mkdir(parents=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False).sign(key, hashes.SHA256()))
    cert, pem = dest/'localhost.crt', dest/'localhost.key'
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    src = agent/'app/src/main/java/id/kubusteknologi/kn/u300'
    # Agent 0.5: Api/Config bergantung ke kelas inti lain (ClockSync, GatePipeline, PassageMachine, …) → kompilasi
    # seluruh core/ seperti test-host.ps1.
    sources = (sorted((src/'core').glob('*.java')) + [src/(n+'.java') for n in ('Json', 'Api', 'Config', 'DecisionPolicy', 'Telemetry')]
               + [agent/'tests/ErpIntegrationTest.java'])
    compiler = await asyncio.create_subprocess_exec(str(java/'bin/javac.exe'), '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(dest), *map(str, sources))
    assert await compiler.wait() == 0, 'Java compilation failed'
    _, _, epcs, token = await seed(1)
    app = FastAPI(); app.include_router(router)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0, ssl_keyfile=str(pem), ssl_certfile=str(cert), log_level='warning'))
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started: break
            if task.done(): await task
            await asyncio.sleep(0.05)
        assert server.started, 'local TLS server failed to start'
        port = server.servers[0].sockets[0].getsockname()[1]
        env = dict(os.environ, KN_TEST_DEVICE_KEY=token)
        test = await asyncio.create_subprocess_exec(str(java/'bin/java.exe'), '-cp', str(dest)+os.pathsep+str(jar),
            'id.kubusteknologi.kn.u300.ErpIntegrationTest', f'https://localhost:{port}', str(cert), epcs[0], env=env)
        assert await test.wait() == 0, 'Java/ERP integration failed'
    finally:
        server.should_exit = True
        await task
        client.close()


if __name__ == '__main__':
    asyncio.run(run())
