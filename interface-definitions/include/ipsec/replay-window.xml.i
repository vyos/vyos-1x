<!-- include start from ipsec/replay-window.xml.i -->
<leafNode name="replay-window">
    <properties>
      <help>IPsec replay window to configure for this CHILD_SA</help>
      <valueHelp>
        <format>u32:0</format>
        <description>Disable IPsec replay protection</description>
      </valueHelp>
      <valueHelp>
        <format>u32:1-2040</format>
        <description>Replay window size in packets</description>
      </valueHelp>
      <constraint>
        <validator name="numeric" argument="--range 0-2040"/>
      </constraint>
    </properties>
    <defaultValue>32</defaultValue>
  </leafNode>
  <!-- include end -->
