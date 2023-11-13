<!-- include start from pim/register-suppress-time.xml.i -->
<leafNode name="register-suppress-time">
  <properties>
    <help>Register Suppress Timer</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>In seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
