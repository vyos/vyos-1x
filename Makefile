TMPL_DIR := templates-cfg
OP_TMPL_DIR := templates-op
BUILD_DIR := build
DATA_DIR := data
SHIM_DIR := src/shim
CC := gcc
LIBS := -lzmq
CFLAGS :=

src = $(wildcard interface-definitions/*.xml.in)
obj = $(src:.xml.in=.xml)

%.xml: %.xml.in
	@echo Generating $(BUILD_DIR)/$@ from $<
	# -ansi      This turns off certain features of GCC that are incompatible
	#            with ISO C90. Without this regexes containing '/' as in an URL
	#            won't work
	# -x c       By default GCC guesses the input language from its file extension,
	#            thus XML is unknown. Force it to C language
	# -E         Stop after the preprocessing stage
	# -undef     Do not predefine any system-specific or GCC-specific macros.
	# -nostdinc  Do not search the standard system directories for header files
	# -P         Inhibit generation of linemarkers in the output from the
	#            preprocessor
	@$(CC) -x c-header -E -undef -nostdinc -P -I$(CURDIR)/interface-definitions -o $(BUILD_DIR)/$@ -c $<

$(BUILD_DIR):
	install -d -m 0755 $(BUILD_DIR)/interface-definitions
	install -d -m 0755 $(BUILD_DIR)/op-mode-definitions

.PHONY: interface_definitions
.ONESHELL:
interface_definitions: $(BUILD_DIR) $(obj)
	mkdir -p $(TMPL_DIR)

	find $(BUILD_DIR)/interface-definitions -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-templates {} $(CURDIR)/schema/interface_definition.rng $(TMPL_DIR) || exit 1

	# XXX: delete top level node.def's that now live in other packages
	rm -f $(TMPL_DIR)/firewall/node.def
	rm -f $(TMPL_DIR)/interfaces/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/vif/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/vif/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/vif-s/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/bonding/node.tag/vif-s/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/bridge/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/bridge/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif-s/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif-s/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif-s/node.tag/vif-c/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/ethernet/node.tag/vif-s/node.tag/vif-c/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/l2tpv3/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/l2tpv3/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/openvpn/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/pppoe/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/pppoe/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif-s/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif-s/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif-s/node.tag/vif-c/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/pseudo-ethernet/node.tag/vif-s/node.tag/vif-c/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/tunnel/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/tunnel/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/vxlan/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/vxlan/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/wireless/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/wireless/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/wireless/node.tag/vif/node.tag/ip/node.def
	rm -f $(TMPL_DIR)/interfaces/wireless/node.tag/vif/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/wirelessmodem/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/interfaces/wireguard/node.tag/ipv6/node.def
	rm -f $(TMPL_DIR)/protocols/node.def
	rm -rf $(TMPL_DIR)/protocols/nbgp
	rm -rf $(TMPL_DIR)/protocols/isis
	rm -f $(TMPL_DIR)/protocols/static/node.def
	rm -f $(TMPL_DIR)/system/node.def
	rm -f $(TMPL_DIR)/vpn/node.def
	rm -f $(TMPL_DIR)/vpn/ipsec/node.def

.PHONY: op_mode_definitions
.ONESHELL:
op_mode_definitions:
	mkdir -p $(OP_TMPL_DIR)

	find $(CURDIR)/op-mode-definitions/ -type f -name "*.xml" | xargs -I {} $(CURDIR)/scripts/build-command-op-templates {} $(CURDIR)/schema/op-mode-definition.rng $(OP_TMPL_DIR) || exit 1

	# XXX: delete top level op mode node.def's that now live in other packages
	rm -f $(OP_TMPL_DIR)/add/node.def
	rm -f $(OP_TMPL_DIR)/clear/node.def
	rm -f $(OP_TMPL_DIR)/clear/interfaces/node.def
	rm -f $(OP_TMPL_DIR)/set/node.def
	rm -f $(OP_TMPL_DIR)/show/node.def
	rm -f $(OP_TMPL_DIR)/show/interfaces/node.def
	rm -f $(OP_TMPL_DIR)/show/ipv6/node.def
	rm -f $(OP_TMPL_DIR)/show/ipv6/bgp/node.def
	rm -f $(OP_TMPL_DIR)/show/ipv6/route/node.def
	rm -f $(OP_TMPL_DIR)/restart/node.def
	rm -f $(OP_TMPL_DIR)/monitor/node.def
	rm -f $(OP_TMPL_DIR)/generate/node.def
	rm -f $(OP_TMPL_DIR)/show/system/node.def
	rm -f $(OP_TMPL_DIR)/show/vpn/node.def
	rm -f $(OP_TMPL_DIR)/delete/node.def
	rm -f $(OP_TMPL_DIR)/reset/vpn/node.def

	# XXX: ping must be able to recursivly call itself as the
	# options are provided from the script itself
	ln -s ../node.tag $(OP_TMPL_DIR)/ping/node.tag/node.tag/

.PHONY: component_versions
.ONESHELL:
component_versions: $(BUILD_DIR) $(obj)
	$(CURDIR)/scripts/build-component-versions $(BUILD_DIR)/interface-definitions $(DATA_DIR)

.PHONY: vyshim
vyshim:
	$(MAKE) -C $(SHIM_DIR)

.PHONY: all
all: clean interface_definitions op_mode_definitions component_versions vyshim

.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(TMPL_DIR)
	rm -rf $(OP_TMPL_DIR)
	$(MAKE) -C $(SHIM_DIR) clean

.PHONY: test
test:
	set -e; python3 -m compileall -q .
	PYTHONPATH=python/ python3 -m "nose" --with-xunit src --with-coverage --cover-erase --cover-xml --cover-package src/conf_mode,src/op_mode,src/completion,src/helpers,src/validators,src/tests --verbose

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
