#!/bin/sh

# For lines like `aliases "foo";`, regex matches everything between the quotes
grep -oP '(?<=aliases ").+(?=";)' /run/conserver/conserver.cf