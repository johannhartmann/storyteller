{
  description = "Storyteller – reproducible Python-3.12 dev environment (poetry2nix)";
  inputs = {
    # pin nixpkgs to the 25.05 channel (includes Python 3.12)
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

    # poetry2nix after the April-2025 fix that switched to fetchCargoVendor
    # → commit 3d8e5f0 is encoded with ?rev=… in the URL
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
    };

    # flake-utils helper macros
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils, poetry2nix, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        /* Bind the helpers (`mkPoetryEnv`, `mkPoetryApplication`, …) to the
           exact pkgs set we pinned above – the pattern recommended in the
           poetry2nix README. */
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryEnv;

        # Build a Poetry virtual-env for Python-3.12
        pythonEnv = mkPoetryEnv {
          projectDir = self;           # expects pyproject.toml + poetry.lock here
          python     = pkgs.python312; # override default interpreter
        };
      in {
        # `nix develop` will drop you into this shell
        devShells.default = pythonEnv.env;

        # Optional: export the environment as a buildable package
        packages.storyteller = pythonEnv;
      });
}

