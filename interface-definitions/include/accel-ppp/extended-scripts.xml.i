<!-- include start from accel-ppp/extended-scripts.xml.i -->
<node name="extended-scripts">
  <properties>
    <help>Extended script execution</help>
  </properties>
  <children>
    <leafNode name="on-pre-up">
      <properties>
        <help>Script to run before session interface comes up</help>
          <constraint>
            <validator name="script"/>
          </constraint>
      </properties>
    </leafNode>
    <leafNode name="on-up">
      <properties>
        <help>Script to run when session interface is completely configured and started</help>
          <constraint>
            <validator name="script"/>
          </constraint>
      </properties>
    </leafNode>
    <leafNode name="on-down">
      <properties>
        <help>Script to run when session interface going to terminate</help>
          <constraint>
            <validator name="script"/>
          </constraint>
      </properties>
    </leafNode>
    <leafNode name="on-change">
      <properties>
        <help>Script to run when session interface changed by RADIUS CoA handling</help>
          <constraint>
            <validator name="script"/>
          </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
