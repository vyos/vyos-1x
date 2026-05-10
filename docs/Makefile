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

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile html dirhtml pdf livehtml defaultvalue

html:
	$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

dirhtml:
	$(SPHINXBUILD) -M dirhtml "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

pdf:
	$(SPHINXBUILD) -M latexpdf "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

livehtml:
	sphinx-autobuild --host $(AUTOHOST) --port $(AUTOPORT) \
		--ignore '$(BUILDDIR)/**' \
		--ignore '**/_build/**' \
		--ignore '**/_rst_legacy/**' \
		"$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

defaultvalue: export VYOS_DEFAULT=True
defaultvalue: html

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
