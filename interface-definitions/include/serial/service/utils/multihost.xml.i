<!-- include start from serial/service/utils/multihost.xml.i -->
<leafNode name="mode">
  <properties>
    <help>Multihost mode</help>
    <completionHelp>
      <list>backup-failover all-hosts disable</list>
    </completionHelp>
    <valueHelp>
      <format>backup-failover</format>
      <description>Initiate connection to backup host if main host is unavailable</description>
    </valueHelp>
    <valueHelp>
      <format>all-hosts</format>
      <description>Initiate connection to all hosts listed in multihost list</description>
    </valueHelp>
    <valueHelp>
      <format>disable</format>
      <description>Disable multihost feature</description>
    </valueHelp>
    <constraint>
      <regex>(backup-failover|all-hosts|disable)</regex>
    </constraint>
  </properties>
  <defaultValue>disable</defaultValue>
</leafNode>
<leafNode name="backup-hostname">
  <properties>
    <help>Backup host name</help>
    <constraint>
      <regex>[-a-zA-Z0-9]+</regex>
    </constraint>
    <constraintErrorMessage>Host name must be alphanumeric and can contain hyphens</constraintErrorMessage>
  </properties>
</leafNode>
<leafNode name="backup-hostport">
  <properties>
    <help>Backup host tcp port</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Port number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
