# SPDX-License-Identifier: MIT
{ pkgs, self }:
let
  project = pkgs.herdr-purifier.buildHerdrProject { src = ../examples/minimal; };
in
{
  cli = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
  environment = project.packages.environment;
  project = project.tests;
  release = project.release;
}
