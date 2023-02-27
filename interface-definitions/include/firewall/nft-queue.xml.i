<!-- include start from firewall/nft-queue.xml.i -->
<leafNode name="queue">
  <properties>
    <help>Queue target to use. Action queue must be defined to use this setting</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Queue target</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 0-65535"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="queue-options">
  <properties>
    <help>Options used for queue target. Action queue must be defined to use this setting</help>
    <completionHelp>
      <list>bypass fanout</list>
    </completionHelp>
    <valueHelp>
      <format>bypass</format>
      <description>Let packets go through if userspace application cannot back off</description>
    </valueHelp>
    <valueHelp>
      <format>fanout</format>
      <description>Distribute packets between several queues</description>
    </valueHelp>
    <constraint>
      <regex>(bypass|fanout)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->