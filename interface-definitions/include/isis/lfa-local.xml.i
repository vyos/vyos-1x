<!-- include start from isis/lfa-local.xml.i -->
<node name="local">
  <properties>
    <help>Local loop free alternate options</help>
  </properties>
  <children>
    <node name="load-sharing">
      <properties>
        <help>Load share prefixes across multiple backups</help>
      </properties>
      <children>
        <node name="disable">
          <properties>
            <help>Disable load sharing</help>
          </properties>
          <children>
            #include <include/isis/level-1-2-leaf.xml.i>
          </children>
        </node>
      </children>
    </node>
    <node name="priority-limit">
      <properties>
        <help>Limit backup computation up to the prefix priority</help>
      </properties>
      <children>
        <node name="medium">
          <properties>
            <help>Compute for critical, high, and medium priority prefixes</help>
          </properties>
          <children>
            #include <include/isis/level-1-2-leaf.xml.i>
          </children>
        </node>
        <node name="high">
          <properties>
            <help>Compute for critical, and high priority prefixes</help>
          </properties>
          <children>
            #include <include/isis/level-1-2-leaf.xml.i>
          </children>
        </node>
        <node name="critical">
          <properties>
            <help>Compute for critical priority prefixes only</help>
          </properties>
          <children>
            #include <include/isis/level-1-2-leaf.xml.i>
          </children>
        </node>
      </children>
    </node>
    <node name="tiebreaker">
      <properties>
        <help>Configure tiebreaker for multiple backups</help>
      </properties>
      <children>
        <node name="downstream">
          <properties>
            <help>Prefer backup path via downstream node</help>
          </properties>
          <children>
            <tagNode name="index">
              <properties>
                <help>Set preference order among tiebreakers</help>
                <valueHelp>
                  <format>u32:1-255</format>
                    <description>The index integer value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
              <children>
                #include <include/isis/level-1-2-leaf.xml.i>
              </children>
            </tagNode>
          </children>
        </node>
        <node name="lowest-backup-metric">
          <properties>
            <help>Prefer backup path with lowest total metric</help>
          </properties>
          <children>
            <tagNode name="index">
              <properties>
                <help>Set preference order among tiebreakers</help>
                <valueHelp>
                  <format>u32:1-255</format>
                    <description>The index integer value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
              <children>
                #include <include/isis/level-1-2-leaf.xml.i>
              </children>
            </tagNode>
          </children>
        </node>
        <node name="node-protecting">
          <properties>
            <help>Prefer node protecting backup path</help>
          </properties>
          <children>
            <tagNode name="index">
              <properties>
                <help>Set preference order among tiebreakers</help>
                <valueHelp>
                  <format>u32:1-255</format>
                    <description>The index integer value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
              <children>
                #include <include/isis/level-1-2-leaf.xml.i>
              </children>
            </tagNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->