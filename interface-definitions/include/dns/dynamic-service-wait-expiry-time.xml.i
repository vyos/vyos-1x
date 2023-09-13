<!-- include start from dns/dynamic-service-wait-expiry-time.xml.i -->
<leafNode name="wait-time">
  <properties>
    <help>Time in seconds to wait between update attempts</help>
    <valueHelp>
      <format>u32:60-86400</format>
      <description>Time in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 60-86400"/>
    </constraint>
    <constraintErrorMessage>Wait time must be between 60 and 86400 seconds</constraintErrorMessage>
  </properties>
</leafNode>
<leafNode name="expiry-time">
  <properties>
    <help>Time in seconds for the hostname to be marked expired in cache</help>
    <valueHelp>
      <format>u32:300-2160000</format>
      <description>Time in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 300-2160000"/>
    </constraint>
    <constraintErrorMessage>Expiry time must be between 300 and 2160000 seconds</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
