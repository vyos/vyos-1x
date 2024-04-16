<!-- include start from haproxy/tcp-request.xml.i -->
<node name="tcp-request">
  <properties>
    <help>tcp-request directive</help>
  </properties>
  <children>
    <leafNode name="inspect-delay">
      <properties>
        <help>Set the maximum allowed time to wait for data during content inspection</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>the timeout value specified in milliseconds</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
