<leafNode name="port">
  <properties>
    <help>Port number used to establish connection</help>
    <valueHelp>
      <format>1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
