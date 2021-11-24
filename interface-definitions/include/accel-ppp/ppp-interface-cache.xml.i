<!-- include start from accel-ppp/ppp-interface-cache.xml.i -->
<leafNode name="interface-cache">
  <properties>
    <help>PPP interface cache</help>
    <valueHelp>
      <format>u32:1-256000</format>
      <description>Count of interfaces to keep in cache</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-256000"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
