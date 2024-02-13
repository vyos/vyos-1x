<!-- include start from accel-ppp/limits.xml.i -->
<node name="limits">
  <properties>
    <help>Limits the connection rate from a single source</help>
  </properties>
  <children>
    <leafNode name="connection-limit">
      <properties>
        <help>Acceptable rate of connections (e.g. 1/min, 60/sec)</help>
        <constraint>
          <regex>[0-9]+\/(min|sec)</regex>
        </constraint>
        <constraintErrorMessage>illegal value</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="burst">
      <properties>
        <help>Burst count</help>
      </properties>
    </leafNode>
    <leafNode name="timeout">
      <properties>
        <help>Timeout in seconds</help>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
