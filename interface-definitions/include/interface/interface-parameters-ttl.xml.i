<!-- include start from interface/interface-parameters-ttl.xml.i -->
<leafNode name="ttl">
  <properties>
    <help>Specifies TTL value to use in outgoing packets (default: 0)</help>
    <valueHelp>
      <format>0</format>
      <description>Copy value from original IP header</description>
    </valueHelp>
    <valueHelp>
      <format>1-255</format>
      <description>Time to Live</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
    <constraintErrorMessage>TTL must be between 0 and 255</constraintErrorMessage>
  </properties>
  <defaultValue>0</defaultValue>
</leafNode>
<!-- include end -->
