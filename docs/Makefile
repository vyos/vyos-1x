# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = VyOS
SOURCEDIR     = .
BUILDDIR      = _build

AUTOHOST      = 0.0.0.0
AUTOPORT      = 8000
AUTOOPTS      = --watch .

SWAP          = python3 ../scripts/swap_sources.py

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile swap restore html dirhtml pdf livehtml defaultvalue

swap:
	$(SWAP) --swap

restore:
	$(SWAP) --restore

html: swap
	@trap '$(SWAP) --restore' EXIT; \
		$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

dirhtml: swap
	@trap '$(SWAP) --restore' EXIT; \
		$(SPHINXBUILD) -M dirhtml "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

pdf: swap
	@trap '$(SWAP) --restore' EXIT; \
		$(SPHINXBUILD) -M latexpdf "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

livehtml: swap
	@trap '$(SWAP) --restore' EXIT; \
		sphinx-autobuild --host $(AUTOHOST) --port $(AUTOPORT) \
		--ignore '*/_build/*' \
		--ignore '*/md-*' \
		"$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

defaultvalue: export VYOS_DEFAULT=True
defaultvalue: html

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
