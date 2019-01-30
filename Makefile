TMPL_DIR := templates-cfg
OP_TMPL_DIR := templates-op

.PHONY: interface_definitions
.ONESHELL:
interface_definitions:
	mkdir -p $(TMPL_DIR)

	find $(CURDIR)/interface-definitions/ -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-templates {} $(CURDIR)/schema/interface_definition.rng $(TMPL_DIR) || exit 1

	# XXX: delete top level node.def's that now live in other packages
	rm -f $(TMPL_DIR)/interfaces/node.def
	rm -f $(TMPL_DIR)/protocols/node.def
	rm -f $(TMPL_DIR)/system/node.def
	rm -f $(TMPL_DIR)/system/options/node.def
	rm -f $(TMPL_DIR)/vpn/node.def
	rm -f $(TMPL_DIR)/vpn/ipsec/node.def

.PHONY: op_mode_definitions
.ONESHELL:
op_mode_definitions:
	mkdir -p $(OP_TMPL_DIR)

	find $(CURDIR)/op-mode-definitions/ -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-op-templates {} $(CURDIR)/schema/op-mode-definition.rng $(OP_TMPL_DIR) || exit 1

	# XXX: delete top level op mode node.def's that now live in other packages
	rm -f $(OP_TMPL_DIR)/clear/node.def
	rm -f $(OP_TMPL_DIR)/set/node.def
	rm -f $(OP_TMPL_DIR)/show/node.def
	rm -f $(OP_TMPL_DIR)/show/interfaces/node.def
	rm -f $(OP_TMPL_DIR)/show/ip/node.def
	rm -f $(OP_TMPL_DIR)/reset/node.def
	rm -f $(OP_TMPL_DIR)/restart/node.def
	rm -f $(OP_TMPL_DIR)/monitor/node.def
	rm -f $(OP_TMPL_DIR)/generate/node.def

.PHONY: all
all: clean interface_definitions op_mode_definitions

.PHONY: clean
clean:
	rm -rf $(TMPL_DIR)/*
	rm -rf $(OP_TMPL_DIR)/*

.PHONY: test
test:
	PYTHONPATH=python/ python3 -m "nose" --exe --with-xunit src --with-coverage --cover-erase --cover-xml --cover-package --cover-html src/conf_mode,src/op_mode,src/completion,src/helpers,src/validators,src/tests --verbose

.PHONY: sonar
sonar:
	sonar-scanner -X -Dsonar.login=${SONAR_TOKEN}

.PHONY: docs
.ONESHELL:
docs:
	sphinx-apidoc -o sphinx/source/  python/
	cd sphinx/
	PYTHONPATH=../python make html
