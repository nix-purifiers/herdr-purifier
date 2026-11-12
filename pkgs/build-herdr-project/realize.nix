# SPDX-License-Identifier: MIT
{
  project,
  lockFile,
  pluginLock,
  target,
}:
let
  pkgs = import (/. + "@nixpkgs@") { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeHerdr = pkgs.callPackage ./herdr.nix { };
  toolchain = pkgs.buildEnv {
    name = "herdr-purifier-toolchain";
    paths = [
      nativeHerdr
      pkgs.git
      pkgs.bash
      pkgs.python3
      pkgs.nodejs
      pkgs.lua
      pkgs.coreutils
    ];
  };
  args = {
    src = /. + project;
    lockFile = /. + lockFile;
    pluginLock = /. + pluginLock;
  };
  lock = import ../../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } args;
in
if target == "environment" then
  pkgs.callPackage ./environment.nix { inherit purifier nativeHerdr toolchain; } { inherit lock; }
else if target == "runtime" then
  pkgs.runCommand "herdr-purifier-runtime" { } ''ln -s @runtime@ "$out"''
else if target == "release" then
  (pkgs.callPackage ./default.nix { inherit purifier nativeHerdr toolchain; } args).release
else
  throw "herdr-purifier: unknown realization target ${target}"
