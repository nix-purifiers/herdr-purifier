final: prev: {
  herdr-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
