<!-- include start from accel-ppp/log.xml.i -->
<node name="log">
  <properties>
    <help>Server logging </help>
  </properties>
  <children>
    <leafNode name="level">
      <properties>
        <help>Specifies log level</help>
        <valueHelp>
          <format>0</format>
          <description>Turn off logging</description>
        </valueHelp>
        <valueHelp>
          <format>1</format>
          <description>Log only error messages</description>
        </valueHelp>
        <valueHelp>
          <format>2</format>
          <description>Log error and warning messages</description>
        </valueHelp>
        <valueHelp>
          <format>3</format>
          <description>Log error, warning and minimum information messages</description>
        </valueHelp>
        <valueHelp>
          <format>4</format>
          <description>Log error, warning and full information messages</description>
        </valueHelp>
        <valueHelp>
          <format>5</format>
          <description>Log all messages including debug messages</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-5"/>
        </constraint>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
