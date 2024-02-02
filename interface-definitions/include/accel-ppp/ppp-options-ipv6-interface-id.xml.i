<!-- include start from accel-ppp/ppp-options-ipv6-interface-id.xml.i -->
<leafNode name="ipv6-interface-id">
  <properties>
    <help>Fixed or random interface identifier for IPv6</help>
    <completionHelp>
      <list>random</list>
    </completionHelp>
    <valueHelp>
      <format>random</format>
      <description>Random interface identifier for IPv6</description>
    </valueHelp>
    <valueHelp>
      <format>x:x:x:x</format>
      <description>specify interface identifier for IPv6</description>
    </valueHelp>
    <constraint>
      <regex>(random|((\d+){1,4}:){3}(\d+){1,4})</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="ipv6-peer-interface-id">
  <properties>
    <help>Peer interface identifier for IPv6</help>
    <completionHelp>
      <list>random calling-sid ipv4-addr</list>
    </completionHelp>
    <valueHelp>
      <format>x:x:x:x</format>
      <description>Interface identifier for IPv6</description>
    </valueHelp>
    <valueHelp>
      <format>random</format>
      <description>Use a random interface identifier for IPv6</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4-addr</format>
      <description>Calculate interface identifier from IPv4 address, for example 192:168:0:1</description>
    </valueHelp>
    <valueHelp>
      <format>calling-sid</format>
      <description>Calculate interface identifier from calling-station-id</description>
    </valueHelp>
    <constraint>
      <regex>(random|calling-sid|ipv4-addr|((\d+){1,4}:){3}(\d+){1,4})</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="ipv6-accept-peer-interface-id">
  <properties>
    <help>Accept peer interface identifier</help>
    <valueless/>
  </properties>
</leafNode>
<!-- include end -->
