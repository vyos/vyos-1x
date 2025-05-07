<!-- include start from serial/general/keepalive-setting.xml.i -->
<leafNode name="interval">
  <properties>
    <help>Monitor Connection Interval (in s, default: 180)</help>
    <valueHelp>
      <format>u32:1-32767</format>
      <description>Decimal integer (1-32767)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-32767"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="retries">
  <properties>
    <help>Monitor Connection Number of Retries (default: 5)</help>
    <valueHelp>
      <format>u32:1-32767</format>
      <description>Decimal integer (1-32767)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-32767"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="retry-timeout">
  <properties>
    <help>Monitor Connection Retry Timeout (default: 5)</help>
    <valueHelp>
      <format>u32:1-32767</format>
      <description>Decimal integer (1-32767)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-32767"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
