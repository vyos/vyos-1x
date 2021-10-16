<!-- include start from vrrp-transition-script.xml.i -->
<node name="transition-script">
  <properties>
    <help>VRRP transition scripts</help>
  </properties>
  <children>
    <leafNode name="master">
      <properties>
        <help>Script to run on VRRP state transition to master</help>
        <constraint>
          <validator name="script"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="backup">
      <properties>
        <help>Script to run on VRRP state transition to backup</help>
        <constraint>
          <validator name="script"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="fault">
      <properties>
        <help>Script to run on VRRP state transition to fault</help>
        <constraint>
          <validator name="script"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="stop">
      <properties>
        <help>Script to run on VRRP state transition to stop</help>
        <constraint>
          <validator name="script"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
