# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  nativeHerdr,
  toolchain,
  purifier,
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-herdr-plugin-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  metadata = writeText "herdr-plugin-graph.json" (builtins.toJSON checked.data);
in
runCommand "purified-herdr-plugins"
  {
    nativeBuildInputs = [
      toolchain
      python3
    ]
    ++ nativeBuildInputs;
  }
  ''
    export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_STATE_HOME="$TMPDIR/state" XDG_CACHE_HOME="$TMPDIR/cache" XDG_RUNTIME_DIR="$TMPDIR/runtime"
    export HERDR_PURIFIER_REGISTRY_FILE="$TMPDIR/plugins.json"
    export HERDR_PURIFIER_SESSION_ROOT="$TMPDIR/sessions"
    export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
    export SOURCE_DATE_EPOCH=1
    mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"
    python3 ${../herdr_purifier/build.py} ${metadata} ${sources} "$out" ${nativeHerdr}/bin/herdr
    ln -s ${sources} "$out/sources"
  ''
