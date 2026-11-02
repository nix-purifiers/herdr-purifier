# herdr-purifier

Locked, Nix-resolved workflow plugins for Herdr.

## Quickstart

Declare plugins in `herdr-purifier.toml`:

```toml
[[plugins]]
name = "layout"
source = "ogulcancelik/herdr-plugin-examples/dev-layout-bootstrap"
```

Then use the supplied wrapper:

```sh
nix shell 'github:nix-purifiers/herdr-purifier'
herdr-purifier lock
herdr-purifier prefetch
herdr
```

Commit `herdr-purifier.toml`, `herdr-plugins.lock.json` and
`herdr-purifier.lock.json`. Ignore `.herdr-purifier/`.
You can install the wrapper through your usual Nix configuration.

Locked projects use their own native Herdr sessions, so an existing
ordinary server cannot supply a different set of plugins. Named sessions
such as `herdr --session work` work within the project. Normal Herdr
configuration and plugin config/state directories are retained.
Project session state lives under `.herdr-purifier/`.

Without a companion lock, the wrapper warns and runs ordinary, impure
Herdr with its normal sessions. Invalid or stale locks fail with a repair
instruction.

## Lock and update

```sh
herdr-purifier lock
herdr-purifier update layout
herdr-purifier update
```

The native installer selects and validates each plugin. The companion
records exact Git commits, source hashes and native registry metadata.
`lock` retains valid selections; `update NAME` updates one plugin, and
`update` updates all plugins. Names can be declaration aliases or native
plugin ids.

A declaration can also specify `ref`, `enabled` and an explicit Git
mirror `url`. Otherwise it follows the repository's default branch and
is enabled. Sources use native `owner/repo[/subdir]` syntax.

`prefetch` fetches sources with Nix and runs native installation and
build commands in the sandbox. The prepared plugins are registered from
the Nix store using native manifest validation. Herdr and plugin actions
then run outside the sandbox. Prefetch roots each prepared graph and SDK,
including older graphs used by existing project sessions.

Use the helper for dependency changes. Guarded native plugin
install/update/link/unlink/uninstall commands are rejected. Native
plugin enable/disable commands remain available within the prepared
registry. Update the supplied Herdr SDK through your Nix configuration.

## External locks

```sh
herdr-purifier \
  --project ./app \
  --lockfile ./locks/companion.json \
  --tool-lockfile ./locks/plugins.json \
  lock

export HERDR_PURIFIER_LOCKFILE="$PWD/locks/companion.json"
export HERDR_PURIFIER_TOOL_LOCKFILE="$PWD/locks/plugins.json"
cd app
herdr plugin list
```

The working tree's native lock remains untouched. `--native-lock` and
`HERDR_PURIFIER_NATIVE_LOCKFILE` also select the native registry lock.

## Nix builds

The overlay exposes `pkgs.herdr-purifier.buildHerdrProject`:

```nix
pkgs.herdr-purifier.buildHerdrProject {
  src = ./.;
}
```

It returns `packages`, `tests`, `release` and `fetches`.
`packages.project` and `packages.environment` provide built plugins and
the prepared native registry. Output names and fetch declarations are
available during evaluation without building. `lockFile` and
`pluginLock` select external locks. `nativeBuildInputs` supplies extra
build tools; `fetchers` can supply alternative Nix fetch implementations.

## Releases

```sh
herdr-purifier publish \
  --repo OWNER/REPOSITORY \
  --tag v0.1.0
```

This creates or updates a GitHub release with a deterministic Nix-built
source archive containing the declarations and both locks.
Authentication uses ordinary `gh` configuration.

## Scope

Supports GitHub-style plugin sources and public HTTP(S)/Git mirrors,
including plugin subdirectories. Git submodules are not yet supported.
The SDK includes Bash, Python, Node.js and Lua. Build hooks must work
offline from declared inputs; plugins with language package dependencies
need the corresponding purifier integration or a composed Nix build.

Locked remote-machine sessions are not yet supported; run the wrapper
on the target machine. The SDK targets x86_64-linux and aarch64-linux.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
