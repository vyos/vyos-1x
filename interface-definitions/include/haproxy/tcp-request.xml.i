<!-- include start from haproxy/tcp-request.xml.i -->
<node name="tcp-request">
  <properties>
    <help>TCP request directive</help>
  </properties>
  <children>
    <leafNode name="inspect-delay">
      <properties>
        <help>Set the maximum allowed time to wait for data during content inspection</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>The timeout value specified in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
        <constraintErrorMessage>The timeout value must be in range 1 to 65535 milliseconds</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
