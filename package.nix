# Adapted from mtul0729/magpie-flake c420f20ba48cf880e167e011fd584980af270f15.
# See LICENSE and README.md for attribution and the downstream policy.
{
  lib,
  buildGoModule,
  fetchFromGitHub,
  fetchurl,
  makeDesktopItem,
  makeWrapper,
  pkg-config,
  gtk4,
  webkitgtk_6_0,
  bun,
}: let
  source = builtins.fromJSON (builtins.readFile ./sources.json);
  # CVE-2026-111497 is fixed in Bun 1.4.4. Keep this floor even when a
  # consumer follows an older nixpkgs; prefer its Bun once it is new enough.
  # Backport of NixOS/nixpkgs 54de6a06226b3ac00fa6446a28b3087205fe7042.
  bunRuntime =
    if lib.versionAtLeast bun.version "1.4.4"
    then bun
    else
      bun.overrideAttrs (finalAttrs: previousAttrs: {
        version = "1.4.4";
        src = finalAttrs.passthru.sources.x86_64-linux;
        passthru =
          previousAttrs.passthru
          // {
            sources = {
              x86_64-linux = fetchurl {
                url = "https://github.com/oven-sh/bun/releases/download/bun-v${finalAttrs.version}/bun-linux-x64-baseline.zip";
                hash = "sha256-4ERutVmVdy65iUvrrppr42jZhai5Jx7hJEhvmUbu3XY=";
              };
            };
          };
      });
in
  buildGoModule (finalAttrs: {
    pname = "magpie";
    version = source.version;

    src = fetchFromGitHub {
      owner = "yetone";
      repo = "magpie";
      inherit (source) rev hash;
    };

    inherit (source) vendorHash;
    subPackages = ["."];

    patches = [
      ./patches/no-self-desktop-file.patch
      ./patches/no-double-tray-item-cosmic.patch
      ./patches/nix-policy.patch
    ];

    postPatch = ''
      cp ${./tests/settings_test.go} internal/settings/nix_policy_test.go
      cp ${./tests/stats_test.go} internal/stats/nix_policy_test.go
      cp ${./tests/plugin_test.go} internal/plugin/nix_policy_test.go
    '';

    tags = ["production"];
    ldflags = ["-s" "-w" "-X main.version=v${finalAttrs.version}"];

    nativeBuildInputs = [pkg-config makeWrapper];
    buildInputs = [gtk4 webkitgtk_6_0];

    # Exercise the downstream policy without running account/network integration tests.
    doCheck = true;
    checkPhase = ''
      runHook preCheck
      go test -count=1 -timeout=120s -run '^(TestNix.*|TestCheckUpdates|TestPinned)$' ./internal/settings ./internal/stats ./internal/plugin
      runHook postCheck
    '';

    postInstall = let
      desktopItem = makeDesktopItem {
        name = "magpie";
        desktopName = "Magpie";
        comment = "Every agent's model, one place";
        exec = "magpie %U";
        icon = "magpie";
        categories = ["Development" "Utility"];
        startupWMClass = "magpie";
        terminal = false;
        mimeTypes = ["x-scheme-handler/magpie"];
      };
    in ''
      install -Dm644 build/windows/icon-256.png $out/share/icons/hicolor/256x256/apps/magpie.png
      install -Dm644 ${desktopItem}/share/applications/magpie.desktop $out/share/applications/magpie.desktop
      install -Dm644 LICENSE $out/share/licenses/magpie/LICENSE
    '';

    postFixup = ''
      wrapProgram $out/bin/magpie --set MAGPIE_BUN ${lib.getExe bunRuntime}
    '';

    passthru.bun = bunRuntime;

    doInstallCheck = true;
    installCheckPhase = ''
      runHook preInstallCheck
      export HOME=$(mktemp -d)
      export XDG_CONFIG_HOME="$HOME/.config"
      export XDG_CACHE_HOME="$HOME/.cache"
      export XDG_DATA_HOME="$HOME/.local/share"
      export XDG_STATE_HOME="$HOME/.local/state"
      ${lib.getExe bunRuntime} --version | grep -Fx '${bunRuntime.version}'
      ${lib.getExe bunRuntime} -e '
        const { brotliCompressSync, brotliDecompressSync } = require("node:zlib");
        const input = "magpie plugin runtime";
        if (brotliDecompressSync(brotliCompressSync(input)).toString() !== input) {
          throw new Error("Bun Brotli round trip failed");
        }
      '
      $out/bin/magpie version | grep -F '${finalAttrs.version}'
      $out/bin/magpie update auto | grep -F 'automatic updates are off'
      runHook postInstallCheck
    '';

    meta = {
      description = "AI agent model and subscription manager with Nix-managed updates";
      homepage = "https://usemagpie.ai";
      license = lib.licenses.mit;
      mainProgram = "magpie";
      platforms = ["x86_64-linux"];
    };
  })
