<!-- include start from serial/user/serial-timeout.xml.i -->
<node name="timeout">
  <properties>
    <help>User serial timeout</help>
  </properties>
  <children>
    <leafNode name="session">
      <properties>
        <help>Close the session/connection when the user Session Timeout expires (in s)</help>
        <valueHelp>
          <format>u32:0-4294967</format>
          <description>Decimal integer (0 - 4294967)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="idle">
      <properties>
        <help>Close a connection because of inactivity when the user Idle Timeout expires (in s)</help>
        <valueHelp>
          <format>u32:0-4294967</format>
          <description>Decimal integer (0 - 4294967)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
