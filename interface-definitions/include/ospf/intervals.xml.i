<!-- include start from ospf/intervals.xml.i -->
<leafNode name="dead-interval">
  <properties>
    <help>Interval after which a neighbor is declared dead</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Neighbor dead interval (seconds)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>40</defaultValue>
</leafNode>
<leafNode name="hello-interval">
  <properties>
    <help>Interval between hello packets</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Hello interval (seconds)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>10</defaultValue>
</leafNode>
<leafNode name="retransmit-interval">
  <properties>
    <help>Interval between retransmitting lost link state advertisements</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Retransmit interval (seconds)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>5</defaultValue>
</leafNode>
<leafNode name="transmit-delay">
  <properties>
    <help>Link state transmit delay</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Link state transmit delay (seconds)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
  <defaultValue>1</defaultValue>
</leafNode>
<!-- include end -->
