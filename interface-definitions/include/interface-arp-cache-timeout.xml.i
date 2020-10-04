<!-- included start from interface-arp-cache-timeout.xml.i -->
<leafNode name="arp-cache-timeout">
  <properties>
    <help>ARP cache entry timeout in seconds</help>
    <valueHelp>
      <format>1-86400</format>
      <description>ARP cache entry timout in seconds (default 30)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-86400"/>
    </constraint>
    <constraintErrorMessage>ARP cache entry timeout must be between 1 and 86400 seconds</constraintErrorMessage>
  </properties>
  <defaultValue>30</defaultValue>
</leafNode>
<!-- included end -->
