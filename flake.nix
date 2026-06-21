{
  description = "A basic flake installing pdm package manager (for use with venv)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    pyproject-nix = {
      url = "github:nix-community/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, nixpkgs-unstable, pyproject-nix, ... }:
    let
      inherit (nixpkgs) lib;

      project = pyproject-nix.lib.project.loadPyproject {
        # Read & unmarshal pyproject.toml relative to this project root.
        # projectRoot is also used to set `src` for renderers such as buildPythonPackage.
        projectRoot = ./.;
      };

      # This example is only using x86_64-linux
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      pkgs-unstable = nixpkgs-unstable.legacyPackages.${system};

      python = pkgs.python3;

    in
    {
      # Build our package using `buildPythonPackage`
      # packages.${system}.default =
        # let
        #   # Returns an attribute set that can be passed to `buildPythonPackage`.
        #   attrs = project.renderers.buildPythonPackage { inherit python; };
        # in
        # # Pass attributes to buildPythonPackage.
        # # Here is a good spot to add on any missing or custom attributes.
        # python.pkgs.buildPythonPackage (attrs // {
        #   env.CUSTOM_ENVVAR = "hello";
        # });

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          # pkgs.pdm on nixos-26.05 currently fails to build; unstable has a cached binary.
          pkgs-unstable.pdm
          python
          python.pkgs.virtualenv
        ];

        shellHook = ''
          unset PYTHONPATH
          export PDM_IGNORE_SAVED_PYTHON=1
        '';
      };
    };
}
