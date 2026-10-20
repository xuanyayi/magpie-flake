{
  description = "Magpie built from upstream source with Nix-managed privacy and updates";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = {
    self,
    nixpkgs,
  }: let
    forAllSystems = nixpkgs.lib.genAttrs ["x86_64-linux" "aarch64-linux"];
  in {
    overlays.default = final: _: {
      magpie = final.callPackage ./package.nix {};
    };

    packages = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      magpie = pkgs.callPackage ./package.nix {};
    in {
      inherit magpie;
      default = magpie;
    });

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.magpie}/bin/magpie";
        meta.description = "Magpie with Nix-managed privacy and updates";
      };
    });

    checks = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      inherit (self.packages.${system}) magpie;
      updater = pkgs.runCommand "magpie-updater-tests" {nativeBuildInputs = [pkgs.python3 pkgs.git pkgs.bash];} ''
        cp -r ${./scripts} scripts
        cp -r ${./tests} tests
        python3 -B -m unittest discover -s tests -p 'test_*.py'
        touch $out
      '';
    });

    formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);
  };
}
