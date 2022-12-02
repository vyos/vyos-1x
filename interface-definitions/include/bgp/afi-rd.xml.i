<!-- include start from bgp/afi-rd.xml.i -->
<node name="rd">
  <properties>
    <help>Specify route distinguisher</help>
  </properties>
  <children>
    <node name="vpn">
      <properties>
        <help>Between current address-family and VPN</help>
      </properties>
      <children>
        <leafNode name="export">
          <properties>
            <help>For routes leaked from current address-family to VPN</help>
            <valueHelp>
              <format>ASN:NN_OR_IP-ADDRESS:NN</format>
              <description>Route Distinguisher, (x.x.x.x:yyy|xxxx:yyyy)</description>
            </valueHelp>
            <constraint>
              <validator name="bgp-rd-rt" argument="--route-distinguisher"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
