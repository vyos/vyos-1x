<!-- include start from interface/traffic-policy.xml.i -->
<node name="traffic-policy">
  <properties>
    <help>Traffic-policy for interface</help>
  </properties>
  <children>
    <leafNode name="in">
      <properties>
        <help>Ingress traffic policy for interface</help>
        <completionHelp>
          <path>traffic-policy drop-tail</path>
          <path>traffic-policy fair-queue</path>
          <path>traffic-policy fq-codel</path>
          <path>traffic-policy limiter</path>
          <path>traffic-policy network-emulator</path>
          <path>traffic-policy priority-queue</path>
          <path>traffic-policy random-detect</path>
          <path>traffic-policy rate-control</path>
          <path>traffic-policy round-robin</path>
          <path>traffic-policy shaper</path>
          <path>traffic-policy shaper-hfsc</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Policy name</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="out">
      <properties>
        <help>Egress traffic policy for interface</help>
        <completionHelp>
          <path>traffic-policy</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Policy name</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->