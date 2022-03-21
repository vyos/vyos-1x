<!-- include start from qos/queue-type.xml.i -->
<leafNode name="queue-type">
  <properties>
    <help>Queue type for default traffic</help>
    <completionHelp>
      <list>fq-codel fair-queue drop-tail random-detect</list>
    </completionHelp>
    <valueHelp>
      <format>fq-codel</format>
      <description>Fair Queue Codel</description>
    </valueHelp>
    <valueHelp>
      <format>fair-queue</format>
      <description>Stochastic Fair Queue (SFQ)</description>
    </valueHelp>
    <valueHelp>
      <format>drop-tail</format>
      <description>First-In-First-Out (FIFO)</description>
    </valueHelp>
    <valueHelp>
      <format>random-detect</format>
      <description>Random Early Detection (RED)</description>
    </valueHelp>
    <constraint>
      <regex>(fq-codel|fair-queue|drop-tail|random-detect)</regex>
    </constraint>
  </properties>
  <defaultValue>drop-tail</defaultValue>
</leafNode>
<!-- include end -->
