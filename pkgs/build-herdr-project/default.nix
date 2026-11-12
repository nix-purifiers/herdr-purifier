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
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/herdr-purifier.lock.json",
  pluginLock ? src + "/herdr-plugins.lock.json",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".herdr-purifier"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      inherit src lockFile pluginLock;
    }
  );
  environment = import ./environment.nix {
    inherit
      lib
      runCommand
      fetchgit
      python3
      writeText
      nativeHerdr
      toolchain
      purifier
      ;
  } { inherit lock fetchers nativeBuildInputs; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  release =
    assert lock.problems == [ ];
    runCommand "herdr-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir source "$out"
        cp -r ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/herdr-purifier.lock.json
        cp ${pluginLock} source/herdr-plugins.lock.json
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -C source -cf - . | gzip -n > "$out/project.tar.gz"
      '';
in
{
  packages = {
    inherit environment;
    project = environment;
    default = environment;
  };
  tests = environment;
  inherit release;
  fetches = lock.entries;
}
