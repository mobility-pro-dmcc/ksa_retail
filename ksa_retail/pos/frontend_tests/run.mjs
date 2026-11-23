/**
 * Unit tests for the POS frontend domain logic (pure TypeScript, no DOM).
 *   node apps/ksa_retail/ksa_retail/pos/frontend_tests/run.mjs
 * Bundles each *.test.ts with Frappe's esbuild and runs it with Node's test runner.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.resolve(here, "../../../../frappe/package.json"));
const esbuild = require("esbuild");
const out = mkdtempSync(path.join(tmpdir(), "ksa-pos-tests-"));

try {
	const entries = readdirSync(here).filter((name) => name.endsWith(".test.ts"));
	const outputs = [];
	for (const entry of entries) {
		const outfile = path.join(out, entry.replace(/\.ts$/, ".mjs"));
		esbuild.buildSync({ entryPoints: [path.join(here, entry)], bundle: true, platform: "node", format: "esm", outfile, logLevel: "error" });
		outputs.push(outfile);
	}
	const result = spawnSync(process.execPath, ["--test", ...outputs], { stdio: "inherit" });
	process.exitCode = result.status ?? 1;
} finally {
	rmSync(out, { recursive: true, force: true });
}
