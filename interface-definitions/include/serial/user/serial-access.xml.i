<!-- include start from serial/user/serial-access.xml.i -->
<tagNode name="access">
  <properties>
    <help>User serial access</help>
    <valueHelp>
      <format>start-end</format>
      <description>tty port or tty port range to match</description>
    </valueHelp>
    <completionHelp>
      <script>${vyos_completion_dir}/list_login_ttys.py</script>
    </completionHelp>
    <constraint>
      <validator name="tty-port-range"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="mode">
      <properties>
        <help>User serial access mode</help>
        <completionHelp>
          <list>read-in read-out read-write disable</list>
        </completionHelp>
        <constraint>
          <regex>(read-in|read-out|read-write|disable)</regex>
        </constraint>
        <multi/>
      </properties>
      <defaultValue>read-in read-write read-out</defaultValue>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
