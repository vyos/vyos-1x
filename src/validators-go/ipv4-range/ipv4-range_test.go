package main

import (
	"net/netip"
	"testing"
)

var (
	addr = "192.0.2.1"
)

func TestParseIP(t *testing.T) {
	parsed_1 := ParseIP(addr)
	parsed_2, _ := netip.ParseAddr(addr)

	if parsed_1 != parsed_2 {
		t.Errorf("Parsing test error: %s is not equal to %s", parsed_1, parsed_2)
	}
}
