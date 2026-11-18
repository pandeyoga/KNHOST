# Kontainer uji jalan Playwright (Node) — dipakai bila mesin tidak punya Node.js (mis. Windows + Docker Desktop).
# Browser & pustaka sistem dari image resmi Playwright (Ubuntu noble, chromium-1148 = Playwright 1.49.x), Node 22 resmi
# (nodejs.org), paket npm: playwright 1.49.1 + mongosh 2.3.8 (cek buku lewat KN_MONGO_URL, tanpa docker CLI).
#
#   docker build -t kn-uji-pw:1 docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/docker
ARG BASE=mcr.microsoft.com/playwright/python:v1.49.1-noble
FROM ${BASE}
ARG NODE_VER=v22.12.0
RUN python3 -c "import urllib.request as u; u.urlretrieve('https://nodejs.org/dist/${NODE_VER}/node-${NODE_VER}-linux-x64.tar.gz', '/tmp/node.tgz')" \
 && mkdir -p /opt/node && tar -xzf /tmp/node.tgz -C /opt/node --strip-components=1 && rm /tmp/node.tgz \
 && ln -sf /opt/node/bin/node /usr/local/bin/node && ln -sf /opt/node/bin/npm /usr/local/bin/npm && ln -sf /opt/node/bin/npx /usr/local/bin/npx
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 NODE_PATH=/opt/pw/node_modules
WORKDIR /opt/pw
RUN npm init -y >/dev/null && npm install --no-audit --no-fund playwright@1.49.1 mongosh@2.3.8 \
 && ln -sf /opt/pw/node_modules/.bin/mongosh /usr/local/bin/mongosh
WORKDIR /work
