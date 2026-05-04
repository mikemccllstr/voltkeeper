// ABOUTME: Downloads the latest bluetti APK by extracting the URL from the download page's JavaScript, mimicking browser behavior.
// ABOUTME: Idempotent — skips download if APK exists; warns if a newer version is available on the server.

import { mkdir, writeFile, readFile, access, open } from "node:fs/promises";
import { Readable, Writable } from "node:stream";

const BASE_URL = "https://download.bluetti.app";
const APK_PATH = "bluetti-files/bluetti.apk";
const VERSION_PATH = "bluetti-files/.apk-version";

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

  // 4. Check if we already have the APK
  const apkExists = await access(APK_PATH)
    .then(() => true)
    .catch(() => false);

  if (apkExists) {
    let savedVersion = "";
    try {
      savedVersion = (await readFile(VERSION_PATH, "utf-8")).trim();
    } catch {
      // no version file — assume old
    }

    if (savedVersion === serverFilename) {
      console.log(`APK is up to date (${serverFilename})`);
      return;
    }
    console.log(
      `WARNING: A newer APK is available on the server (${serverFilename}).`,
    );
    console.log(`You have: ${savedVersion || "unknown version"}`);
    console.log("Run 'mise run cleanup' then 'mise run download-apk' to update.");
    return;
  }

  // 5. Download the APK
  await mkdir("bluetti-files", { recursive: true });

  console.log(`Downloading ${serverFilename} from ${downloadUrl}...`);
  const resp = await fetch(downloadUrl);
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);

  const total = parseInt(resp.headers.get("content-length") || "0", 10);
  let downloaded = 0;

  const fh = await open(APK_PATH, "w");
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

  await writeFile(VERSION_PATH, serverFilename + "\n");

  console.log("\nDone.");
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
