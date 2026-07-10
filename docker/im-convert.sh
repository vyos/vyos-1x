#!/bin/bash
# Wrapper invoked by sphinx.ext.imgconverter as the `image_converter` command
# (docs/conf.py sets image_converter = 'im-convert').
#
# Sphinx calls it as: im-convert "<src>[0]" "<dst>" (the "[0]" frame-index
# suffix is ImageMagick syntax for "first frame/page", appended unconditionally
# by sphinx/ext/imgconverter.py).
#
# Debian's `imagemagick` package is built --without-rsvg (LGPL licensing), so
# its own SVG coder is a minimal libxml2-based renderer rather than a wrapper
# around librsvg. That built-in coder cannot handle SVGs with an embedded
# base64-encoded raster <image> element (common in diagrams exported from
# draw.io/diagrams.net): it fails with
#   "convert-im6.q16: unable to open image `image/png;base64,...'"
# because it tries to open the data-URI payload as if it were a file path.
# `rsvg-convert` (from librsvg2-bin) handles the same file correctly.
#
# Route .svg sources through rsvg-convert directly; everything else (webp,
# gif, pdf, ...) goes through ImageMagick's `convert` as before — webp support
# is compiled into this ImageMagick build, so that path needs no delegate.
#
# Output size is constrained: the docs pipeline's per-file size gate
# (scripts/docs_gates/gates.py) enforces the Cloudflare Workers 25 MiB
# asset cap on the built PDF, and naive full-resolution truecolor PNG
# conversion inflates it to ~183 MiB (the ~170 source .webp files are
# lossy-compressed; decoded to truecolor PNG they explode ~6x). The raster
# policy below (cap at 1000px on the long edge — only shrinking, never
# enlarging — plus non-dithered 128-color palette quantization and max PNG
# compression) brings the summed image payload to ~10 MiB (~15 MiB final
# PDF). Sphinx's imgconverter fixes the destination extension to .png (from
# the conversion rule's target mimetype) and pdflatex picks its decoder by
# extension, so switching photographic sources to JPEG is not available
# here — resolution + palette are the levers. 1000px at the PDF's ~6.3in
# text width is ~158 dpi; spot-checked legible on screenshots, diagrams,
# and photos alike.
set -euo pipefail

# sphinx.ext.imgconverter's is_available() probes the converter with a
# single-arg call (`im-convert -version`) before ever doing a real
# conversion. Delegate straight to ImageMagick's own -version so the probe
# succeeds — is_available()'s result is cached at the class level for the
# whole build, so a failed probe here silently disables ALL conversion
# (webp included), not just SVG.
if [ "$#" -lt 2 ]; then
    exec convert "$@"
fi

src=$1
dst=$2

# Strip ImageMagick's trailing frame-index suffix, e.g.
# "/path/to/file.svg[0]" -> "/path/to/file.svg".
plain_src=${src%\[*\]}

case "$plain_src" in
    *.svg|*.SVG)
        exec rsvg-convert -o "$dst" "$plain_src"
        ;;
    *)
        # See the size-cap rationale in the header comment. `1000x1000>`
        # only shrinks images larger than 1000px on either edge; `+dither`
        # disables dithering (IM6 semantics: -dither enables, +dither
        # disables), which quantizes flat UI colors cleanly AND compresses
        # far better than dithered output; `-quality 95` for PNG means
        # zlib level 9 + adaptive row filtering.
        exec convert "$src" -resize '1000x1000>' -strip +dither -colors 128 -quality 95 "$dst"
        ;;
esac
