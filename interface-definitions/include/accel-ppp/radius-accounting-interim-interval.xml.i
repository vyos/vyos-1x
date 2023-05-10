<!-- include start from accel-ppp/radius-accounting-interim-interval.xml.i -->
<leafNode name="accounting-interim-interval">
  <properties>
    <help>Interval in seconds to send accounting information</help>
    <valueHelp>
      <format>u32:1-3600</format>
      <description>Interval in seconds to send accounting information</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-3600"/>
    </constraint>
    <constraintErrorMessage>Interval value must be between 1 and 3600 seconds</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
