<!-- include start from qos/queue-type.xml.i -->
<leafNode name="queue-type">
  <properties>
    <help>Queue type for default traffic</help>
    <completionHelp>
      <list>drop-tail fair-queue fq-codel priority random-detect</list>
    </completionHelp>
    <valueHelp>
      <format>drop-tail</format>
      <description>First-In-First-Out (FIFO)</description>
    </valueHelp>
    <valueHelp>
      <format>fair-queue</format>
      <description>Stochastic Fair Queue (SFQ)</description>
    </valueHelp>
    <valueHelp>
      <format>fq-codel</format>
      <description>Fair Queue Codel</description>
    </valueHelp>
    <valueHelp>
      <format>priority</format>
      <description>Priority queuing</description>
    </valueHelp>
    <valueHelp>
      <format>random-detect</format>
      <description>Random Early Detection (RED)</description>
    </valueHelp>
    <constraint>
      <regex>(drop-tail|fair-queue|fq-codel|priority|random-detect)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
