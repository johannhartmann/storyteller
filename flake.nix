{
  description = "Storyteller – Python-3.12 dev env with poetry2nix";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-25.05";                # 3.12 lives here :contentReference[oaicite:0]{index=0}
    poetry2nix.url  = "github:nix-community/poetry2nix";                 # any commit; overlay fixes helper
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, poetry2nix, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # ---- 1️⃣  overlay that restores removed helper -----------------
        overlay = final: prev: {
          rustPlatform = prev.rustPlatform // {
            fetchCargoTarball = prev.rustPlatform.fetchCargoVendor;      # alias :contentReference[oaicite:1]{index=1}
          };
        };

        pkgs = import nixpkgs { inherit system; overlays = [ overlay ]; };

        # ---- 2️⃣  bind poetry2nix helpers to that patched pkgs set -----
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryEnv;

        # ---- 3️⃣  build the Python-3.12 env from your Poetry metadata --
        pythonEnv = mkPoetryEnv {
          projectDir = self;           # expects pyproject.toml + poetry.lock
          python     = pkgs.python312;
          # optional speed-up if you prefer wheels:
          preferWheels = true;
        };
      in {
        devShells.default = pythonEnv.env;          # `nix develop`
        packages.storyteller = pythonEnv;           # `nix build .#storyteller`
      });
}

