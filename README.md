vyos-smoketest
==============

This is a set of scripts and test data for sanity checking VyOS builds.

The main entry point is /usr/bin/vyos-smoketest

It will try to check for common things that break such as kernel modules not loading,
and print a test report.

It also comes with a huge reference config that has almost every feature set.
