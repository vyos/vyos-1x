TMPL_DIR := templates-cfg
OP_TMPL_DIR := templates-op
BUILD_DIR := build
DATA_DIR := data
SHIM_DIR := src/shim
XDP_DIR := src/xdp
LIBS := -lzmq
CFLAGS :=

J2LINT := $(shell command -v j2lint 2> /dev/null)

config_xml_src = $(wildcard interface-definitions/*.xml.in)
config_xml_obj = $(config_xml_src:.xml.in=.xml)
op_xml_src = $(wildcard op-mode-definitions/*.xml.in)
op_xml_obj = $(op_xml_src:.xml.in=.xml)

%.xml: %.xml.in
	@echo Generating $(BUILD_DIR)/$@ from $<
	mkdir -p $(BUILD_DIR)/$(dir $@)
	$(CURDIR)/scripts/transclude-template $< > $(BUILD_DIR)/$@

.PHONY: interface_definitions
.ONESHELL:
interface_definitions: $(config_xml_obj)
	mkdir -p $(TMPL_DIR)

	$(CURDIR)/scripts/override-default $(BUILD_DIR)/interface-definitions

	find $(BUILD_DIR)/interface-definitions -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-templates {} $(CURDIR)/schema/interface_definition.rng $(TMPL_DIR) || exit 1

	# XXX: delete top level node.def's that now live in other packages
	# IPSec VPN EAP-RADIUS does not support source-address
	rm -rf $(TMPL_DIR)/vpn/ipsec/remote-access/radius/source-address

	# T4284 neq QoS implementation is not yet live
	find $(TMPL_DIR)/interfaces -name redirect -type d -exec rm -rf {} \;
	rm -rf $(TMPL_DIR)/qos
	rm -rf $(TMPL_DIR)/interfaces/input

	# T2472 - EIGRP support
	rm -rf $(TMPL_DIR)/protocols/eigrp
	# T2773 - EIGRP support for VRF
	rm -rf $(TMPL_DIR)/vrf/name/node.tag/protocols/eigrp

	# XXX: test if there are empty node.def files - this is not allowed as these
	# could mask help strings or mandatory priority statements
	find $(TMPL_DIR) -name node.def -type f -empty -exec false {} + || sh -c 'echo "There are empty node.def files! Check your interface definitions." && exit 1'

.PHONY: op_mode_definitions
.ONESHELL:
op_mode_definitions: $(op_xml_obj)
	mkdir -p $(OP_TMPL_DIR)

	find $(BUILD_DIR)/op-mode-definitions/ -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-op-templates {} $(CURDIR)/schema/op-mode-definition.rng $(OP_TMPL_DIR) || exit 1

	# XXX: delete top level op mode node.def's that now live in other packages
	rm -f $(OP_TMPL_DIR)/add/node.def
	rm -f $(OP_TMPL_DIR)/clear/interfaces/node.def
	rm -f $(OP_TMPL_DIR)/clear/node.def
	rm -f $(OP_TMPL_DIR)/delete/node.def
	rm -f $(OP_TMPL_DIR)/generate/node.def
	rm -f $(OP_TMPL_DIR)/monitor/node.def
	rm -f $(OP_TMPL_DIR)/set/node.def
	rm -f $(OP_TMPL_DIR)/show/interfaces/node.def
	rm -f $(OP_TMPL_DIR)/show/node.def
	rm -f $(OP_TMPL_DIR)/show/system/node.def

	# XXX: ping and traceroute must be able to recursivly call itself as the
	# options are provided from the script itself
	ln -s ../node.tag $(OP_TMPL_DIR)/ping/node.tag/node.tag/
	ln -s ../node.tag $(OP_TMPL_DIR)/traceroute/node.tag/node.tag/

	# XXX: test if there are empty node.def files - this is not allowed as these
	# could mask help strings or mandatory priority statements
	find $(OP_TMPL_DIR) -name node.def -type f -empty -exec false {} + || sh -c 'echo "There are empty node.def files! Check your interface definitions." && exit 1'

.PHONY: vyshim
vyshim:
	$(MAKE) -C $(SHIM_DIR)

.PHONY: vyxdp
vyxdp:
	$(MAKE) -C $(XDP_DIR)

.PHONY: all
all: clean interface_definitions op_mode_definitions check test j2lint vyshim

.PHONY: check
.ONESHELL:
check:
	@echo "Checking which CLI scripts are not enabled to work with vyos-configd..."
	@for file in `ls src/conf_mode -I__pycache__`
	do
		if ! grep -q $$file data/configd-include.json; then
			echo "* $$file"
		fi
	done

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(TMPL_DIR)
	rm -rf $(OP_TMPL_DIR)
	$(MAKE) -C $(SHIM_DIR) clean
	$(MAKE) -C $(XDP_DIR) clean

.PHONY: test
test:
	set -e; python3 -m compileall -q -x '/vmware-tools/scripts/, /ppp/' .
	PYTHONPATH=python/ python3 -m "nose" --with-xunit src --with-coverage --cover-erase --cover-xml --cover-package src/conf_mode,src/op_mode,src/completion,src/helpers,src/validators,src/tests --verbose

.PHONY: j2lint
j2lint:
ifndef J2LINT
	$(error "j2lint binary not found, consider installing: pip install git+https://github.com/aristanetworks/j2lint.git@341b5d5db86")
endif
	$(J2LINT) data/

.PHONY: sonar
sonar:
	sonar-scanner -X -Dsonar.login=${SONAR_TOKEN}

.PHONY: docs
.ONESHELL:
docs:
	sphinx-apidoc -o sphinx/source/  python/
	cd sphinx/
	PYTHONPATH=../python make html

deb:
	dpkg-buildpackage -uc -us -tc -b

.PHONY: schema
schema:
	trang -I rnc -O rng schema/interface_definition.rnc schema/interface_definition.rng
	trang -I rnc -O rng schema/op-mode-definition.rnc schema/op-mode-definition.rng
