# SPDX-License-Identifier: MIT
{ herdr }:
herdr.overrideAttrs (old: {
  postPatch = (old.postPatch or "") + ''
    substituteInPlace src/persist/plugin_registry.rs \
      --replace-fail 'crate::config::config_dir().join("plugins.json")' \
        'std::env::var_os("HERDR_PURIFIER_REGISTRY_FILE").map(PathBuf::from).unwrap_or_else(|| crate::config::config_dir().join("plugins.json"))' \
      --replace-fail 'crate::config::config_dir().join(REGISTRY_LOCK_FILE)' \
        'registry_path().with_file_name(REGISTRY_LOCK_FILE)'
    substituteInPlace src/cli/plugin.rs \
      --replace-fail 'let total = plugin.build.len();' \
        'if std::env::var("HERDR_PURIFIER_CAPTURE").as_deref() == Ok("1") { return Ok(()); }
         let total = plugin.build.len();'
    substituteInPlace src/session.rs \
      --replace-fail 'crate::config::config_dir()' 'session_root_dir()' \
      --replace-fail 'pub fn data_dir() -> PathBuf {' \
        'fn session_root_dir() -> PathBuf {
            std::env::var_os("HERDR_PURIFIER_SESSION_ROOT").map(PathBuf::from).unwrap_or_else(crate::config::config_dir)
        }

        pub fn data_dir() -> PathBuf {'
    substituteInPlace src/session.rs \
      --replace-fail 'data_dir_for(name).join("herdr.sock")' \
        'purifier_socket_path_for(name, "herdr.sock").unwrap_or_else(|| data_dir_for(name).join("herdr.sock"))' \
      --replace-fail 'data_dir_for(name).join("herdr-client.sock")' \
        'purifier_socket_path_for(name, "herdr-client.sock").unwrap_or_else(|| data_dir_for(name).join("herdr-client.sock"))' \
      --replace-fail 'pub fn api_socket_path_for(name: Option<&str>) -> PathBuf {' \
        'fn purifier_socket_path_for(name: Option<&str>, file: &str) -> Option<PathBuf> {
            use sha2::{Digest, Sha256};
            let base = std::env::var_os("HERDR_PURIFIER_SOCKET_ROOT")?;
            let mut hash = Sha256::new();
            hash.update(data_dir_for(name).as_os_str().as_encoded_bytes());
            let identity = format!("{:x}", hash.finalize());
            Some(PathBuf::from(base).join(format!("{}-{}", &identity[..32], file)))
        }

        pub fn api_socket_path_for(name: Option<&str>) -> PathBuf {'
  '';
})
