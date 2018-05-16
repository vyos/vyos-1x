TMPL_DIR := templates-cfg
OP_TMPL_DIR := templates-op

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

.PHONY: op_mode_definitions
.ONESHELL:
op_mode_definitions:
	mkdir -p $(OP_TMPL_DIR)

	find $(CURDIR)/op-mode-definitions/ -type f | xargs -I {} $(CURDIR)/scripts/build-command-op-templates {} $(CURDIR)/schema/op-mode-definition.rng $(OP_TMPL_DIR)

	# XXX: delete top level op mode node.def's that now live in other packages
	rm -f $(OP_TMPL_DIR)/show/node.def
	rm -f $(OP_TMPL_DIR)/show/dns/node.def
	rm -f $(OP_TMPL_DIR)/reset/node.def
	rm -f $(OP_TMPL_DIR)/restart/node.def
	rm -f $(OP_TMPL_DIR)/monitor/node.def

.PHONY: all
all: interface_definitions op_mode_definitions

.PHONY: clean
clean:
	rm -rf $(TMPL_DIR)/*
	rm -rf $(OP_TMPL_DIR)/*

.PHONY: test
test:
	python3 -m "nose" --with-xunit src --with-coverage --cover-erase --cover-xml --cover-package src/conf_mode,src/op_mode --verbose

.PHONY: sonar
sonar:
	sonar-scanner -X -Dsonar.login=${SONAR_TOKEN}
