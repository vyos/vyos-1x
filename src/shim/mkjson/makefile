CFLAGS = -Wall -Os -I.
CC = gcc
AR = ar

#USE_ASPRINTF make flag can be used in order to encourage asprintf use inside the library
ifeq ($(USE_ASPRINTF),1)
CFLAGS += -D_GNU_SOURCE
endif

#Builds object and a static library file
all: clean force
	$(CC) $(CFLAGS) -c mkjson.c -o obj/mkjson.o
	$(AR) -cvq lib/libmkjson.a obj/mkjson.o
	$(AR) -t lib/libmkjson.a

#Normal cleanup
clean:
	-rm -rf obj
	-rm -rf lib

#Environment init
force:
	-mkdir obj
	-mkdir lib

#Build the example snippet
example: all
	gcc -o example examples/example.c -I. -Llib -lmkjson

	
