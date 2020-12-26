#!/usr/bin/perl
#
# Module: vyatta-sg-blacklist.pl
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
# Portions created by Vyatta are Copyright (C) 2008-2009 Vyatta, Inc.
# All Rights Reserved.
#
# Author: Stig Thormodsrud
# Date: October 2008
# Description: script to download/update free url blacklist.
#
# **** End License ****
#

use Getopt::Long;
use POSIX;
use IO::Prompt;
use Sys::Syslog qw(:standard :macros);
use File::Copy;
use Fcntl qw(:flock);
use base qw(Exporter);
use File::Basename;
use File::Compare;

use lib "/opt/vyatta/share/perl5";
use Vyatta::Config;
use Vyatta::File;

use warnings;
use strict;

#
# Default blacklist
#
# Below are some free blacklists we've tried:
#
# http://squidguard.mesd.k12.or.us/blacklists.tgz
# http://ftp.teledanmark.no/pub/www/proxy/squidguard/contrib/blacklists.tar.gz
# ftp://ftp.univ-tlse1.fr/pub/reseau/cache/squidguard_contrib/blacklists.tar.gz
#
# Note: the auto install/update assumes that the blacklist url is a tar gz
#       file with the blacklist categorys in a "blacklist" directory.  Some
#       of the commercially available blacklists are a cgi script instead, so
#       those blacklists will need a different install/update script.  Of
#       course they can be manually installed/updated.
#
my $blacklist_url = 'ftp://ftp.univ-tlse1.fr/pub/reseau/cache/squidguard_contrib/blacklists.tar.gz';

#squid globals
my $squid_init      = '/etc/init.d/squid';
my $squid_mime_type = '/usr/share/squid/mime.conf';

#squidGuard globals
my $urlfilter_data_dir            = '/opt/vyatta/etc/config/url-filtering';
my $squidguard_blacklist_db  = "$urlfilter_data_dir/squidguard/db";
my $squidguard_log_dir       = '/var/log/squid';
my $squidguard_blacklist_log = "$squidguard_log_dir/blacklist.log";
my $squidguard_safesearch    = "/opt/vyatta/etc/safesearch_rewrites";

#vyattaguard globals
my $vyattaguard = '/opt/vyatta/sbin/vg';

sub webproxy_get_global_data_dir {
    return $urlfilter_data_dir;
}

my $global_data_dir = webproxy_get_global_data_dir();


sub squid_get_mime {
    my @mime_types = ();
    open(my $FILE, "<", $squid_mime_type) or die "Error: read $!";
    my @lines = <$FILE>;
    close($FILE);
    foreach my $line (@lines) {
	next if $line =~ /^#/;         # skip comments
	if ($line =~ /^([\S]+)[\s]+([\S]+)[\s]+([\S]+)[\s]+([\S]+).*$/) {
	    my $type = $2;
	    push @mime_types, $type if $type =~ /\//;
	}
    }
    return @mime_types;
}

sub squidguard_is_configured {
    my $config = new Vyatta::Config;
    $config->setLevel('service webproxy url-filtering');
    # This checks the running config, so it is assumed
    # to be called from op mode.
    return 1 if $config->existsOrig('squidguard');
    return 0;
}

sub squidguard_get_blacklist_dir {
    return $squidguard_blacklist_db;
}

sub squidguard_get_blacklist_log {
    return $squidguard_blacklist_log;
}

sub squidguard_get_safesearch_rewrites {
    my @rewrites = ();
    open(my $FILE, "<", $squidguard_safesearch) or die "Error: read $!";
    my @lines = <$FILE>;
    close($FILE);
    chomp @lines;
    foreach my $line (@lines) {
	next if $line =~ /^#/;         # skip comments
        if ($line =~ /^s\@/) {
            push @rewrites, $line;
        }
    }
    return @rewrites;
}

sub squidguard_ec_get_categorys {
    my %cat_hash;

    die "Must enable vyattaguard" if ! squidguard_use_ec();
    die "Missing vyattaguard package\n" if ! -e $vyattaguard;
    exit 1 if ! -e "$urlfilter_data_dir/sitefilter/categories.txt";

    my @lines = `$vyattaguard list`;
    foreach my $line (@lines) {
        my ($id, $category) = split ':', $line;
        next if ! defined $category;
        chomp $category;
        $category =~ s/\s/\_/g;
        $category =~ s/\&/\_and\_/g;
        $cat_hash{$id} = $category;
    }
    return %cat_hash;
}

sub squidguard_ec_cat2name {
    my ($cat) = @_;

    my %cat_hash = squidguard_ec_get_categorys();
    return $cat_hash{$cat} if defined $cat_hash{$cat};
    return;
}

sub squidguard_ec_name2cat {
    my ($name) = @_;

    my %cat_hash = squidguard_ec_get_categorys();
    foreach my $key (keys (%cat_hash)) {
        if ($cat_hash{$key} eq $name) {
            return $key;
        }
    }
    return;
}

sub squidguard_use_ec {
    my $rc = system("cli-shell-api inSession");
    my ($exist_func, $value_func);
    if ($rc == 0) {
        $exist_func = 'exists';
        $value_func = 'returnValue';
    } else {
        $exist_func = 'existsOrig';
        $value_func = 'returnOrigValue';
    }
    my $config = new Vyatta::Config;
    $config->setLevel('service webproxy url-filtering squidguard');
    if ($config->$exist_func('vyattaguard')) {
        return if ! -e $vyattaguard;
        my $mode = $config->$value_func('vyattaguard mode');
        return $mode;
    }
    return;
}

sub squidguard_get_blacklists {

    my @blacklists = ();
    if (squidguard_use_ec()) {
        die "Missing vyattaguard package\n" if ! -e $vyattaguard;
        my %cat_hash = squidguard_ec_get_categorys();
        foreach my $key (keys (%cat_hash)) {
            next if ! defined $cat_hash{$key};
            push @blacklists, $cat_hash{$key};
        }
    } else {
        my $dir = $squidguard_blacklist_db;
        opendir(DIR, $dir) || die "can't opendir $dir: $!";
        my @dirs = readdir(DIR);
        closedir DIR;

        foreach my $file (@dirs) {
            next if $file eq '.';
            next if $file eq '..';
            if (-d "$dir/$file") {
                push @blacklists, $file;
            }
        }
    }
    @blacklists = sort(@blacklists);
    return @blacklists;
}

sub squidguard_generate_db {
    my ($interactive, $category, $group) = @_;

    my $db_dir   = squidguard_get_blacklist_dir();
    my $tmp_conf = "/tmp/sg.conf.$$";
    my $output   = "dbhome $db_dir\n";
    $output     .= squidguard_build_dest($category, 0, $group);
    $output     .= "\nacl {\n";
    $output     .= "\tdefault {\n";
    $output     .= "\t\tpass all\n";
    $output     .= "\t}\n}\n\n";
    webproxy_write_file($tmp_conf, $output);

    my $dir = "$db_dir/$category";
    if ( -l $dir) {
	print "Skip link for   [$category] -> [", readlink($dir), "]\n"
	    if $interactive;
	return;
    }
    foreach my $type ('domains', 'urls', 'expressions') {
	my $path = "$category/$type";
	my $file = "$db_dir/$path";
	if (-e $file and -s _) {  # check exists and non-zero
	    my $file_db = "$file.db";
	    if (! -e $file_db) {
		#
		# it appears that there is a bug in squidGuard that if
		# the db file doesn't exist then running with -C leaves
		# huge tmp files in /var/tmp.
		#
		system("touch $file.db");
		system("chown -R proxy.proxy $file.db > /dev/null 2>&1");
	    }
	    my $wc = `cat $file| wc -l`; chomp $wc;
	    print "Building DB for [$path] - $wc entries\n" if $interactive;
	    my $cmd = "\"squidGuard -d -c $tmp_conf -C $path\"";
	    system("su - proxy -c $cmd > /dev/null 2>&1");
	}
    }
    system("rm $tmp_conf");
}

sub squidguard_is_category_local {
    my ($category) = @_;

    my $db_dir = squidguard_get_blacklist_dir();
    my $local_file = "$db_dir/$category/local";
    return 1 if -e $local_file;
    return 0;
}

sub squidguard_is_blacklist_installed {
    if (squidguard_use_ec()) {
        if (-e "$urlfilter_data_dir/sitefilter/urldb") {
            return 1;
        }
    } else {
        my @blacklists = squidguard_get_blacklists();
        foreach my $category (@blacklists) {
            next if squidguard_is_category_local($category);
            return 1;
        }
    }
    return 0;
}

sub squidguard_get_blacklist_domains_urls_exps {
    my ($list) = shift;

    my $dir = $squidguard_blacklist_db;
    my ($domains, $urls, $exps) = undef;
    $domains = "$list/domains"     if -f "$dir/$list/domains" && -s _;
    $urls    = "$list/urls"        if -f "$dir/$list/urls" && -s _;
    $exps    = "$list/expressions" if -f "$dir/$list/expressions" && -s _;
    return ($domains, $urls, $exps);
}

sub squidguard_get_blacklist_files {
    my ($type, $category) = @_;

    my @lists = squidguard_get_blacklists();
    my @files = ();
    foreach my $list (@lists) {
	my ($domain, $url, $exp) = squidguard_get_blacklist_domains_urls_exps(
	    $list);
	if ($type eq 'domains') {
	    next if !defined $domain;
	    if (defined $category) {
		next if $domain ne "$category/domains";
	    }
	    $domain = "$squidguard_blacklist_db/$domain";
	    push @files, $domain;
	}
	if ($type eq 'urls') {
	    next if !defined $url;
	    if (defined $category) {
		next if $url ne "$category/urls";
	    }
	    $url = "$squidguard_blacklist_db/$url";
	    push @files, $url;
	}
	if ($type eq 'expressions') {
	    next if !defined $exp;
	    if (defined $category) {
		next if $url ne "$category/expressions";
	    }
	    $exp = "$squidguard_blacklist_db/$exp";
	    push @files, $exp;
	}

    }
    @files = sort(@files);
    return @files;
}

sub squidguard_get_log_files {
    open(my $LS, "-|", "ls $squidguard_log_dir/bl*.log* 2> /dev/null | sort -nr ");
    my @log_files = <$LS>;
    close $LS;
    chomp @log_files;
    return @log_files;
}

sub squidguard_build_dest {
    my ($category, $logging, $group, $ec) = @_;

    my $output = '';
    my ($domains, $urls, $exps);
    if (squidguard_is_category_local("$category-$group")) {
	($domains, $urls, $exps) = squidguard_get_blacklist_domains_urls_exps(
	    "$category-$group");
    } else {
	($domains, $urls, $exps) = squidguard_get_blacklist_domains_urls_exps(
	    $category);
    }

    my $ec_cat = undef;
    if  (defined $ec) {
        $ec_cat = squidguard_ec_name2cat($category);
    }

    $output  = "dest $category-$group {\n";
    $output .= "\tdomainlist     $domains\n" if defined $domains;
    $output .= "\turllist        $urls\n"    if defined $urls;
    $output .= "\texpressionlist $exps\n"    if defined $exps;
    $output .= "\teccategory     $ec_cat\n"  if defined $ec_cat;
    if ($logging) {
	my $log = basename($squidguard_blacklist_log);
	$output .= "\tlog            $log\n";
    }
    $output .= "}\n\n";
    return $output;
}

sub webproxy_read_file {
    my ($file) = @_;
    my @lines;
    if ( -e $file) {
	open(my $FILE, '<', $file) or die "Error: read $!";
	@lines = <$FILE>;
	close($FILE);
	chomp @lines;
    }
    return @lines;
}

sub is_same_as_file {
    my ($file, $value) = @_;

    return if ! -e $file;

    my $mem_file = '';
    open my $MF, '+<', \$mem_file or die "couldn't open memfile $!\n";
    print $MF $value;
    seek($MF, 0, 0);

    my $rc = compare($file, $MF);
    return 1 if $rc == 0;
    return;
}

sub webproxy_write_file {
    my ($file, $config) = @_;

    # Avoid unnecessary writes.  At boot the file will be the
    # regenerated with the same content.
    return if is_same_as_file($file, $config);

    open(my $fh, '>', $file) || die "Couldn't open $file - $!";
    print $fh $config;
    close $fh;
    return 1;
}

sub webproxy_append_file {
    my ($dst, $src) = @_;

    open(my $ih, '<', $src) || die "Couldn't open $src - $!";
    open(my $oh, '>>', $dst) || die "Couldn't open $dst - $!";
    for (<$ih>) {
        print $oh $_;
    }
    close($oh);
    close($ih);
    return 1;
}

sub webproxy_delete_local_entry {
    my ($file, $value) = @_;

    my $db_dir = squidguard_get_blacklist_dir();
    $file = "$db_dir/$file";
    my @lines = webproxy_read_file($file);
    my $config = '';
    foreach my $line (@lines) {
	$config .= "$line\n" if $line ne $value;
    }
    if ($config eq '') {
	unlink($file);
    } else {
	webproxy_write_file($file, $config);
    }
    return;
}

sub webproxy_delete_all_local {
    my $db_dir = squidguard_get_blacklist_dir();
    my @categorys = squidguard_get_blacklists();
    foreach my $category (@categorys) {
	if (squidguard_is_category_local($category)) {
	    system("rm -rf $db_dir/$category");
	}
    }
    return;
}

sub print_err {
    my ($interactive, $msg) = @_;
    if ($interactive) {
	print "$msg\n";
    } else {
	syslog(LOG_ERR, $msg);
    }
}

sub squidguard_count_blacklist_entries {
    my $db_dir = squidguard_get_blacklist_dir();

    my $total = 0;
    my @categories = squidguard_get_blacklists();
    foreach my $category (@categories) {
	foreach my $type ('domains', 'urls') {
	    my $path = "$category/$type";
	    my $file = "$db_dir/$path";
	    if (-e $file) {
		my $wc = `cat $file| wc -l`; chomp $wc;
		$total += $wc;
	    }
	}
    }
    return $total;
}

sub squidguard_clean_tmpfiles {
    #
    # workaround for squidguard
    # bug http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=494281
    #
    my @tmpfiles = </var/tmp/*>;
    foreach my $file (@tmpfiles) {
	my ($dev, $ino, $mode, $nlink, $uid, $gid, $rdev, $size, $atime,
	    $mtime, $ctime, $blksize, $blocks) = stat($file);
	my $name = (getpwuid($uid))[0] if $uid;
	unlink($file) if $name and $name eq 'proxy';
    }
}

sub squidguard_auto_update {
    my ($interactive, $file) = @_;

    my $rc;
    my $db_dir = squidguard_get_blacklist_dir();
    my $tmp_blacklists = '/tmp/blacklists.gz';

    if (!squidguard_is_blacklist_installed()) {
        my ($disk_free, $disk_required);
        $disk_required = (30 * 1024 * 1024); # 30MB
        $disk_free = `df $db_dir | grep -v Filesystem | awk '{ print \$4 }'`;
        chomp($disk_free);
        $disk_free *= 1024;
        if ($disk_free < $disk_required) {
            die "Error: not enough disk space $disk_required\/$disk_free";
        }
    }

    if (defined $file) {
      # use existing file
	$rc = copy($file, $tmp_blacklists);
	if (!$rc) {
	    print_err($interactive, "Unable to copy [$file] $!");
	    return 1;
	}
    } else {
      # get from net
	my $opt = '';
	$opt = "-q" if ! $interactive;
	$rc = system("wget -O $tmp_blacklists $opt $blacklist_url");
	if ($rc) {
	    print_err($interactive, "Unable to download [$blacklist_url] $!");
	    return 1;
	}
    }

    print "Uncompressing blacklist...\n" if $interactive;
    $rc = system("tar --directory /tmp -zxvf $tmp_blacklists > /dev/null");
    if ($rc) {
	print_err($interactive, "Unable to uncompress [$blacklist_url] $!");
	return 1;
    }
    my $b4_entries = squidguard_count_blacklist_entries();
    my $archive = "$global_data_dir/squidguard/archive";
    mkdir_p($archive) if ! -d $archive;
    system("rm -rf $archive/*");
    system("mv $db_dir/* $archive 2> /dev/null");
    $rc = system("mv /tmp/blacklists/* $db_dir");
    if ($rc) {
	print_err($interactive, "Unable to install [$blacklist_url] $!");
	return 1;
    }
    system("mv $archive/local-* $db_dir 2> /dev/null");
    rm_rf($tmp_blacklists);
    rm_rf("/tmp/blacklists");

    my $after_entries = squidguard_count_blacklist_entries();
    my $mode = "auto-update";
    $mode = "manual" if $interactive;
    syslog(LOG_WARNING,
	   "blacklist entries updated($mode) ($b4_entries/$after_entries)");
    return 0;
}

sub squidguard_install_blacklist_def {
    squidguard_auto_update(1, undef);
}

sub squidguard_update_blacklist {
    my ($interactive, $update_category) = @_;

    my @blacklists = squidguard_get_blacklists();
    print "Checking permissions...\n" if $interactive;
    my $db_dir = squidguard_get_blacklist_dir();
    system("chown -R proxy.proxy $db_dir > /dev/null 2>&1");
    chmod(2770, $db_dir);

    #
    # generate temporary config for each category & generate DB
    #
    foreach my $category (@blacklists) {
	next if defined $update_category and $update_category ne $category;
	squidguard_generate_db($interactive, $category, 'default');
    }
}


#
# main
#
my ($update_bl, $update_bl_cat, $update_bl_file, $auto_update_bl);

GetOptions("update-blacklist!"           => \$update_bl,
	   "update-blacklist-category=s" => \$update_bl_cat,
	   "update-blacklist-file=s"     => \$update_bl_file,
	   "auto-update-blacklist!"      => \$auto_update_bl,
);

my $sg_updatestatus_file = "$global_data_dir/squidguard/updatestatus";
if (! -e "$global_data_dir/squidguard") {
    system("mkdir -p $global_data_dir/squidguard/db");
    my ($login, $pass, $uid, $gid) = getpwnam('proxy')
        or die "proxy not in passwd file";
    chown $uid, $gid, "$global_data_dir/squidguard/db";
}
touch($sg_updatestatus_file);
system("echo update failed at `date` > $sg_updatestatus_file");
system("sudo rm -f /var/lib/sitefilter/updatestatus");

my $lock_file = '/tmp/vyatta_bl_lock';
open(my $lck, ">", $lock_file) || die "Lock failed\n";
flock($lck, LOCK_EX);

if (defined $update_bl_cat) {
    squidguard_update_blacklist(1, $update_bl_cat);
    if (squidguard_is_configured()) {
	print "\nThe webproxy daemon must be restarted\n";
	if ((defined($ENV{VYATTA_PROCESS_CLIENT}) && $ENV{VYATTA_PROCESS_CLIENT} eq 'gui2_rest') ||
	    prompt("Would you like to restart it now? [confirm]",-y1d=>"y")) {
	    squid_restart(1);
	}
    }
    squidguard_clean_tmpfiles();
}

if (defined $update_bl) {
    my $updated = 0;
    if (!squidguard_is_blacklist_installed()) {
	print "Warning: No url-filtering blacklist installed\n";
	if ((defined($ENV{VYATTA_PROCESS_CLIENT}) && $ENV{VYATTA_PROCESS_CLIENT} eq 'gui2_rest') ||
	    prompt("Would you like to download a default blacklist? [confirm]",
		   -y1d=>"y")) {
	    exit 1 if squidguard_install_blacklist_def();
	    $updated = 1;
	} else {
	    exit 1;
	}
    } else {
	if ((defined($ENV{VYATTA_PROCESS_CLIENT}) && $ENV{VYATTA_PROCESS_CLIENT} eq 'gui2_rest') ||
	    prompt("Would you like to re-download the blacklist? [confirm]",
		   -y1d=>"y")) {
	    my $rc = squidguard_auto_update(1, undef);
	    $updated = 1 if ! $rc;
	}
    }
    if (! $updated) {
	print "No blacklist updated\n";
	if ((defined($ENV{VYATTA_PROCESS_CLIENT}) && $ENV{VYATTA_PROCESS_CLIENT} eq 'gui2_rest') ||
	    !prompt("Do you still want to generate binary DB? [confirm]",
		   -y1d=>"y")) {
	    exit 1;
	}
    }
    # if there was an update we need to re-gen the binary DBs
    # and restart the daemon
    squidguard_update_blacklist(1);
    if (squidguard_is_configured()) {
	print "\nThe webproxy daemon must be restarted\n";
	if ((defined($ENV{VYATTA_PROCESS_CLIENT}) && $ENV{VYATTA_PROCESS_CLIENT} eq 'gui2_rest') ||
	    prompt("Would you like to restart it now? [confirm]",-y1d=>"y")) {
	    squid_restart(1);
	}
    }
    squidguard_clean_tmpfiles();
}

if (defined $update_bl_file) {
    if (! -e $update_bl_file) {
	die "Error: file [$update_bl_file] doesn't exist";
    }
    my $rc = squidguard_auto_update(0, $update_bl_file);
    exit 1 if $rc;
    squidguard_update_blacklist(1);
    squidguard_clean_tmpfiles();
}

if (defined $auto_update_bl) {
    my $rc = squidguard_auto_update(0);
    exit 1 if $rc;
    squidguard_update_blacklist(0);
    if (squidguard_is_configured()) {
	squid_restart(0);
    }
    squidguard_clean_tmpfiles();
}

system("echo update succeeded at `date` > $sg_updatestatus_file");
close($lck);
exit 0;

#end of file
