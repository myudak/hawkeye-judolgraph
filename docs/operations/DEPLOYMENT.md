# Deployment dan Akses Mesin Lain

For the double-click Windows installer and portable ZIP, see
[WINDOWS_DISTRIBUTION.md](WINDOWS_DISTRIBUTION.md). That distribution remains loopback-only and
stores mutable state under `%LOCALAPPDATA%\HAWK-EYE`; it is separate from the Docker/server path
documented below.

## Boundary saat ini

HAWK-EYE adalah aplikasi single-investigator. Ia memiliki access gate HTTP Basic opsional dan satu
exact-Origin guard opsional untuk demo, tetapi tidak memiliki akun/role, tenant isolation, rate
limit, atau TLS termination. Deployment yang didukung tetap satu service di mesin yang dipercaya
dengan port host terikat ke `127.0.0.1`.

## Docker di server

```powershell
git clone <repository-url> hawkeye
Set-Location hawkeye
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Data default berada di `./data`. Lokasi lain dapat dipilih dari `.env`:

```dotenv
HAWKEYE_DATA_PATH=D:/hawkeye-data
HAWKEYE_PORT=8760
```

Pada Linux, gunakan absolute path yang dapat ditulis user non-root container.

## Akses dari workstation

Pertahankan aplikasi di loopback server dan buat SSH tunnel:

```powershell
ssh -N -L 8760:127.0.0.1:8760 investigator@server
```

Browser workstation kemudian membuka `http://127.0.0.1:8760`. SSH menyediakan autentikasi dan
enkripsi transport tanpa mengubah threat boundary aplikasi. Tailscale atau WireGuard dapat menjadi
transport menuju SSH server.

## Upgrade

```powershell
docker compose down
Copy-Item -Recurse data data-backup-YYYYMMDD
git pull --ff-only
docker compose build --pull
docker compose up -d
```

Jangan menghapus `data/` atau menjalankan `docker compose down -v` sebagai langkah upgrade. Bind
mount adalah canonical local state untuk cases, workspace SQLite, comparisons, dan artifacts.

## Health dan diagnosis

```powershell
docker compose ps
docker compose logs --tail 200 hawkeye
Invoke-RestMethod http://127.0.0.1:8760/health
```

Acceptance penuh sebelum pemindahan mesin:

```powershell
pnpm verify:docker
```

Script menggunakan project Compose dan data directory sementara, lalu membersihkan container test.
Ia tidak menyentuh `./data` produksi.

## Egress VPN hanya untuk HAWK-EYE

Gunakan overlay ini bila investigator perlu satu lokasi egress yang dicatat secara eksplisit tanpa
mengubah default route host. SSH, Git, Docker, dan `cloudflared` tetap keluar melalui IP VPS;
request HTTP, Chromium, dan provider LLM dari container HAWK-EYE keluar melalui OpenVPN.

Prasyarat Linux:

```bash
test -c /dev/net/tun
```

Simpan file sumber `.ovpn` di mesin operator dan siapkan salinan runtime yang telah divalidasi:

```bash
uv run python tools/deployment/prepare_openvpn_config.py \
  ca-free-15.protonvpn.udp.ovpn \
  data/vpn/ca-free-15.protonvpn.udp.ovpn
```

Masukkan credential OpenVPN khusus Proton—bukan password akun—ke `.env` dengan permission `0600`:

```dotenv
PROTON_OPENVPN_USER=isi-di-mesin-deployment
PROTON_OPENVPN_PASSWORD=isi-di-mesin-deployment
PROTON_OPENVPN_CONFIG_PATH=./data/vpn/ca-free-15.protonvpn.udp.ovpn
PROTON_OPENVPN_PORT=51820
GLUETUN_LOG_LEVEL=warning
```

Validasi dan start:

```bash
docker compose -f compose.yaml -f compose.vpn.yaml config --quiet
docker compose -f compose.yaml -f compose.vpn.yaml up -d --build
docker compose -f compose.yaml -f compose.vpn.yaml ps
docker compose -f compose.yaml -f compose.vpn.yaml logs --tail 100 gluetun
```

Port aplikasi dipublikasikan oleh Gluetun tetapi tetap hanya pada host loopback. HAWK-EYE tidak
mendapat `NET_ADMIN`; ia hanya berbagi network namespace sidecar. Seluruh egress monolithic service,
termasuk request ke OpenRouter, melewati VPN dan tetap dilindungi TLS aplikasi.

Verifikasi host dan container memakai IP berbeda:

```bash
curl -4 https://api.ipify.org
docker compose -f compose.yaml -f compose.vpn.yaml exec -T hawkeye \
  python -c "import urllib.request; print(urllib.request.urlopen('https://api.ipify.org').read().decode())"
```

Jangan menilai keberhasilan VPN dari satu situs live. Geo-restriction tetap dapat berlaku walaupun
tunnel sehat. Capture restriction page apa adanya dan pertahankan fixture terkendali sebagai test
truth. VPN tidak boleh dipakai untuk login, CAPTCHA, bypass restriction, atau automatic candidate
crawl.

### Rotasi dan rollback

Setelah mengganti credential atau config, recreate kedua service:

```bash
docker compose -f compose.yaml -f compose.vpn.yaml up -d --force-recreate
```

Rollback ke egress VPS langsung tanpa menghapus data:

```bash
docker compose -f compose.yaml -f compose.vpn.yaml down
docker compose -f compose.yaml up -d
```

Jangan memakai `down -v`; evidence tetap berada pada bind mount `data/`.

## Exception demo sementara

Owner mengizinkan satu demo sementara melalui Cloudflare Tunnel. Siapkan `.env` tanpa mengubah atau
mem-publish key:

```dotenv
OPENROUTER_APIKEY=isi-di-mesin-demo
OPENROUTER_MODEL=openai/gpt-5.6-luna
HAWKEYE_PUBLIC_DEMO_ORIGIN=https://hawkeye.example.com

# Opsional. Hapus keduanya untuk demo tanpa login.
HAWKEYE_AUTH_USERNAME=
HAWKEYE_AUTH_PASSWORD=
```

Start aplikasi:

```powershell
docker compose -f compose.yaml -f compose.openrouter.yaml up -d --build
```

Di Cloudflare dashboard, buat remotely-managed Tunnel dengan published application:

```text
Public hostname: hawkeye.example.com
Service:         http://127.0.0.1:8760
```

Jalankan connector `cloudflared` di host sesuai command/token yang diberikan dashboard. Tunnel harus
berjalan di host, bukan mengubah publish address Compose. Jangan commit tunnel token atau credential
JSON. Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8760/health
Invoke-WebRequest https://hawkeye.example.com/health
```

Ketika origin demo dikonfigurasi, mutation publik hanya menerima satu header
`Origin: https://hawkeye.example.com`; missing, `null`, HTTP, alternate port, subdomain, wildcard,
duplicate, dan attacker origin ditolak. Local browser `127.0.0.1`/`localhost` tetap dapat melakukan
mutation dengan same-origin header. Forwarded headers tidak dipercaya dan CORS tidak diaktifkan.

Cloudflare Tunnel membuat koneksi outbound dari host dan mem-proxy HTTPS publik ke service HTTP
loopback. Tanpa Basic Auth atau Cloudflare Access, siapa pun tetap dapat membaca UI/API dan direct
client dapat memalsukan header Origin. Hentikan tunnel dan kosongkan `HAWKEYE_PUBLIC_DEMO_ORIGIN`
setelah demo selesai.

## Public production tidak termasuk

Exception demo di atas tidak mengubah boundary produk. Router port-forward langsung, bind
`0.0.0.0` pada host, dan public production reverse proxy belum didukung.
Milestone public deployment harus menambahkan dan menguji setidaknya:

- authentication dan authorization;
- HTTPS serta secure proxy-header policy;
- CSRF/session design;
- rate limit dan request/body budgets pada edge;
- storage isolation, encryption, backup, dan retention;
- audit log operator dan incident response;
- threat model untuk malicious collected content dan multi-user access.
