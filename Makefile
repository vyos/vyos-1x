TMPL_DIR := templates

.PHONY: interface_definitions
.ONESHELL:
interface_definitions:
	mkdir -p $(TMPL_DIR)

	find $(CURDIR)/interface-definitions/ -type f | xargs -I {} $(CURDIR)/scripts/build-command-templates {} $(CURDIR)/schema/interface_definition.rng $(TMPL_DIR)

	# XXX: delete top level node.def's that now live in other packages
	rm -f $(TMPL_DIR)/system/node.def
	rm -f $(TMPL_DIR)/service/node.def
	rm -f $(TMPL_DIR)/service/dns/node.def
	rm -f $(TMPL_DIR)/protocols/node.def

	# Workaround for special nodes that should not have "type: txt"
	sed -i '/^type: txt/d' $(TMPL_DIR)/service/dns/forwarding/listen-on/node.def
	sed -i '/^type: txt/d' $(TMPL_DIR)/service/dns/forwarding/system/node.def

.PHONY: all
all: interface_definitions

.PHONY: clean
clean:
	rm -rf $(TMPL_DIR)/*
