# witty-agent-loader

This directory contains the source for the **`witty-agent-loader`** RPM subpackage (under `packaging/agent-loader/` in the `euler-copilot-shell` repo), which deploys the managed resources that accompany the `opencode` CLI as a system-managed installation.

## Goals

- `/etc/opencode/opencode.json` is owned by exactly one package
- Multiple Agent/Skill/Plugin sub-RPMs can install and uninstall cleanly without interfering with each other
- No per-package JSON editing in `%post` or `%postun` scripts
- Sub-packages can declare OpenCode Plugin entries via the `plugin` field in config.d fragments

## RPM directory layout

- `/usr/share/witty/opencode/skills/<rpm-name>/...` — skill assets from sub-RPMs
- `/usr/share/witty/opencode/agents/<rpm-name>/...` — prompt Markdown files and other file-based assets from sub-RPMs
- `/usr/share/witty/opencode/config.d/<rpm-name>.json` — `opencode.json`-compatible config fragments from sub-RPMs
- `/usr/share/witty/opencode/plugins/<rpm-name>/...` — OpenCode Plugin files deployed by sub-RPMs (optional)
- `/usr/libexec/witty-opencode/rebuild-managed-config.mjs` — config generator, owned by the loader package
- `/etc/opencode/opencode.json` — generated managed config

## How the generator works

`bin/rebuild-managed-config.mjs` scans `config.d/*.json`, treating each file as an `opencode.json`-compatible fragment. It rewrites relative `{file:...}` references to absolute paths and produces `/etc/opencode/opencode.json`.

The generated config includes:

- A fixed `skills.paths` entry pointing at the shared skills root
- All merged config sections (e.g. `agent`, `mcp`, `provider`, `permission`, `plugin`)

The generator is designed to run from `%posttrans` or a file trigger, so a single RPM transaction only rebuilds the managed config once.

### `plugin` field

Sub-packages can declare a `plugin` array in their config.d fragment to load OpenCode Plugins. Entries may be `file://` local file paths or npm package names. Plugin entries from multiple sub-packages are deduplicated and merged.

`plugin` is not a conflict namespace (conflict namespaces are `agent`, `command`, `mode`, `mcp`), so multiple sub-packages can each declare their own plugin entries without errors.

## RPM hook scripts

Two additional components ship with the loader package:

- `bin/run-managed-config-hook.sh` — a shared shell wrapper for use in RPM scriptlets and file triggers
- `../docs/witty-agent-loader-addon-packaging.md` — packaging conventions and spec guidance for Agent/Skill/config sub-RPM maintainers

### Why both `%posttrans` and file triggers?

- `%posttrans` handles the case where the **loader package itself** is installed or upgraded and needs to create or refresh `/etc/opencode/opencode.json`.
- `%transfiletriggerin` and `%filetriggerpostun` are the right tool for **sub-RPM lifecycle events**: they fire when files under `config.d`, `agents`, `skills`, or `plugins` directories are added or removed, even when the loader package is not part of the transaction. Removal uses the per-package `%filetriggerpostun` because `%transfiletriggerpostun` does not fire on package removal in rpm 4.17-4.19.

This split keeps sub-RPMs as plain data packages while the loader package remains the sole owner of generated config.

> When the loader package itself is erased, the monitored directories it owns are also removed, and rpm 4.18 may still run its own `%filetriggerpostun`. Since the hook script is already gone by then, an unconditional call fails with exit 127. The spec guards every hook invocation with `[ -x ... ]`, so a loader removal skips the rebuild cleanly.

### Failure policy

The shared hook is **fail-open** by default: it logs errors but exits successfully, so a failed config rebuild never leaves an RPM transaction in an incomplete state.

Set `WITTY_OPENCODE_RPM_HOOK_STRICT=1` before invoking the hook if your policy requires hard failure instead.

## Drop-in format

See `examples/config.d/witty-example.json` for a working example.

Each drop-in must be a valid `opencode.json` fragment:

- `$schema` is optional and ignored during merging
- Top-level sections such as `agent`, `mcp`, `provider`, `permission`, `command`, and `plugin` can be included directly
- Relative `{file:...}` tokens are resolved against the drop-in file's directory and rewritten to absolute paths in the generated `/etc/opencode/opencode.json`

If any managed namespace (`agent`, `command`, `mode`, `mcp`) contains duplicate names, the generator aborts before any atomic rename, leaving the previous config intact.

## Directory contents

- `bin/rebuild-managed-config.mjs` — config generation script
- `bin/run-managed-config-hook.sh` — RPM hook wrapper script
- `docs/witty-opencode-base.md` — user documentation (bundled into tarball)
- `examples/` — sample drop-in and prompt layout (not in tarball)

See `packaging/docs/witty-agent-loader-addon-packaging.md` in the repo for sub-RPM packaging conventions.
