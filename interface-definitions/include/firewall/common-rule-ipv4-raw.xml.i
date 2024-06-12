<!-- include start from firewall/common-rule-ipv4-raw.xml.i -->
#include <include/firewall/add-addr-to-group-ipv4.xml.i>
#include <include/firewall/action-and-notrack.xml.i>
#include <include/generic-description.xml.i>
#include <include/firewall/dscp.xml.i>
#include <include/firewall/fragment.xml.i>
#include <include/generic-disable-node.xml.i>
#include <include/firewall/icmp.xml.i>
#include <include/firewall/limit.xml.i>
#include <include/firewall/log.xml.i>
#include <include/firewall/log-options.xml.i>
#include <include/firewall/match-ipsec.xml.i>
#include <include/firewall/protocol.xml.i>
#include <include/firewall/nft-queue.xml.i>
#include <include/firewall/recent.xml.i>
#include <include/firewall/tcp-flags.xml.i>
#include <include/firewall/tcp-mss.xml.i>
#include <include/firewall/time.xml.i>
#include <include/firewall/ttl.xml.i>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
  </children>
</node>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
  </children>
</node>
<!-- include end -->