#!/bin/bash

debug=false
regexes=()
execes=()
value=

while [[ $# -gt 0 ]]; do
	case "$1" in
		--regex)
			regexes+=("$2")
			;;
		--exec)
			execes+=("$2")
			;;
		--value)
			value="$2"
			;;
		--debug)
			debug=true
			;;
	esac
	shift
done

for re in "${regexes[@]}"; do
	echo "$value" | grep -Px -e "$re" - 2>&1 >/dev/null
	case $? in
		0)
			exit 0
			;;
		2)
			$debug && echo "error in regex \"$re\" value \"$value\""
			;;
	esac
done

for ex in "${execes[@]}"; do
	$debug && echo "$ex $value"
	eval "$ex" "$value"
	e=$?
	case $e in
		0)
			exit 0
			;;
		*)
			$debug && echo "exit status $e"
			;;
	esac
done

exit 1
