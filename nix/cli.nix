# SPDX-License-Identifier: MIT
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  nativeHerdr,
  toolchain,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "herdr-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/herdr-purifier"
    cp -r herdr_purifier nix "$out/lib/herdr-purifier/"
    install -m755 bin/herdr-purifier "$out/bin/herdr-purifier"
    substituteInPlace "$out/lib/herdr-purifier/nix/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' \
      --replace-fail '@purifier@' '${purifierSrc}' \
      --replace-fail '@runtime@' "$out"
    wrapProgram "$out/bin/herdr-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set HERDR_PURIFIER_HERDR ${nativeHerdr}/bin/herdr \
      --set HERDR_PURIFIER_HERDR_VERSION ${nativeHerdr.version}
    makeWrapper "$out/bin/herdr-purifier" "$out/bin/herdr" --add-flags 'native --'
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Herdr workflow with locked Nix-resolved plugins";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "herdr-purifier";
  };
}
