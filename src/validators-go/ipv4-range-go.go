package main

import (
    "net"
    "os"
    "strings"
    "math/big"
)

var (
    hosts = os.Args[1]
)


func IP4toInt(IPv4Address net.IP) int64 {
    IPv4Int := big.NewInt(0)
    IPv4Int.SetBytes(IPv4Address.To4())
    return IPv4Int.Int64()
}

func IsIPv4(ip string) bool {
    if net.ParseIP(ip) == nil {
        return false
    }
    return true
}

func main() {
    dash := strings.Contains(hosts, "-")
    if dash == false {
        os.Exit(1)
    }

    lines := strings.Split(hosts, "-")
    first, second := string(lines[0]), string(lines[1])

    dec_first := IP4toInt(net.ParseIP(first))
    dec_second := IP4toInt(net.ParseIP(second))

    if dec_first  >= dec_second  {
        os.Exit(1)
    }

    for _, host := range lines {
        if IsIPv4(host) == false {
            os.Exit(1)
        }
    }
}
