# SPDX-License-Identifier: MIT
{ lib }:
{
  src,
  lockFile ? src + "/herdr-purifier.lock.json",
  pluginLock ? src + "/herdr-plugins.lock.json",
}:
let
  fix = message: "herdr-purifier: ${message}; run herdr-purifier lock";
  exists =
    builtins.pathExists lockFile
    && builtins.pathExists pluginLock
    && builtins.pathExists (src + "/herdr-purifier.toml");
  raw =
    if exists then
      builtins.addErrorContext (fix "invalid companion JSON") (
        builtins.fromJSON (builtins.readFile lockFile)
      )
    else
      { };
  data = if builtins.isAttrs raw then raw else { };
  text = if exists then builtins.readFile (src + "/herdr-purifier.toml") else "";
  config =
    if exists then
      builtins.addErrorContext (fix "invalid plugin declarations") (builtins.fromTOML text)
    else
      { };
  nativeText = if exists then builtins.readFile pluginLock else "";
  native =
    if exists then
      builtins.addErrorContext (fix "invalid native registry JSON") (builtins.fromJSON nativeText)
    else
      [ ];
  pathOK =
    p:
    builtins.isString p
    && p != ""
    && !lib.hasPrefix "/" p
    && !lib.hasInfix "\\" p
    && builtins.all (
      v:
      !(builtins.elem v [
        ""
        "."
        ".."
      ])
    ) (lib.splitString "/" p);
  nameOK = n: builtins.isString n && builtins.match "[A-Za-z0-9][A-Za-z0-9_-]*" n != null;
  urlOK = u: builtins.isString u && builtins.match "(https?|git|file)://[^[:space:]@]+" u != null;
  refOK =
    r:
    r == null
    || (
      builtins.isString r && r != "" && !lib.hasPrefix "-" r && builtins.match "[^[:space:]]+" r != null
    );
  itemOK =
    p:
    builtins.isAttrs p
    && nameOK (p.name or null)
    && pathOK (p.source or null)
    && builtins.match "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(/[^[:space:]]+)?" p.source != null
    && urlOK (
      p.url
        or "https://github.com/${lib.concatStringsSep "/" (lib.take 2 (lib.splitString "/" p.source))}.git"
    )
    && refOK (p.ref or null)
    && builtins.isBool (p.enabled or true);
  items = config.plugins or null;
  configOK =
    builtins.isList items
    && builtins.all itemOK items
    && builtins.length (lib.unique (map (p: p.name) items)) == builtins.length items;
  ordered = lib.sort (a: b: a.name < b.name) items;
  hex40 = v: builtins.isString v && builtins.match "[0-9a-f]{40}" v != null;
  b64 =
    v:
    builtins.isString v
    && builtins.match "([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?" v != null;
  selectedOK =
    item: p:
    let
      info = p.plugin or { };
      source = info.source or { };
      entry = p.entry or { };
      git = entry.git or { };
      parts = lib.splitString "/" item.source;
      subdir = lib.concatStringsSep "/" (lib.drop 2 parts);
      root = "plugins/${item.name}" + lib.optionalString (subdir != "") "/${subdir}";
    in
    builtins.isAttrs p
    && (p.name or null) == item.name
    && builtins.isAttrs info
    && builtins.isString (info.plugin_id or null)
    && builtins.match "[A-Za-z0-9.:_-]+" info.plugin_id != null
    && builtins.isString (info.name or null)
    && builtins.isString (info.version or null)
    && (info.plugin_root or null) == root
    && (info.manifest_path or null) == root + "/herdr-plugin.toml"
    && (info.enabled or null) == (item.enabled or true)
    && builtins.isAttrs source
    && (source.kind or null) == "github"
    && (source.owner or null) == builtins.elemAt parts 0
    && (source.repo or null) == builtins.elemAt parts 1
    && (source.subdir or null) == (if subdir == "" then null else subdir)
    && (source.requested_ref or null) == (item.ref or null)
    && hex40 (source.resolved_commit or null)
    && (source.managed_path or null) == "plugins/${item.name}"
    && (source.installed_unix_ms or null) == 0
    && builtins.isAttrs entry
    && (entry.path or null) == item.name
    && builtins.isString (entry.hash or null)
    && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
    && builtins.isAttrs git
    &&
      (git.url or null)
      == (item.url or "https://github.com/${builtins.elemAt parts 0}/${builtins.elemAt parts 1}.git")
    && (git.rev or null) == source.resolved_commit
    && (git.leaveDotGit or null) == true
    && (git.submodules or null) == false
    && builtins.isAttrs (git.commitObject or null)
    && b64 (git.commitObject.object or null)
    && (git.commitObject.gitlinks or null) == [ ];
  plugins = data.plugins or null;
  problems = map fix (
    if !exists then
      [ "missing declarations or native/companion lock" ]
    else if !builtins.isAttrs raw || (data.version or null) != 1 then
      [ "unsupported companion format" ]
    else if
      (data.contentHash or null)
      != builtins.hashString "sha256" (builtins.toJSON (removeAttrs data [ "contentHash" ]))
    then
      [ "companion contentHash mismatch" ]
    else if !configOK then
      [ "invalid plugin declarations" ]
    else if
      (data.configHash or null) != builtins.hashString "sha256" text || (data.config or null) != text
    then
      [ "plugin declarations changed" ]
    else if
      (data.nativeHash or null) != builtins.hashString "sha256" nativeText
      || (data.nativeLock or null) != nativeText
    then
      [ "native registry lock changed" ]
    else if !builtins.isList plugins || builtins.length plugins != builtins.length ordered then
      [ "incomplete native plugin graph" ]
    else if
      !builtins.all (i: selectedOK (builtins.elemAt ordered i) (builtins.elemAt plugins i)) (
        lib.range 0 (builtins.length ordered - 1)
      )
    then
      [ "native Git plugin export changed" ]
    else if
      !builtins.isList native
      || native != map (p: p.plugin) plugins
      || builtins.length (lib.unique (map (p: p.plugin.plugin_id) plugins)) != builtins.length plugins
    then
      [ "native registry pins do not match export" ]
    else
      [ ]
  );
in
{
  purifier = "herdr-purifier";
  inherit problems data;
  entries = if problems == [ ] then map (p: p.entry) plugins else [ ];
  outputs =
    if problems == [ ] then
      {
        project = { };
        environment = { };
      }
    else
      { };
}
