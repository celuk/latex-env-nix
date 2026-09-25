{
  description = "LaTeX + draw.io document build environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        # TeX Live scheme-small (pdflatex + recommended packages: geometry,
        # hyperref, booktabs, xcolor, tabularx, pifont, ...) plus only the
        # extras this repo actually uses. ~0.7 GB instead of ~7 GB for
        # scheme-full. If a document needs a missing package, add it here
        # (find the name with: nix search nixpkgs texlivePackages.<name>).
        texlive = pkgs.texliveSmall.withPackages (ps: [
          ps.latexmk # build driver used by the Makefile
          ps.texcount # make count
          ps.standalone # scripts/latex_table_to_png.py
          ps.varwidth # scripts/latex_table_to_png.py
          ps.biber # biblatex bibliographies
          ps.biblatex
          ps.collection-langeuropean # babel support (turkish, ...)
          ps.pgf # tikz
        ]);
      in
      {
        # mkShellNoCC: no C compiler toolchain in the closure (nothing here
        # compiles C).
        devShells.default = pkgs.mkShellNoCC {
          shellHook = ''
            ${pkgs.lib.optionalString pkgs.stdenv.isDarwin ''
              # macOS Terminal leaves LANG unset when the system region has
              # no exact POSIX locale (e.g. "en_TR"). Apple's
              # /etc/bashrc_Apple_Terminal then makes the nix bash re-run
              # setlocale() at every prompt, which fails and prints
              # "setlocale: LC_COLLATE: cannot change locale ()".
              # Exporting a valid default locale silences that for this
              # shell and everything it spawns (make, latexmk, perl, ...).
              if [ -z "''${LANG:-}" ]; then
                export LANG=en_US.UTF-8
              fi

              # On macOS the nix drawio package ships an app bundle, not a
              # plain `drawio` binary on PATH. scripts/drawio_xml_to_pdf.py
              # and `make edit` pick this up via the DRAWIO environment
              # variable.
              export DRAWIO="${pkgs.drawio}/Applications/draw.io.app/Contents/MacOS/draw.io"
            ''}
            alias m=make
            echo "LaTeX + draw.io env ready — run 'make help' to see all commands."
          '';
          packages =
            [
              pkgs.bashInteractive # This is a must
              pkgs.gnumake
              pkgs.gitMinimal # full pkgs.git drags in ~1.5 GB (perl, gui, ...)

              # LaTeX (see `texlive` above)
              texlive

              # draw.io for editing/exporting drawio/*.xml figures
              pkgs.drawio

              # PDF -> PNG tooling used by the scripts; .out so the shell
              # doesn't pull the dev output (cairo/glib headers, ~1.4 GB)
              pkgs.poppler-utils.out # pdftoppm

              # Helper scripts in scripts/ use only the stdlib; swap for
              # pkgs.python3 (or python3.withPackages) if you need more
              pkgs.python3Minimal
            ]
            ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
              # Headless draw.io export (no X server / CI); the export
              # script wraps drawio with xvfb-run when DISPLAY is unset.
              pkgs.xvfb-run
            ];
        };
      }
    );
}
