// ABOUTME: Downloads the latest bluetti APK by extracting the URL from the download page's JavaScript, mimicking browser behavior.
// ABOUTME: Stores each version in its own subdirectory under bluetti-files/. Idempotent — skips if that version is already downloaded.

import { mkdir, readdir, access, open } from "node:fs/promises";
import { Readable, Writable } from "node:stream";

const BASE_URL = "https://download.bluetti.app";
const FILES_DIR = "bluetti-files";

function versionDir(filename) {
  return `${FILES_DIR}/${filename}`;
}

function apkPath(filename) {
  return `${versionDir(filename)}/bluetti.apk`;
}

async function main() {
  // 1. Fetch env.js to get serverGatewayGlobal
  const envJs = await fetch(`${BASE_URL}/webjars/global/env.js`).then((r) =>
    r.text(),
  );
  const gatewayMatch = envJs.match(
    /serverGatewayGlobal:\s*"([^"]+)"/,
  );
  if (!gatewayMatch) throw new Error("Could not extract serverGatewayGlobal from env.js");
  const serverGateway = gatewayMatch[1];

  // 2. Fetch download.js to get the apiUrl
  const downloadJs = await fetch(
    `${BASE_URL}/webjars/download/bluetti/assets/download.js`,
  ).then((r) => r.text());
  const apiUrlMatch = downloadJs.match(
    /apiUrl\s*=\s*"([^"]+)"/,
  );
  if (!apiUrlMatch) throw new Error("Could not extract apiUrl from download.js");
  const apiUrl = apiUrlMatch[1];

  const downloadUrl = `${serverGateway}${apiUrl}`;

  // 3. HEAD request to get server-side filename (encodes version)
  const headResp = await fetch(downloadUrl, { method: "HEAD" });
  if (!headResp.ok) throw new Error(`HEAD request failed: ${headResp.status}`);
  const disposition = headResp.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";\s]+)"?/);
  const serverFilename = filenameMatch ? filenameMatch[1] : "unknown";

  // 4. Check if this version is already downloaded
  const dest = apkPath(serverFilename);
  const alreadyDownloaded = await access(dest)
    .then(() => true)
    .catch(() => false);

  if (alreadyDownloaded) {
    console.log(`Already downloaded: ${serverFilename}`);

    const existing = await listVersions();
    const others = existing.filter((v) => v !== serverFilename);
    if (others.length > 0) {
      console.log(`Other downloaded versions: ${others.join(", ")}`);
    }
    return;
  }

  // 5. Download the APK into its versioned directory
  const dir = versionDir(serverFilename);
  await mkdir(dir, { recursive: true });

  console.log(`Downloading ${serverFilename} from ${downloadUrl}...`);
  const resp = await fetch(downloadUrl);
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);

  const total = parseInt(resp.headers.get("content-length") || "0", 10);
  let downloaded = 0;

  const fh = await open(dest, "w");
  const writeStream = fh.createWriteStream();

  const progressStream = new Writable({
    write(chunk, _encoding, callback) {
      downloaded += chunk.length;
      if (total) {
        const pct = ((downloaded / total) * 100).toFixed(1);
        process.stdout.write(`\r  ${pct}% (${(downloaded / 1024 / 1024).toFixed(1)} MB)`);
      }
      writeStream.write(chunk, callback);
    },
    final(callback) {
      writeStream.end(callback);
    },
  });

  const nodeReadable = Readable.fromWeb(resp.body);
  await new Promise((resolve, reject) => {
    nodeReadable.pipe(progressStream).on("finish", resolve).on("error", reject);
  });

  const allVersions = await listVersions();
  console.log("\nDone.");
  console.log(`Downloaded versions: ${allVersions.join(", ")}`);
}

async function listVersions() {
  try {
    const entries = await readdir(FILES_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
