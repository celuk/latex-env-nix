PROJECT = main
TEXDIR = latex
TEX = latexmk
# -g forces a full latexmk pass even when it thinks nothing changed;
# needed because figures guarded by \IfFileExists never enter latexmk's
# dependency list while missing, so their later appearance goes unnoticed.
TEXFLAGS = -pdf -f -g -interaction=nonstopmode -synctex=1
PNG_DPI ?= 600
MSG ?= update

DRAWIO_XML := $(wildcard drawio/*.xml)
DRAWIO_PDF := $(patsubst drawio/%.xml,figures/%.pdf,$(DRAWIO_XML))

.DEFAULT_GOAL := all

# Targets that take a free-form second word as their argument
# (e.g. `make xp example`): turn that word into a no-op goal.
ifneq ($(filter xp pdf2png edit new,$(MAKECMDGOALS)),)
ARG_NAME := $(word 2,$(MAKECMDGOALS))
ifneq ($(ARG_NAME),)
.PHONY: $(ARG_NAME)
$(ARG_NAME):
	@:
endif
endif

##@ Document

all: $(PROJECT).pdf ## Export changed figures and build main.pdf (default)

$(PROJECT).pdf: $(TEXDIR)/$(PROJECT).tex $(DRAWIO_PDF) FORCE
	$(TEX) $(TEXFLAGS) $(TEXDIR)/$(PROJECT).tex

watch: $(DRAWIO_PDF) ## Rebuild the PDF automatically on every save
	$(TEX) $(TEXFLAGS) -pvc $(TEXDIR)/$(PROJECT).tex

view: $(PROJECT).pdf ## Build and open main.pdf
	@case "$$(uname)" in \
		Darwin) open $(PROJECT).pdf ;; \
		*) xdg-open $(PROJECT).pdf ;; \
	esac

count: ## Word count of the document
	@texcount -inc -total $(TEXDIR)/$(PROJECT).tex

##@ Figures

# Incremental rule: a figure PDF is rebuilt only when its XML changed.
figures/%.pdf: drawio/%.xml
	python3 scripts/drawio_xml_to_pdf.py -d $< -o figures/

figs: $(DRAWIO_PDF) ## Export only the drawio figures whose XML changed

xp: ## Export one figure: make xp <name>
	@name="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$name" ]; then \
		echo "Usage: make xp <xml_name_without_extension>"; \
		exit 1; \
	fi; \
	python3 scripts/drawio_xml_to_pdf.py -d "drawio/$$name.xml" -o figures/

xps: ## Force re-export of all drawio figures
	@found=0; \
	for xml in drawio/*.xml; do \
		if [ ! -e "$$xml" ]; then \
			continue; \
		fi; \
		found=1; \
		python3 scripts/drawio_xml_to_pdf.py -d "$$xml" -o figures/; \
	done; \
	if [ $$found -eq 0 ]; then \
		echo "No XML files found in drawio/."; \
	fi

new: ## Create a blank drawio figure: make new <name>
	@name="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$name" ]; then \
		echo "Usage: make new <xml_name_without_extension>"; \
		exit 1; \
	fi; \
	if [ -e "drawio/$$name.xml" ]; then \
		echo "drawio/$$name.xml already exists."; \
		exit 1; \
	fi; \
	printf '%s\n' "$$DRAWIO_TEMPLATE" > "drawio/$$name.xml"; \
	echo "Created drawio/$$name.xml (edit it with: make edit $$name)"

edit: ## Open a figure in the draw.io editor: make edit <name>
	@name="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$name" ]; then \
		echo "Usage: make edit <xml_name_without_extension>"; \
		exit 1; \
	fi; \
	exe="$${DRAWIO:-}"; \
	if [ -z "$$exe" ]; then exe="$$(command -v drawio || true)"; fi; \
	if [ -z "$$exe" ] && [ -x "/Applications/draw.io.app/Contents/MacOS/draw.io" ]; then \
		exe="/Applications/draw.io.app/Contents/MacOS/draw.io"; \
	fi; \
	if [ -z "$$exe" ]; then \
		echo "draw.io not found. Enter the nix shell first: nix develop"; \
		exit 1; \
	fi; \
	case "$$(uname)" in \
		Darwin) flags="--use-mock-keychain" ;; \
		*) flags="--password-store=basic" ;; \
	esac; \
	"$$exe" $$flags "drawio/$$name.xml" >/dev/null 2>&1 &

##@ PNG export

pdf2png: ## Convert one figure PDF to PNG: make pdf2png <name>
	@name="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$name" ]; then \
		echo "Usage: make pdf2png <pdf_name_without_extension>"; \
		exit 1; \
	fi; \
	mkdir -p figures-png; \
	case "$$name" in \
		*.pdf) input_pdf="figures/$$name" ;; \
		*) input_pdf="figures/$$name.pdf" ;; \
	esac; \
	python3 scripts/pdf_to_png.py -i "$$input_pdf" -o figures-png/ --dpi "$(PNG_DPI)"

pdfs2png: ## Convert all figure PDFs to PNGs (PNG_DPI=600)
	@mkdir -p figures-png
	@found=0; \
	for pdf in figures/*.pdf; do \
		if [ ! -e "$$pdf" ]; then \
			continue; \
		fi; \
		found=1; \
		python3 scripts/pdf_to_png.py -i "$$pdf" -o figures-png/ --dpi "$(PNG_DPI)"; \
	done; \
	if [ $$found -eq 0 ]; then \
		echo "No PDF files found in figures/."; \
	fi

tables2png: ## Render every LaTeX table as a standalone PNG
	@mkdir -p figures-png/tables
	@found=0; \
	for tex in $(TEXDIR)/*.tex; do \
		if [ ! -e "$$tex" ]; then \
			continue; \
		fi; \
		found=1; \
		python3 scripts/latex_table_to_png.py -t "$$tex" -o figures-png/tables/ --dpi "$(PNG_DPI)"; \
	done; \
	if [ $$found -eq 0 ]; then \
		echo "No .tex files found in $(TEXDIR)/."; \
	fi

fixfigs: ## Re-encode figures/*.png with sips (macOS only)
	@for f in figures/*.png; do sips -s format png "$$f" --out "$${f%.png}_fixed.png" && mv "$${f%.png}_fixed.png" "$$f"; done;

##@ Git shortcuts

st: ## Short git status
	@git status -sb

pull: ## git pull
	git pull

push: ## git push
	git push

up: ## Pull, commit everything (MSG="update"), push
	git pull && git add . && \
	(git diff --cached --quiet && echo "Nothing to commit." || git commit -m "$(MSG)") && \
	git push

##@ Cleaning

clean: ## Remove latexmk auxiliary files
	$(TEX) -c $(TEXDIR)/$(PROJECT).tex

distclean: ## Also remove main.pdf and bib leftovers
	$(TEX) -C $(TEXDIR)/$(PROJECT).tex
	rm -f $(PROJECT)-blx.bib
	rm -f $(PROJECT).bbl
	rm -f $(PROJECT).run.xml
	rm -f $(PROJECT).loi
	rm -f $(PROJECT).synctex*

cleanfigs: ## Remove figure PDFs generated from drawio/ and all PNGs
	rm -f $(DRAWIO_PDF)
	rm -rf figures-png

cleanall: distclean cleanfigs ## Remove everything generated

##@ Aliases

allfigs: xps ## Same as xps
allwithfigs: allfigs all ## Force-export all figures, then build

##@ Help

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z0-9_%-]+:.*##/ {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

define DRAWIO_TEMPLATE
<mxGraphModel dx="1426" dy="827" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
  </root>
</mxGraphModel>
endef
export DRAWIO_TEMPLATE

FORCE:

.PHONY: all watch view count figs xp xps new edit pdf2png pdfs2png tables2png fixfigs st pull push up clean distclean cleanfigs cleanall help allfigs allwithfigs FORCE
