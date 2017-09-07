TMPL_DIR := templates

.PHONY: interface_definitions
.ONESHELL:
interface_definitions:
	find $(CURDIR)/interface-definitions/ -type f | xargs -I {} $(CURDIR)/scripts/build-command-templates {} $(CURDIR)/schema/interface_definition.rng $(TMPL_DIR)

.PHONY: all
all: interface_definitions

.PHONY: clean
clean:
	rm -rf $(TMPL_DIR)/*
