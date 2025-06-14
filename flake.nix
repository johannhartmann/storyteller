{
  description = "Dev-Shell für Projekt XYZ";

  inputs = {
    nixpkgs     = { url = "github:NixOS/nixpkgs/nixos-25.05"; };
    flake-utils = { url = "github:numtide/flake-utils"; };
    mach-nix    = { url = "github:DavHau/mach-nix"; };
  };

  outputs = { self, nixpkgs, flake-utils, mach-nix, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs      = import nixpkgs { inherit system; };
        pythonEnv = mach-nix.lib."${system}".mkPython {
          python      = pkgs.python312Full;
          requirements = builtins.readFile ./requirements.txt;
        };
      in {
        devShells.${system}.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ];
          shellHook = ''
            echo "🦄 Python 3.12-Umgebung geladen"
          '';
        };
      }
    );
}

