# nix-env

Reproducible Nix environment for writing LaTeX documents with draw.io figures.

Everything comes from the Nix dev shell — TeX Live (scheme-small + latexmk, biber, texcount, tikz, standalone and the other packages the repo uses), draw.io, Python 3, poppler (`pdftoppm`), git, make. No manual installations besides Nix itself.

If a document needs a LaTeX package that is not included, add it to the `texlive = pkgs.texliveSmall.withPackages (...)` list in `flake.nix` (e.g. `ps.pgfplots`) — package names can be found with `nix search nixpkgs texlivePackages.<name>`.

## Quick Start

```sh
nix develop    # enter the environment (everything is provided)
make           # export changed drawio figures + build main.pdf
make help      # see all available commands
```

`make` is incremental: a figure is only re-exported when its `drawio/*.xml` changed since the last build. Inside the dev shell, `m` is an alias for `make`.

## Layout

| Directory | Purpose |
| --- | --- |
| `latex/` | `.tex` sources; `latex/main.tex` is the document entry point |
| `drawio/` | draw.io `.xml` figure sources (files start and end with `mxGraphModel`) |
| `figures/` | generated figure PDFs (from `drawio/`) or any other PDFs/images you add |
| `figures-png/` | PNG exports of the figure PDFs / tables |
| `scripts/` | Python helper scripts (drawio→pdf, pdf→png, table→png, svg→drawio) |

## Requirements

* ~2 GB of free space (first `nix develop` downloads about 1.7 GB)

## Install Nix (once)

* On Ubuntu 22/24 LTS:
  * `sudo apt install curl git`
  * `sh <(curl -L https://nixos.org/nix/install) --daemon`
    * Yes to all. Give sudo permissions if asked.
    * Check for errors/warnings during installation.
  * Create a config file for nix:
    * ```mkdir -p $HOME/.config/nix && touch $HOME/.config/nix/nix.conf && echo -e "\n# Added by script\nexperimental-features = nix-command flakes\nmax-jobs = auto\nuse-xdg-base-directories = true" | tee -a $HOME/.config/nix/nix.conf```
  * Reboot: `reboot`
* On macOS:
  * `sh <(curl -L https://nixos.org/nix/install)`
  * Create the same nix config file as above.
  * Restart the terminal.
* Check that nix works:
  * `nix-shell -p nix-info --run "nix-info -m"`

## Activate Environment

```sh
git clone https://github.com/celuk/nix-env
cd nix-env
nix develop
```

* The first time it will download ~1.7 GB of packages and write a fresh `flake.lock` (commit it to pin the environment).
* Optional: with [direnv](https://direnv.net/) installed, `direnv allow` auto-enters the shell on `cd`.

## Build the Document

```sh
make               # export changed drawio figures, then build main.pdf
```

That single command does everything: any `drawio/*.xml` newer than its `figures/*.pdf` is re-exported first, then `latex/main.tex` is compiled to `main.pdf` at the repo root.

A dummy example is included: `latex/main.tex` plus `drawio/example.xml`, so a fresh clone builds out of the box.

## Make Targets

Run `make help` for this list in the terminal.

### Document

| Target | What it does |
| --- | --- |
| `make` / `make all` | Export changed figures and compile `latex/main.tex` to `main.pdf` |
| `make watch` | Recompile automatically on every save (`latexmk -pvc`) |
| `make view` | Build and open `main.pdf` in the default viewer |
| `make count` | Word count of the document (texcount) |

### Figures

| Target | What it does |
| --- | --- |
| `make figs` | Export only the drawio figures whose XML changed |
| `make xp <name>` | Export `drawio/<name>.xml` to `figures/<name>.pdf` |
| `make xps` | Force re-export of all `drawio/*.xml` |
| `make new <name>` | Create a blank `drawio/<name>.xml` from a template |
| `make edit <name>` | Open `drawio/<name>.xml` in the draw.io editor |

### PNG export

| Target | What it does |
| --- | --- |
| `make pdf2png <name>` | Convert `figures/<name>.pdf` to `figures-png/<name>.png` |
| `make pdfs2png` | Convert all `figures/*.pdf` to PNGs (`PNG_DPI=600` by default) |
| `make tables2png` | Render every LaTeX table in `latex/*.tex` as a standalone PNG |
| `make fixfigs` | Re-encode `figures/*.png` with sips (macOS only) |

### Git shortcuts

| Target | What it does |
| --- | --- |
| `make up` | `git pull`, `git add .`, commit (skipped if no changes), `git push` |
| `make up MSG="fix typo"` | Same, but with a custom commit message |
| `make st` | Short git status |
| `make pull` / `make push` | Plain `git pull` / `git push` |

### Cleaning

| Target | What it does |
| --- | --- |
| `make clean` | Remove latexmk auxiliary files |
| `make distclean` | Also remove the generated PDF and bib leftovers |
| `make cleanfigs` | Remove figure PDFs generated from `drawio/` and all PNGs |
| `make cleanall` | Remove everything generated |

`PNG_DPI` can be overridden, e.g. `make pdfs2png PNG_DPI=300`.

## Scripts

* `scripts/drawio_xml_to_pdf.py` — exports a draw.io XML to a cropped, selectable (vector text) PDF. Finds draw.io via the `DRAWIO` env var (set by the nix shell on macOS), `drawio` on PATH, or the macOS app bundle. On Linux without a display it automatically runs under `xvfb-run`.
* `scripts/pdf_to_png.py` — rasterizes one PDF to PNG via `pdftoppm` (falls back to `sips` on macOS).
* `scripts/latex_table_to_png.py` — extracts `table` environments from a `.tex` file and renders each as a standalone PNG.
* `scripts/svg_to_drawio_xml.py` — wraps an SVG into a draw.io `mxGraphModel` XML so it can be edited/placed in draw.io.

## Editing Figures

The typical figure workflow, all inside the dev shell:

```sh
make new mydiagram    # create a blank drawio/mydiagram.xml
make edit mydiagram   # draw it in the draw.io editor, save
make                  # re-export changed figures + rebuild the document
```

`make edit` finds draw.io automatically (the `DRAWIO` env var set by the nix shell on macOS, `drawio` on PATH, or the macOS app bundle). On macOS it is launched with `--use-mock-keychain` so the nix-built (ad-hoc signed) app never triggers the Keychain access prompt; on Linux `--password-store=basic` avoids the equivalent keyring prompt.
