#!/usr/bin/perl
#
# Module: vyatta-nat-translate.pl
# 
# **** License ****
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
# 
# This code was originally developed by Vyatta, Inc.
# Portions created by Vyatta are Copyright (C) 2007 Vyatta, Inc.
# All Rights Reserved.
# 
# Author: Stig Thormodsrud
# Date: July 2008
# Description: Script to display nat translations
# 
# **** End License ****
#

use Getopt::Long;
use XML::Simple;
use Data::Dumper;
use POSIX;

use warnings;
use strict;

my $dump = 0;
my ($xml_file, $verbose, $proto, $stats, $ipaddr, $pipe);
my $type;
my $verbose_format = "%-20s %-18s %-20s %-18s\n";
my $format         = "%-20s %-20s %-4s  %-8s";

sub add_xml_root {
    my $xml = shift;

    $xml = '<data>' . $xml . '</data>';
    return $xml;
}


sub read_xml_file {
    my $file = shift;

    local($/, *FD);  # slurp mode
    open FD, "<", $file or die "Couldn't open $file\n";
    my $xml = <FD>;
    close FD;
    return $xml;
}

sub print_xml {
    my $data = shift;
    print Dumper($data); 
}

sub guess_snat_dnat {
    my ($src, $dst) = @_;

    if ($src->{original} eq $dst->{reply}) {
	return "dnat";
    }
    if ($dst->{original} eq $src->{reply}) {
	return "snat";
    }
    return "unkn";
}

sub nat_print_xml {
    my ($data, $type) = @_;

    my $flow = 0;

    my %flowh;
    while (1) {
	my $meta = 0;
	last if ! defined $data->{flow}[$flow];
	my $flow_ref = $data->{flow}[$flow];
	my $flow_type = $flow_ref->{type};
	my (%src, %dst, %sport, %dport, %proto);
	my (%packets, %bytes);
	my $timeout = undef;
	my $uses = undef;
	while (1) {
	    my $meta_ref = $flow_ref->{meta}[$meta];
	    last if ! defined $meta_ref;
	    my $dir = $meta_ref->{direction};
	    if ($dir eq 'original' or $dir eq 'reply') {
		my $l3_ref    = $meta_ref->{layer3}[0];
		my $l4_ref    = $meta_ref->{layer4}[0];
		my $count_ref = $meta_ref->{counters}[0];
		if (defined $l3_ref) {
		    $src{$dir} = $l3_ref->{src}[0];
		    $dst{$dir} = $l3_ref->{dst}[0];
		    if (defined $l4_ref) {
			$sport{$dir} = $l4_ref->{sport}[0];
			$dport{$dir} = $l4_ref->{dport}[0];
			$proto{$dir} = $l4_ref->{protoname};
		    }
		}
		if (defined $stats and defined $count_ref) {
		    $packets{$dir} = $count_ref->{packets}[0];
		    $bytes{$dir}   = $count_ref->{bytes}[0];
		}
	    } elsif ($dir eq 'independent') {
		$timeout = $meta_ref->{timeout}[0];
		$uses    = $meta_ref->{'use'}[0];
	    }
	    $meta++;
	}
	my ($proto, $in_src, $in_dst, $out_src, $out_dst);
	$proto    = $proto{original};
	$in_src   = "$src{original}";
	$in_src  .= ":$sport{original}" if defined $sport{original};
	$in_dst   = "$dst{original}";
	$in_dst  .= ":$dport{original}" if defined $dport{original};
	$out_src  = "$dst{reply}";
	$out_src .= ":$dport{reply}" if defined $dport{reply};
	$out_dst  = "$src{reply}";
	$out_dst .= ":$sport{reply}" if defined $sport{reply};
	if (defined $verbose) {
	    printf($verbose_format, $in_src, $in_dst, $out_src, $out_dst);
	}
#	if (! defined $type) {
#	    $type = guess_snat_dnat(\%src, \%dst);
#	}
	if (defined $type) {
	    my ($from, $to);
	    if ($type eq 'source') {
		$from = "$src{original}";
		$to   = "$dst{reply}";
		if (defined $sport{original} and defined $dport{reply}) {
		    if ($sport{original} ne $dport{reply}) {
			$from .= ":$sport{original}";
			$to   .= ":$dport{reply}";
		    }
		}
	    } else {
		$from = "$dst{original}";
		$to   = "$src{reply}";
		if (defined $dport{original} and defined $sport{reply}) {
		    if ($dport{original} ne $sport{reply}) {
			$from .= ":$dport{original}";
			$to   .= ":$sport{reply}";
		    }
		}
	    }
	    if (defined $verbose) {
		print "  $proto: $from ==> $to";
	    } else {
		my $timeout2 = "";
		if (defined $timeout) {
		    $timeout2 = $timeout;
		}
		printf($format, $from, $to, $proto, $timeout2);
		print " $flow_type" if defined $flow_type;
		print "\n";
	    }
	}
	if (defined $verbose) {
	    print "  timeout: $timeout" if defined $timeout;
	    print " use: $uses " if defined $uses;
	    print " type: $flow_type" if defined $flow_type;
	    print "\n";
	}
	if (defined $stats) {
	    foreach my $dir ('original', 'reply') {
		if (defined $packets{$dir}) {
                    printf("  %-8s: packets %s, bytes %s\n",
		           $dir, $packets{$dir}, $bytes{$dir});
		}
	    }
	}
	$flow++;
    }
    return $flow;
}


#
# main
#
GetOptions("verbose"  => \$verbose,
	   "proto=s"  => \$proto,
	   "file=s"   => \$xml_file,
	   "stats"    => \$stats,
	   "type=s"   => \$type,
	   "ipaddr=s" => \$ipaddr,
	   "pipe"     => \$pipe,
);

my $conntrack = '/usr/sbin/conntrack';
if  (! -f $conntrack) {
    die "Package [conntrack] not installed";
}

die "Must specify NAT type!" if !defined($type);
die "Unknown NAT type!" if (($type ne 'source') && ($type ne 'destination'));

my $xs = XML::Simple->new(ForceArray => 1, KeepRoot => 0);
my ($xml, $data);

# flush stdout after every write for pipe mode
$| = 1 if defined $pipe; 

if (defined $verbose) {
    printf($verbose_format, 'Pre-NAT src', 'Pre-NAT dst', 
	   'Post-NAT src', 'Post-NAT dst');
} else {
    printf($format, 'Pre-NAT', 'Post-NAT', 'Prot', 'Timeout');
    print " Type" if defined $pipe;
    print "\n";
}

if (defined $xml_file) {
    $xml = read_xml_file($xml_file);
    $data = $xs->XMLin($xml);
    if ($dump) {
	print_xml($data);
	exit;
    }
    nat_print_xml($data, 'snat');

} elsif (defined $pipe) {
    while ($xml = <STDIN>) {
	$xml =~ s/\<\?xml version=\"1\.0\" encoding=\"utf-8\"\?\>//;
	$xml =~ s/\<conntrack\>//;
	$xml = add_xml_root($xml);
	$data = $xs->XMLin($xml);
	nat_print_xml($data, $type);
    }
} else {
    if (defined $proto) {
	$proto = "-p $proto" 
    } else {
	$proto = "";
    }
    if ($type eq 'source') {
	my $ipopt = "";
	if (defined $ipaddr) {
	    $ipopt = "--orig-src $ipaddr";
	} 
	$xml = `sudo $conntrack -L -n $ipopt -o xml $proto 2>/dev/null`;
	chomp $xml;
	$data = undef;
	$data = $xs->XMLin($xml) if ! $xml eq '';
    }
    if ($type eq 'destination') {
	my $ipopt = "";
	if (defined $ipaddr) {
	    $ipopt = "--orig-dst $ipaddr";
	} 
	$xml = `sudo $conntrack -L -g $ipopt -o xml $proto 2>/dev/null`;
	chomp $xml;
	$data = undef;
	$data = $xs->XMLin($xml) if ! $xml eq '';
    }
    nat_print_xml($data, $type) if defined $data;
}

# end of file
