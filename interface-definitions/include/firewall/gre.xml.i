<!-- include start from firewall/gre.xml.i -->
<node name="gre">
  <properties>
    <help>GRE fields to match</help>
  </properties>
  <children>
    <node name="flags">
      <properties>
        <help>GRE flag bits to match</help>
      </properties>
      <children>
        <node name="key">
          <properties>
            <help>Header includes optional key field</help>
          </properties>
          <children>
            <leafNode name="unset">
              <properties>
                <help>Header does not include optional key field</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <node name="checksum">
          <properties>
            <help>Header includes optional checksum</help>
          </properties>
          <children>
            <leafNode name="unset">
              <properties>
                <help>Header does not include optional checksum</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <node name="sequence">
          <properties>
            <help>Header includes a sequence number field</help>
          </properties>
          <children>
            <leafNode name="unset">
              <properties>
                <help>Header does not include a sequence number field</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="inner-proto">
      <properties>
        <help>EtherType of encapsulated packet</help>
        <completionHelp>
          <list>ip ip6 arp 802.1q 802.1ad</list>
        </completionHelp>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Ethernet protocol number</description>
        </valueHelp>
        <valueHelp>
          <format>u32:0x0-0xffff</format>
          <description>Ethernet protocol number (hex)</description>
        </valueHelp>
        <valueHelp>
          <format>ip</format>
          <description>IPv4</description>
        </valueHelp>
        <valueHelp>
          <format>ip6</format>
          <description>IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>arp</format>
          <description>Address Resolution Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>802.1q</format>
          <description>VLAN-tagged frames (IEEE 802.1q)</description>
        </valueHelp>
        <valueHelp>
          <format>802.1ad</format>
          <description>Provider Bridging (IEEE 802.1ad, Q-in-Q)</description>
        </valueHelp>
        <valueHelp>
          <format>gretap</format>
          <description>Transparent Ethernet Bridging (L2 Ethernet over GRE, gretap)</description>
        </valueHelp>
        <constraint>
          <regex>(ip|ip6|arp|802.1q|802.1ad|gretap|0x[0-9a-fA-F]{1,4})</regex>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/interface/parameters-key.xml.i>
    <leafNode name="version">
      <properties>
        <help>GRE Version</help>
        <valueHelp>
          <format>gre</format>
          <description>Standard GRE</description>
        </valueHelp>
        <valueHelp>
          <format>pptp</format>
          <description>Point to Point Tunnelling Protocol</description>
        </valueHelp>
        <constraint>
          <regex>(gre|pptp)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
