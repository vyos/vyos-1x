/* SPDX-License-Identifier: GPL-2.0 */

// Code thankfully copied from:
// https://medium.com/swlh/building-a-xdp-express-data-path-based-peering-router-20db4995da66

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/in.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <linux/udp.h>
#include <linux/socket.h>

#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

#include <stdint.h>

#ifndef XDP_ACTION_MAX
#define XDP_ACTION_MAX (XDP_REDIRECT + 1)
#endif

#ifndef memcpy
#define memcpy(dest, src, n) __builtin_memcpy((dest), (src), (n))
#endif

#ifndef AF_INET
#define AF_INET 2
#endif

#ifndef AF_INET6
#define AF_INET6 10
#endif

#ifndef IPV6_FLOWINFO_MASK
#define IPV6_FLOWINFO_MASK bpf_htonl(0x0FFFFFFF)
#endif

/* This is the data record stored in the map */
struct datarec {
	__u64 rx_packets;
	__u64 rx_bytes;
};

/* Keeps stats per (enum) xdp_action */
struct bpf_map_def SEC("maps") xdp_stats_map = {
	.type        = BPF_MAP_TYPE_PERCPU_ARRAY,
	.key_size    = sizeof(__u32),
	.value_size  = sizeof(struct datarec),
	.max_entries = XDP_ACTION_MAX,
};

struct bpf_map_def SEC("maps") tx_port = {
	.type = BPF_MAP_TYPE_DEVMAP,
	.key_size = sizeof(int),
	.value_size = sizeof(int),
	.max_entries = 256,
};

/* from include/net/ip.h */
static __always_inline int ip_decrease_ttl(struct iphdr *iph)
{
	__u32 check = iph->check;
	check += bpf_htons(0x0100);
	iph->check = (__u16)(check + (check >= 0xFFFF));
	return --iph->ttl;
}

static __always_inline
__u32 xdp_stats_record_action(struct xdp_md *ctx, __u32 action)
{
	if (action >= XDP_ACTION_MAX)
		return XDP_ABORTED;

	/* Lookup in kernel BPF-side return pointer to actual data record */
	struct datarec *rec = bpf_map_lookup_elem(&xdp_stats_map, &action);
	if (!rec)
		return XDP_ABORTED;

	/* BPF_MAP_TYPE_PERCPU_ARRAY returns a data record specific to current
	 * CPU and XDP hooks runs under Softirq, which makes it safe to update
	 * without atomic operations.
	 */
	rec->rx_packets++;
	rec->rx_bytes += (ctx->data_end - ctx->data);

	return action;
}

/* xdp_router is the name of the xdp program */
SEC("prog")
int xdp_router_func(struct xdp_md *ctx)
{
	/* this is the packet context*/
	void *data_end = (void *)(long)ctx->data_end;
	void *data = (void *)(long)ctx->data;
	struct bpf_fib_lookup fib_params = {};
	struct ethhdr *eth = data;
	struct ipv6hdr *ip6h;
	struct iphdr *iph;
	__u16 h_proto;
	__u64 nh_off;
	int rc;
	/* default action is to pass */
	int action = XDP_PASS;

	nh_off = sizeof(*eth);
	if (data + nh_off > data_end) {
		action = XDP_DROP;
		goto out;
	}

	/* determine if this is IP4 or IPv6 by looking at the Ethernet protocol field */
	h_proto = eth->h_proto;
	if (h_proto == bpf_htons(ETH_P_IP)) {
		/* IPv4 part of the code */
		iph = data + nh_off;

		if (iph + 1 > data_end) {
			action = XDP_DROP;
			goto out;
		}
		/* as a real router, we need to check the TTL to prevent never ending loops*/
		if (iph->ttl <= 1)
			goto out;

		/* populate the fib_params fields to prepare for the lookup */
		fib_params.family	= AF_INET;
		fib_params.tos		= iph->tos;
		fib_params.l4_protocol	= iph->protocol;
		fib_params.sport	= 0;
		fib_params.dport	= 0;
		fib_params.tot_len	= bpf_ntohs(iph->tot_len);
		fib_params.ipv4_src	= iph->saddr;
		fib_params.ipv4_dst	= iph->daddr;
	} else if (h_proto == bpf_htons(ETH_P_IPV6)) {
		/* IPv6 part of the code */
		struct in6_addr *src = (struct in6_addr *) fib_params.ipv6_src;
		struct in6_addr *dst = (struct in6_addr *) fib_params.ipv6_dst;

		ip6h = data + nh_off;
		if (ip6h + 1 > data_end) {
			action = XDP_DROP;
			goto out;
		}
		/* as a real router, we need to check the TTL to prevent never ending loops*/
		if (ip6h->hop_limit <= 1)
			goto out;

		/* populate the fib_params fields to prepare for the lookup */
		fib_params.family	= AF_INET6;
		fib_params.flowinfo	= *(__be32 *) ip6h & IPV6_FLOWINFO_MASK;
		fib_params.l4_protocol	= ip6h->nexthdr;
		fib_params.sport	= 0;
		fib_params.dport	= 0;
		fib_params.tot_len	= bpf_ntohs(ip6h->payload_len);
		*src			= ip6h->saddr;
		*dst			= ip6h->daddr;
	} else {
		goto out;
	}

	fib_params.ifindex = ctx->ingress_ifindex;

	/* this is where the FIB lookup happens. If the lookup is successful */
	/* it will populate the fib_params.ifindex with the egress interface index */

	rc = bpf_fib_lookup(ctx, &fib_params, sizeof(fib_params), 0);
	switch (rc) {
	case BPF_FIB_LKUP_RET_SUCCESS:         /* lookup successful */
		   /* we are a router, so we need to decrease the ttl */
		if (h_proto == bpf_htons(ETH_P_IP))
			ip_decrease_ttl(iph);
		else if (h_proto == bpf_htons(ETH_P_IPV6))
			ip6h->hop_limit--;
		/* set the correct new source and destionation mac addresses */
		/* can be found in fib_params.dmac and fib_params.smac */
		memcpy(eth->h_dest, fib_params.dmac, ETH_ALEN);
		memcpy(eth->h_source, fib_params.smac, ETH_ALEN);
		/* and done, now we set the action to bpf_redirect_map with fib_params.ifindex which is the egress port as paramater */
		action = bpf_redirect_map(&tx_port, fib_params.ifindex, 0);
		break;
	case BPF_FIB_LKUP_RET_BLACKHOLE:    /* dest is blackholed; can be dropped */
	case BPF_FIB_LKUP_RET_UNREACHABLE:  /* dest is unreachable; can be dropped */
	case BPF_FIB_LKUP_RET_PROHIBIT:     /* dest not allowed; can be dropped */
		action = XDP_DROP;
		break;
	case BPF_FIB_LKUP_RET_NOT_FWDED:    /* packet is not forwarded */
	case BPF_FIB_LKUP_RET_FWD_DISABLED: /* fwding is not enabled on ingress */
	case BPF_FIB_LKUP_RET_UNSUPP_LWT:   /* fwd requires encapsulation */
	case BPF_FIB_LKUP_RET_NO_NEIGH:     /* no neighbor entry for nh */
	case BPF_FIB_LKUP_RET_FRAG_NEEDED:  /* fragmentation required to fwd */
		/* PASS */
		break;
	}

out:
	/* and done, update stats and return action */
	return xdp_stats_record_action(ctx, action);
}

char _license[] SEC("license") = "GPL";
