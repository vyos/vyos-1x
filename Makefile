.PHONY: all

all:
	# Install is just xcopy

deb:
	dpkg-buildpackage -uc -us -tc -b
