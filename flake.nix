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

        pkgs = import nixpkgs { 
          inherit system; 
          overlays = [ overlay ];
        };

        # ---- 2️⃣  bind poetry2nix helpers to that patched pkgs set -----
        p2n = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        inherit (p2n) mkPoetryEnv;

        # ---- 3️⃣  build the Python-3.12 env from your Poetry metadata --
        pythonEnv = mkPoetryEnv {
          projectDir = self;           # expects pyproject.toml + poetry.lock
          python     = pkgs.python312;
          # optional speed-up if you prefer wheels:
          preferWheels = true;
          
          # Override packages that need special handling
          overrides = p2n.overrides.withDefaults (self: super: {
            azure-cognitiveservices-speech = super.azure-cognitiveservices-speech.overridePythonAttrs (old: {
              preferWheel = true;
              format = "wheel";
              nativeBuildInputs = (old.nativeBuildInputs or []) ++ [
                pkgs.autoPatchelfHook  # patches rpath/SONAME for binary dependencies
              ];
              buildInputs = (old.buildInputs or []) ++ [
                pkgs.openssl  # Azure SDK 1.44.0 supports OpenSSL 3.0
                pkgs.alsa-lib
                pkgs.pulseaudio
                pkgs.gst_all_1.gstreamer
                pkgs.gst_all_1.gst-plugins-base
                pkgs.curl
                pkgs.cacert
                pkgs.zlib
                pkgs.stdenv.cc.cc.lib  # Modern C++ standard library
              ];
              # Skip tests as SDK brings its own
              doCheck = false;
              
              # Ensure the SDK libraries stay together
              postInstall = ''
                # Find the Azure SDK directory
                AZURE_DIR=$(find $out -path "*/azure/cognitiveservices/speech" -type d | head -n1)
                if [ -n "$AZURE_DIR" ]; then
                  echo "Azure SDK directory: $AZURE_DIR"
                  # List all .so files to verify they're all there
                  ls -la "$AZURE_DIR"/*.so || true
                fi
              '';
            });
          });
        };
      in {
        devShells.default = pkgs.mkShell {
          inputsFrom = [ pythonEnv.env ];
          buildInputs = with pkgs; [ 
            cacert 
            alsa-lib
            pulseaudio
            ruff
          ];
          shellHook = ''
            export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
            export CURL_CA_BUNDLE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
            
            # Add ALSA and other libraries to LD_LIBRARY_PATH
            export LD_LIBRARY_PATH="${pkgs.alsa-lib}/lib:${pkgs.pulseaudio}/lib:$LD_LIBRARY_PATH"
            
            # Find Azure SDK directory and add to LD_LIBRARY_PATH
            AZURE_SDK_DIR=$(python -c 'import site, os; p = next((os.path.join(s, "azure/cognitiveservices/speech") for s in site.getsitepackages() if os.path.exists(os.path.join(s, "azure/cognitiveservices/speech"))), None); print(p if p else "")' 2>/dev/null)
            if [ -n "$AZURE_SDK_DIR" ]; then
              export LD_LIBRARY_PATH="$AZURE_SDK_DIR:$LD_LIBRARY_PATH"
              echo "Azure SDK libraries added to LD_LIBRARY_PATH: $AZURE_SDK_DIR"
            fi
            
            echo "ALSA lib available at: ${pkgs.alsa-lib}/lib"
          '';
        };
        packages.storyteller = pythonEnv;           # `nix build .#storyteller`
      });
}

