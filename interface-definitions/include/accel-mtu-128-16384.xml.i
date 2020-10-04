          <leafNode name="mtu">
            <properties>
              <help>Maximum Transmission Unit (MTU) - default 1492</help>
              <constraint>
                <validator name="numeric" argument="--range 128-16384"/>
              </constraint>
            </properties>
            <defaultValue>1492</defaultValue>
          </leafNode>
