# Remote Asset / CDN Extraction Guide

`unity-assets.sh` extracts what ships **inside** the APK. Live-service games
(Addressables + LiveOps) deliver a large share of real content — event UI, story
art, themed backgrounds, extra audio, sometimes whole level packs — **from a CDN
at runtime**. That content is not in the package. This guide captures how to find
it, get the URL, and pull it. Generic; engine detail is Unity-Addressables but the
shape (local catalog + remote base + auth-gated game API) recurs across engines.

## 1. Detect that remote content exists

Unity/Addressables signals under `assets/aa/` (or `assets/bin/Data` for the
catalog):
- `catalog.bin` (or `catalog.json`) + `catalog.hash` + `settings.json`.
- `settings.json` → `m_buildTarget` (platform), `m_AddressablesVersion`,
  `m_DisableCatalogUpdateOnStart`, and profile variables. A **RemoteLoadPath**
  profile var (vs only LocalLoadPath) means remote content.
- In the IL2CPP dump: a `*PathHelper.RemoteLoadPath` getter, a `CDNAssetService`
  / `RemoteLevels` / `EnsureDownloadedAsync` type.
- In `assets/aa/<platform>/`: bundles named `*_local_assets_all.bundle` are the
  **local** half; the catalog referencing bundles that are NOT shipped there is
  the remote half.

If none of these exist, all content is in the APK — skip this guide.

## 2. Local vs remote — classify before chasing anything

A bundle appearing in `catalog.bin` does **not** mean it's on the CDN. Each
catalog entry's InternalId resolves to either `{RuntimePath}/<platform>` (LOCAL,
already in the APK — `unity-assets.sh` got it) or `{RemoteLoadPath}` (CDN-only).

Cheap classifier: list `assets/aa/<platform>/*.bundle` (local set). For every
catalog bundle, strip the `_<32hex>` hash → short name. If the short name is in
the local set (or the name contains `_local_`), it's **local — do not chase it on
the CDN, it will 404.** Only the remainder is CDN-only. Getting this wrong is the
main time-sink (chasing local bundles + brute-forcing wrong URLs).

Also re-check the "wanted" list you were handed: names like `_assets_all_<hash>`
are often **localization string-tables shipped locally**, mis-labeled as remote.

## 3. The CDN URL

Shape (Addressables): `<RemoteLoadPath>/<full provider path>.bundle[?hash=<hash>]`
- `RemoteLoadPath` = a `String.Format` template, a **string literal in
  `global-metadata.dat`** like `https://cdn.host/app/v1/{0}/{1}/{2}`, filled at
  runtime by env / platform / version. Platform is a literal ("Android"); **env
  and version are usually runtime config fields (e.g. a `BuildParameters`
  singleton), NOT in any serialized asset and NOT plain code literals** — so you
  cannot read them statically. Don't burn hours brute-forcing (host is often
  BunnyCDN/CloudFront; every wrong combo is a clean 404).
- The on-CDN path is the **full Addressables provider path**
  (`groupname_assets_assets/modules/.../name.prefab.bundle`), **not** the flat
  `name_<hash>.bundle`. `?hash=` is usually optional. Full provider paths live in
  `catalog.bin` (fragmented across shared strings) or come free from capture (§4).

## 4. Getting env/version — ordered by reliability

1. **System HTTP proxy + user CA (mitmproxy) — this is the one that works.**
   Set the device Wi-Fi **HTTP proxy** to `<your-host>:8080`, run
   `mitmdump -s addon.py --listen-host 0.0.0.0 --listen-port 8080`, install the
   mitmproxy CA as a **user** certificate. Unity's `UnityWebRequest` **honors the
   Android system HTTP proxy** and will trust the user CA → mitmproxy decrypts the
   real CDN GETs. The captured URL hands you env, version, and the exact provider
   path. A minimal addon logs `flow.request.pretty_url` and saves 200 bodies.
2. **frida (rooted device/emulator):** hook the `get_RemoteLoadPath` RVA (from the
   IL2CPP dump) and log its return — the fully resolved base URL in one shot.
3. **Cache scrape — no proxy, no root, no URL needed (great fallback):** Unity
   writes every downloaded bundle to
   `/sdcard/Android/data/<pkg>/files/UnityCache/Shared/<name>/<hash>/__data`
   (raw `UnityFS`, readable by plain `adb pull`). Play the game to trigger the
   content, pull, and rename `__data` by the `<hash>` folder. Slow (you must reach
   each piece of content; much is level/event-gated) but needs zero tooling.

**What does NOT work:** a transparent VPN capture (PCAPdroid) for the *asset* CDN
— Unity's bundled BoringSSL ignores the Android user-CA store, so you get only
`CONNECT host:443` + TLS SNI, never a decrypted GET. A **system proxy** is
different and does work (§4.1). Don't confuse the two.

## 5. Download

Once you have the base + one real provider path, it's plain `curl` (bundle
endpoints are usually unauthenticated):
```
curl -s -o out.bundle "https://cdn.host/app/v1/<env>/<platform>/<ver>/<provider/path>.bundle"
head -c7 out.bundle   # MUST be "UnityFS"; if it's HTML you have the wrong path
```
Reconstruct the other provider paths from `catalog.bin` string fragments (per
group the pattern is consistent) and HEAD-test each. Decode the downloaded
bundles with UnityPy the same way `unity-assets.sh` handles local ones. Save
CDN-only output separately (e.g. `extracted/cdn-bundles/`) from APK-extracted
content, and record the resolved base URL + a working `download_all.sh`.

## 6. Levels / gameplay data ≠ asset CDN

Level definitions and other gameplay data frequently do **not** come from the
asset CDN — they arrive over a **game backend API** (SignalR / gRPC / MessagePack
over WebSocket, gated by a Firebase/JWT token and custom headers). Those 404 on
the asset CDN. Treat them as backend (see `backend-recon-guide.md`): recover the
host/contract from the IL2CPP/Java surface; obtaining the actual data needs an
authenticated in-app capture or authed replay, not a bare curl.

## Report

In `re-digest.md` (or a `remote-assets.md`), state: the CDN base URL and how it
was resolved; counts of CDN-only vs local bundles; which "wanted" items were
actually local; and whether levels/data come from a separate authed API. **Do not
claim CDN content was extracted when only the local half was** — that gap is the
whole point of this pass.
