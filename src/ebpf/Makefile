#clang -target bpf -O2 -c xdp-drop-ebpf.c -o xdp-drop-ebpf.o

src = $(wildcard *.c)
obj = $(src:.c=.o)
CLANG = clang
CFLAGS = -Wall -Wno-unused-value -Wno-pointer-sign -Wno-compare-distinct-pointer-types -Werror -O2

%.o: %.c
	$(CLANG) -target bpf $(CFLAGS) -o $@ -c $<

.PHONY: all
all: $(obj)

.PHONY: clean
clean:
	rm -f *.o
