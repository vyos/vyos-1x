#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/in.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <linux/udp.h>

#include <stdint.h>

/* IP flags. */
#define IP_CE     0x8000    /* Flag: "Congestion"     */
#define IP_DF     0x4000    /* Flag: "Don't Fragment" */
#define IP_MF     0x2000    /* Flag: "More Fragments" */
#define IP_OFFSET 0x1FFF    /* "Fragment Offset" part */

#define SEC(NAME) __attribute__((section(NAME), used))

#define htons(x) ((__be16)___constant_swab16((x)))
#define htonl(x) ((__be32)___constant_swab32((x)))

struct vlan_hdr {
  __be16 h_vlan_TCI;
  __be16 h_vlan_encapsulated_proto;
};

SEC("prog")
int xdp_drop(struct xdp_md *ctx) {
  void *data_end = (void *)(long)ctx->data_end;
  void *data = (void *)(long)ctx->data;
  struct ethhdr *eth = data;

  uint64_t nh_off = sizeof(*eth);
  if (data + nh_off > data_end) {
    return XDP_PASS;
  }

  uint16_t h_proto = eth->h_proto;
  int i;

  /* Handle double VLAN tagged packet. See https://en.wikipedia.org/wiki/IEEE_802.1ad */
  for (i = 0; i < 2; i++) {
    if (h_proto == htons(ETH_P_8021Q) || h_proto == htons(ETH_P_8021AD)) {
      struct vlan_hdr *vhdr;

      vhdr = data + nh_off;
      nh_off += sizeof(struct vlan_hdr);
      if (data + nh_off > data_end) {
        return XDP_PASS;
      }
      h_proto = vhdr->h_vlan_encapsulated_proto;
    }
  }

  if (h_proto == htons(ETH_P_IP)) {
    struct iphdr *iph = data + nh_off;
    struct udphdr *udph = data + nh_off + sizeof(struct iphdr);

    uint32_t hostid = iph->daddr >> 24;

    if (udph + 1 > (struct udphdr *)data_end) {
      return XDP_PASS;
    }
    if (hostid == 0 || hostid == 255) {
      return XDP_DROP;
    }
    if (iph->frag_off & htons(IP_MF | IP_OFFSET)) {
      return XDP_DROP;
    }
    if (iph->protocol == IPPROTO_UDP) {
      __be16 dport = htons(udph->dest);
      __be16 sport = htons(udph->source);

      if (dport == 53 || sport == 53) {
        return XDP_DROP;
      }
    }
  } else if (h_proto == htons(ETH_P_IPV6)) {
    struct ipv6hdr *ip6h = data + nh_off;
    struct udphdr *udph = data + nh_off + sizeof(struct ipv6hdr);

    if (udph + 1 > (struct udphdr *)data_end) {
      return XDP_PASS;
    }
    if (ip6h->nexthdr == IPPROTO_UDP) {
      __be16 dport = htons(udph->dest);
      __be16 sport = htons(udph->source);

      if (dport == 53 || sport == 53) {
        return XDP_DROP;
      }
    }
  }

  return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
