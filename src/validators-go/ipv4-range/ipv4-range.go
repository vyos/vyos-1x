package main

import (
	"fmt"
	"net/netip"
	"os"
	"strings"
)

// Parse a string and raise an error if it is not an IPv4 address
func ParseIP(addr string) netip.Addr {
	netip_addr, err := netip.ParseAddr(addr)
	if err != nil {
		fmt.Printf("The argument cannot be parsed as an IP address: %s", err)
		os.Exit(1)
	}
	if !netip_addr.Is4() {
		fmt.Printf("The address is not an IPv4: %s", netip_addr)
		os.Exit(1)
	}
	return netip_addr
}

func main() {
	// Check arguments
	if len(os.Args) != 2 {
		fmt.Println("There must be one argument provided")
		os.Exit(1)
	}
	args := os.Args[1]

	iprange := strings.Split(args, "-")
	if len(iprange) < 2 {
		fmt.Println("An argument must contain an IPv4 range")
		os.Exit(1)
	}

	// Parse IP addresses
	ip_first := ParseIP(iprange[0])
	ip_second := ParseIP(iprange[1])

	// Check if a first is less than a second
	if !ip_first.Less(ip_second) {
		os.Exit(1)
	}

	// Exit normally
	os.Exit(0)
}
