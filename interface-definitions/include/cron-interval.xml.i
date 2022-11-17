<!-- include start from cron-interval.xml.i -->
<leafNode name="crontab-spec">
  <properties>
    <help>UNIX crontab time specification string</help>
  </properties>
</leafNode>
<leafNode name="interval">
  <properties>
    <help>Execution interval</help>
    <valueHelp>
      <format>&lt;minutes&gt;</format>
      <description>Execution interval in minutes</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;minutes&gt;m</format>
      <description>Execution interval in minutes</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;hours&gt;h</format>
      <description>Execution interval in hours</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;days&gt;d</format>
      <description>Execution interval in days</description>
    </valueHelp>
    <constraint>
      <regex>[1-9]([0-9]*)([mhd]{0,1})</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
