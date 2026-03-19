import fs from "fs";
import path from "path";
import { initializeApp, cert, getApps } from "firebase-admin/app";
import { getDatabase } from "firebase-admin/database";

const DEFAULT_DATABASE_URL =
  "https://cisc475database-default-rtdb.firebaseio.com";
const DEFAULT_EXPORT_PATH = "/submissions";
const DEFAULT_OUTPUT_PATH =
  "src/mturk_results/live/cisc475database-default-rtdb-submissions-export.json";

function parseArgs(argv) {
  const parsed = {};

  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    const next = argv[index + 1];

    if (!current.startsWith("--")) {
      continue;
    }

    const key = current.slice(2);
    if (!next || next.startsWith("--")) {
      parsed[key] = "true";
      continue;
    }

    parsed[key] = next;
    index += 1;
  }

  return parsed;
}

function resolveServiceAccountPath(cliArgs) {
  return (
    cliArgs.serviceAccount ||
    process.env.FIREBASE_SERVICE_ACCOUNT_PATH ||
    "serviceAccountKey.json"
  );
}

function sortKeysDeep(value) {
  if (Array.isArray(value)) {
    return value.map(sortKeysDeep);
  }

  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort((left, right) => left.localeCompare(right))
      .reduce((accumulator, key) => {
        accumulator[key] = sortKeysDeep(value[key]);
        return accumulator;
      }, {});
  }

  return value;
}

async function main() {
  const cliArgs = parseArgs(process.argv.slice(2));
  const serviceAccountPath = resolveServiceAccountPath(cliArgs);
  const databaseURL =
    cliArgs.databaseUrl || process.env.FIREBASE_DATABASE_URL || DEFAULT_DATABASE_URL;
  const exportPath =
    cliArgs.exportPath || process.env.FIREBASE_EXPORT_PATH || DEFAULT_EXPORT_PATH;
  const outputPath =
    cliArgs.output || process.env.FIREBASE_EXPORT_OUTPUT || DEFAULT_OUTPUT_PATH;

  if (!fs.existsSync(serviceAccountPath)) {
    throw new Error(
      `Service account key not found at "${serviceAccountPath}". ` +
        "Set FIREBASE_SERVICE_ACCOUNT_PATH or pass --serviceAccount."
    );
  }

  const serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, "utf8"));

  if (getApps().length === 0) {
    initializeApp({
      credential: cert(serviceAccount),
      databaseURL,
    });
  }

  const db = getDatabase();
  const normalizedPath =
    exportPath === "/" ? "/" : exportPath.replace(/^\/+|\/+$/g, "");
  const snapshot =
    normalizedPath === "/" ? await db.ref("/").once("value") : await db.ref(normalizedPath).once("value");
  const data = snapshot.exists() ? snapshot.val() : null;
  const serialized = `${JSON.stringify(sortKeysDeep(data), null, 2)}\n`;

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, serialized, "utf8");

  console.log(`Exported Firebase path "${exportPath}" to ${outputPath}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
