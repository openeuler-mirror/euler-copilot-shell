#!/usr/bin/env node

/*
 * Copyright (c) 2026 openEuler
 * Witty OpenCode is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *          http://license.coscl.org.cn/MulanPSL2
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 */

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const CONFIG_SCHEMA_URL = "https://opencode.ai/config.json";
const TUI_SCHEMA_URL = "https://opencode.ai/tui.json";
const FILE_TOKEN_RE = /\{file:([^}]+)\}/g;
const CONFLICT_NAMESPACES = ["agent", "command", "mode", "mcp"];

const DEFAULTS = {
  configDropins: "/usr/share/witty/opencode/config.d",
  skillsRoot: "/usr/share/witty/opencode/skills",
  opencodeOutput: "/etc/opencode/opencode.json",
  tuiOutput: "/etc/opencode/tui.json",
  logoPlugin: "/usr/share/witty/opencode/plugins/logo/witty-logo.tsx",
};

const OPTION_ALIASES = {
  agentDropins: "configDropins",
};

const usage = `Usage: node rebuild-managed-config.mjs [options]

Options:
  --config-dropins <dir>   Directory containing opencode.json fragment files.
  --agent-dropins <dir>    Deprecated alias of --config-dropins.
  --skills-root <dir>      Root directory for shared skill bundles.
  --opencode-output <file> Output path for /etc/opencode/opencode.json.
  --tui-output <file>      Output path for /etc/opencode/tui.json.
  --logo-plugin <file>     Absolute plugin path to install into tui.json.
  --dry-run                Print generated JSON to stdout without writing.
  --help                   Show this message.
`;

function parseArgs(argv) {
  const options = { ...DEFAULTS, dryRun: false };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help") {
      options.help = true;
      continue;
    }
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (!arg.startsWith("--")) {
      throw new Error(`Unexpected argument: ${arg}`);
    }

    const rawKey = arg
      .slice(2)
      .replace(/-([a-z])/g, (_, char) => char.toUpperCase());
    const key = OPTION_ALIASES[rawKey] ?? rawKey;
    if (!(key in options)) {
      throw new Error(`Unknown option: ${arg}`);
    }

    index += 1;
    const value = argv[index];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for ${arg}`);
    }
    options[key] = value;
  }

  return options;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function cloneValue(value) {
  if (Array.isArray(value)) return value.map(cloneValue);
  if (isObject(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [key, cloneValue(nested)])
    );
  }
  return value;
}

function dedupeArray(values) {
  const seen = new Set();
  const result = [];

  for (const value of values) {
    const key = JSON.stringify(value);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }

  return result;
}

function mergeValues(target, source) {
  if (source === undefined) return cloneValue(target);
  if (target === undefined) return cloneValue(source);

  if (Array.isArray(target) && Array.isArray(source)) {
    return dedupeArray([...target.map(cloneValue), ...source.map(cloneValue)]);
  }

  if (isObject(target) && isObject(source)) {
    const merged = { ...target };
    for (const [key, value] of Object.entries(source)) {
      merged[key] =
        key in merged ? mergeValues(merged[key], value) : cloneValue(value);
    }
    return merged;
  }

  return cloneValue(source);
}

function rewriteFileTokens(value, baseDir) {
  return value.replace(FILE_TOKEN_RE, (_, rawPath) => {
    if (rawPath.startsWith("~/") || path.isAbsolute(rawPath)) {
      return `{file:${rawPath}}`;
    }
    return `{file:${path.resolve(baseDir, rawPath)}}`;
  });
}

function rewriteFragmentValue(value, baseDir) {
  if (typeof value === "string") return rewriteFileTokens(value, baseDir);
  if (Array.isArray(value))
    return value.map((item) => rewriteFragmentValue(item, baseDir));
  if (!isObject(value)) return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, nested]) => [
      key,
      rewriteFragmentValue(nested, baseDir),
    ])
  );
}

async function readJson(filePath) {
  const text = await fs.readFile(filePath, "utf8");
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(
      `Invalid JSON in ${filePath}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

async function listJsonFiles(dirPath) {
  const entries = await fs
    .readdir(dirPath, { withFileTypes: true })
    .catch((error) => {
      if (
        error &&
        typeof error === "object" &&
        "code" in error &&
        error.code === "ENOENT"
      ) {
        return [];
      }
      throw error;
    });

  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => path.join(dirPath, entry.name))
    .sort((left, right) => left.localeCompare(right));
}

function normalizeFragment(filePath, raw) {
  if (!isObject(raw)) {
    throw new Error(`${filePath}: config fragment root must be an object`);
  }

  const fragment = { ...raw };
  delete fragment.$schema;
  return rewriteFragmentValue(fragment, path.dirname(filePath));
}

function recordNamespaceConflicts(fragment, source, seenNamespaces) {
  for (const namespace of CONFLICT_NAMESPACES) {
    const section = fragment[namespace];
    if (!isObject(section)) continue;

    if (!seenNamespaces.has(namespace)) {
      seenNamespaces.set(namespace, new Map());
    }

    const seenKeys = seenNamespaces.get(namespace);
    for (const key of Object.keys(section)) {
      if (seenKeys.has(key)) {
        throw new Error(
          `Duplicate ${namespace} entry \"${key}\" declared in ${source} and ${seenKeys.get(key)}.`
        );
      }
      seenKeys.set(key, source);
    }
  }
}

async function buildManagedConfig(options) {
  let config = {
    $schema: CONFIG_SCHEMA_URL,
    skills: {
      paths: [options.skillsRoot],
    },
  };

  const seenNamespaces = new Map();
  const files = await listJsonFiles(options.configDropins);

  for (const filePath of files) {
    const raw = await readJson(filePath);
    const fragment = normalizeFragment(filePath, raw);
    recordNamespaceConflicts(fragment, filePath, seenNamespaces);
    config = mergeValues(config, fragment);
  }

  config.$schema = CONFIG_SCHEMA_URL;
  config.skills = mergeValues(
    {
      paths: [options.skillsRoot],
    },
    config.skills
  );

  return config;
}

function buildTuiConfig(options) {
  const config = {
    $schema: TUI_SCHEMA_URL,
  };

  if (options.logoPlugin) {
    config.plugin = [options.logoPlugin];
  }

  return config;
}

async function writeJsonAtomic(outputPath, value) {
  const dirPath = path.dirname(outputPath);
  await fs.mkdir(dirPath, { recursive: true });
  const tempPath = path.join(
    dirPath,
    `.${path.basename(outputPath)}.${process.pid}.${Date.now()}.tmp`
  );
  const text = `${JSON.stringify(value, null, 2)}\n`;
  await fs.writeFile(tempPath, text, "utf8");
  await fs.rename(tempPath, outputPath);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(usage);
    return;
  }

  const opencodeConfig = await buildManagedConfig(options);
  const tuiConfig = buildTuiConfig(options);

  if (options.dryRun) {
    process.stdout.write(
      JSON.stringify({ opencodeConfig, tuiConfig }, null, 2)
    );
    process.stdout.write("\n");
    return;
  }

  await writeJsonAtomic(options.opencodeOutput, opencodeConfig);
  await writeJsonAtomic(options.tuiOutput, tuiConfig);
}

main().catch((error) => {
  process.stderr.write(
    `rebuild-managed-config: ${error instanceof Error ? error.message : String(error)}\n`
  );
  process.exitCode = 1;
});
