BUILDDIR=_build
VPATH=$(BUILDDIR)
OCAMLDIR=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlopt -where)
$(shell mkdir -p $(BUILDDIR) $(BUILDDIR)/stub $(BUILDDIR)/lib $(BUILDDIR)/stub_generator $(BUILDDIR)/test $(BUILDDIR)/generated)
PACKAGES=vyos1x-config,vyconf.vyconfd-config,vyconf.vycall-client,re,ctypes.stubs,ctypes.foreign

GENERATOR_FILES=$(BUILDDIR)/lib/bindings.cmx \
                $(BUILDDIR)/stub_generator/generate.cmx

LIBFILES=$(BUILDDIR)/lib/bindings.cmx \
         $(BUILDDIR)/generated/vyosconfig_bindings.cmx  \
         $(BUILDDIR)/lib/apply_bindings.cmx  \
         $(BUILDDIR)/generated/vyosconfig.o

CAML_INIT=$(BUILDDIR)/stub/init.o
CAML_CTYPES:=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind query ctypes)
CAML_STDLIB:=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind ocamlc -config | awk '/^standard_library_default:/ {print $$2}')

# The files that we'll generate
GENERATED=$(BUILDDIR)/generated/vyosconfig.h \
          $(BUILDDIR)/generated/vyosconfig.c \
          $(BUILDDIR)/generated/vyosconfig_bindings.ml

OSTYPE:=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind ocamlc -config | awk '/^os_type:/ {print $$2}')
SYSTEM:=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind ocamlc -config | awk '/^system:/ {print $$2}')
EXTDLL:=$(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind ocamlc -config | awk '/^ext_dll:/ {print $$2}')

CC:= $(shell eval $$(opam env --root=/opt/opam --set-root); ocamlfind ocamlc -config | awk '/^bytecomp_c_compiler/ {for(i=2;i<=NF;i++) printf "%s " ,$$i}')

LIBNAME:=libvyosconfig.so.0

ifeq ($(OSTYPE),$(filter $(OSTYPE),Win32 Cygwin))
EXTEXE=.exe
else
EXTEXE=
endif

GENERATOR=$(BUILDDIR)/generate$(EXTEXE)

all: sharedlib

PHONY: depends
depends:
	sudo sh -c 'eval $$(opam env --root=/opt/opam --set-root) ;\
		opam pin add vyos1x-config https://github.com/vyos/vyos1x-config.git#6cae8dc757c436972485f6e9baa5f4adf8e5e300 -y ; \
		opam pin add vyconf https://github.com/vyos/vyconf.git#ee86cf713f45d3bcd735440f432b5b7b57a31ca8 -y'

sharedlib: depends $(BUILDDIR)/libvyosconfig$(EXTDLL)

ifeq ($(OSTYPE),$(filter $(OSTYPE),Win32 Cygwin))
$(BUILDDIR)/libvyosconfig$(EXTDLL): $(CAML_INIT) $(LIBFILES)
	ocamlfind opt -o $@ -linkpkg -output-obj -verbose -package $(PACKAGES) $^
else ifeq ($(SYSTEM),$(filter $(SYSTEM),macosx))
$(BUILDDIR)/libvyosconfig$(EXTDLL): $(CAML_INIT) $(LIBFILES)
	ocamlfind opt -o $@ -linkpkg -runtime-variant _pic -verbose -ccopt -dynamiclib -package $(PACKAGES) $^
else
$(BUILDDIR)/libvyosconfig$(EXTDLL): $(CAML_INIT) $(LIBFILES)
	eval $$(opam env --root=/opt/opam --set-root); ocamlfind opt -o $@ -linkpkg -output-obj -runtime-variant _pic -verbose -thread -package $(PACKAGES) -ccopt "-Wl,-soname,$(LIBNAME)" $^
endif

stubs: $(GENERATED)

$(BUILDDIR)/stub/%.o:
	eval $$(opam env --root=/opt/opam --set-root); ocamlc -g -c stub/init.c
	mv init.o $@

$(GENERATED): $(GENERATOR)
	$(GENERATOR) $(BUILDDIR)/generated

$(BUILDDIR)/%.o: %.c
	$(CC) -c -o $@ -fPIC -I $(CAML_CTYPES) -I $(CAML_STDLIB) -I $(OCAMLDIR) -I $(OCAMLDIR)/../ctypes $<

$(BUILDDIR)/%.cmx: %.ml
	eval $$(opam env --root=/opt/opam --set-root); ocamlfind opt -c -o $@ -I $(BUILDDIR)/generated -I $(BUILDDIR)/lib -thread -package $(PACKAGES) $<

$(GENERATOR): $(GENERATOR_FILES)
	eval $$(opam env --root=/opt/opam --set-root); ocamlfind opt -o $@ -I $(BUILDDIR)/lib -linkpkg -thread -package $(PACKAGES) $^

install: sharedlib
	@mkdir -p /usr/lib
	@cp $(BUILDDIR)/libvyosconfig$(EXTDLL) /usr/lib/$(LIBNAME)

clean:
	rm -rf $(BUILDDIR)
