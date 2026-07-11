# Must be run with --privileged flag
# Recommended to run the container with a volume mapped
# in order to easy exprort images built to "external" world
FROM debian:12
LABEL authors="VyOS Maintainers <maintainers@vyos.io>"

ENV DEBIAN_FRONTEND noninteractive

# Standard shell should be bash not dash
RUN echo "dash dash/sh boolean false" | debconf-set-selections && \
    dpkg-reconfigure dash

RUN apt-get update && apt-get install -y \
    vim \
    nano \
    git \
    mc \
    make \
    python3-pip \
    latexmk \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-latex-extra \
    sudo \
    gosu \
    graphviz \
    curl \
    dos2unix

# PDF-build toolchain extras, installed with --no-install-recommends (Trivy
# DS-0029) on a separate line — the texlive line above deliberately keeps
# recommends, which carry font packages LaTeX needs:
# - imagemagick + librsvg2-bin: sphinx.ext.imgconverter via docker/im-convert.sh
# - poppler-utils: pdfinfo for the docs-build workflow's page-count validation
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    librsvg2-bin \
    poppler-utils

RUN pip3 install --break-system-packages \
    Sphinx \
    sphinx-rtd-theme \
    sphinx-autobuild \
    sphinx-notfound-page \
    lxml \
    myst-parser \
    sphinx_design \
    sphinx_llms_txt \
    sphinx_sitemap

# Cleanup
RUN rm -rf /var/lib/apt/lists/*

EXPOSE 8000

# Allow password-less 'sudo' for all users in group 'sudo'
RUN sed "s/^%sudo.*/%sudo\tALL=(ALL) NOPASSWD:ALL/g" -i /etc/sudoers

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# We need to convert the entrypoint with appropriate line endings, else
# there will be an error:
#     standard_init_linux.go:175: exec user process caused
#     "no such file or directory"
RUN dos2unix /usr/local/bin/entrypoint.sh

# sphinx.ext.imgconverter's `image_converter` command (docs/conf.py sets
# image_converter = 'im-convert'). Routes .svg sources to rsvg-convert
# directly, since Debian's imagemagick package is built --without-rsvg and
# its built-in SVG coder can't handle embedded base64 raster <image>
# elements. See docker/im-convert.sh for the full rationale.
COPY im-convert.sh /usr/local/bin/im-convert
RUN dos2unix /usr/local/bin/im-convert && chmod +x /usr/local/bin/im-convert

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
