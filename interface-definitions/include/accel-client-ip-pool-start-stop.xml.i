<!-- included start from accel-client-ip-pool-start-stop.xml.i -->
<leafNode name="start">
  <properties>
    <help>First IP address in the pool</help>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="stop">
  <properties>
    <help>Last IP address in the pool</help>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
