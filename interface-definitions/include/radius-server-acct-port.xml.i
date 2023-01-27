<!-- include start from radius-server-acct-port.xml.i -->
<leafNode name="port">
  <properties>
    <help>Accounting port</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>1813</defaultValue>
</leafNode>
<!-- include end -->
