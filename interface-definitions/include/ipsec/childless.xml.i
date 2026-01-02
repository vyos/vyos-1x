<!-- include start from ipsec/childless.xml.i -->
<leafNode name="childless">
  <properties>
    <help>Enable support for childless IKE SA initiation</help>
    <completionHelp>
      <list>allow prefer force never</list>
    </completionHelp>
    <valueHelp>
      <format>allow</format>
      <description>Accept childless IKE SA in responder mode. Create regular IKE SA in initiator mode</description>
    </valueHelp>
    <valueHelp>
      <format>prefer</format>
      <description>In both responder and initiator modes, accept and create childless IKE SA correspondingly</description>
    </valueHelp>
    <valueHelp>
      <format>force</format>
      <description>Require the use of childless IKE SA in both responder and initiator modes</description>
    </valueHelp>
    <valueHelp>
      <format>never</format>
      <description>Disable support for childless IKE SAs when acting as a responder</description>
    </valueHelp>
    <constraint>
      <regex>(allow|prefer|force|never)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
