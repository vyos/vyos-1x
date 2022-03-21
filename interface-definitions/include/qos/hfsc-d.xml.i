<!-- include start from qos/hfsc-d.xml.i -->
<leafNode name="d">
  <properties>
    <help>Service curve delay</help>
    <valueHelp>
      <format>&lt;number&gt;</format>
      <description>Time in milliseconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
    <constraintErrorMessage>Priority must be between 0 and 65535</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
