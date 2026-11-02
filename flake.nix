# SPDX-License-Identifier: MIT
{
  description = "Locked, Nix-resolved workflow plugins for Herdr";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        herdr-purifier = final.lib.makeScope final.newScope (scope: {
          nativeHerdr = scope.callPackage ./nix/herdr.nix { };
          toolchain = final.buildEnv {
            name = "herdr-purifier-toolchain";
            paths = [
              scope.nativeHerdr
              final.git
              final.bash
              final.python3
              final.nodejs
              final.lua
              final.coreutils
            ];
          };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildHerdrProject = scope.callPackage ./nix/build-project.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        native = (pkgsFor system).herdr-purifier.nativeHerdr;
        default = (pkgsFor system).herdr-purifier.cli;
        cli = self.packages.${system}.default;
      });
      lib.herdr-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/herdr-purifier";
          meta.description = "Lock and prefetch Herdr workflow plugins";
        };
      });
      checks = forAll (
        system:
        import ./tests {
          pkgs = pkgsFor system;
          inherit self;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
