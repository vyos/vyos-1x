<!-- include start from bgp/afi-l2vpn-common.xml.i -->
<leafNode name="advertise-default-gw">
  <properties>
    <help>Advertise All default g/w mac-ip routes in EVPN</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="advertise-svi-ip">
  <properties>
    <help>Advertise svi mac-ip routes in EVPN</help>
    <valueless/>
  </properties>
</leafNode>
#include <include/bgp/route-distinguisher.xml.i>
<node name="route-target">
  <properties>
    <help>Route Target</help>
  </properties>
  <children>
    <leafNode name="both">
      <properties>
        <help>Route Target both import and export</help>
        <valueHelp>
          <format>txt</format>
          <description>Route target (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
        </valueHelp>
        <constraint>
          <validator name="bgp-rd-rt" argument="--route-target"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>Route Target import</help>
        <valueHelp>
          <format>txt</format>
          <description>Route target (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
        </valueHelp>
        <constraint>
          <validator name="bgp-rd-rt" argument="--route-target"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="export">
      <properties>
        <help>Route Target export</help>
        <valueHelp>
          <format>txt</format>
          <description>Route target (A.B.C.D:MN|EF:OPQR|GHJK:MN)</description>
        </valueHelp>
        <constraint>
          <validator name="bgp-rd-rt" argument="--route-target"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
