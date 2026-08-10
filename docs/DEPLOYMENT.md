# Deployment dan Akses Mesin Lain

## Boundary saat ini

HAWK-EYE adalah aplikasi single-investigator. Ia belum memiliki authentication, authorization,
tenant isolation, CSRF boundary untuk public origin, atau TLS termination. Deployment yang didukung
adalah satu service di mesin yang dipercaya dengan port host terikat ke `127.0.0.1`.

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

## Public internet tidak termasuk

Router port-forward langsung, bind `0.0.0.0` pada host, dan public reverse proxy belum didukung.
Milestone public deployment harus menambahkan dan menguji setidaknya:

- authentication dan authorization;
- HTTPS serta secure proxy-header policy;
- CSRF/session design;
- rate limit dan request/body budgets pada edge;
- storage isolation, encryption, backup, dan retention;
- audit log operator dan incident response;
- threat model untuk malicious collected content dan multi-user access.
