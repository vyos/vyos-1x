<!-- include start from saml.xml.i -->
<node name="saml">
  <properties>
    <help>Identity provider configuration</help>
  </properties>

  <children>
    <!--Define IDP Name-->
    <leafNode name="name">
      <properties>
        <help>Identity provider name</help>
        <valueHelp>
          <format>&lt;provider-name&gt;</format>
          <description>Name of the identity provider</description>
        </valueHelp>
      </properties>
    </leafNode>
    <!--End ofDefine IDP Name-->

    <!--Define Metadata URL-->
    <leafNode name="metadata-url">
      <properties>
        <help>Identity provider metadata URL</help>
        <valueHelp>
          <format>https://idp.com/metadata</format>
          <description>Metadata URL of the identity provider</description>
        </valueHelp>
      </properties>
    </leafNode>
    <!--End of Define Metadata URL-->

    <!--Default SAML level-->
    <leafNode name="entityID">
      <properties>
        <help>Your SAML Entity ID</help>
        <valueHelp>
          <format>&lt;https://company.com/sso/saml&gt;</format>
          <description>SAML Entity ID</description>
        </valueHelp>
      </properties>
    </leafNode>
    <!--End of Default SAML level-->

    <!--Default SAML level-->
    <leafNode name="default-sso-level">
      <properties>
        <help>Default level for SSO users</help>
        <valueHelp>
          <format>operator || admin</format>
          <description>Default privilege level for SSO users</description>
        </valueHelp>
        <constraint>
          <regex>^(operator|admin)$</regex>
        </constraint>
      </properties>
    </leafNode>
    <!--End of Default SAML level-->

    <!--Levels-->
    <node name="admin">
      <properties>
        <help>SAML Admin level configuration</help>
      </properties>
      <children>
        <!--Req Attributes-->
        <tagNode name="req">
          <properties>
            <help>Required attributes</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Value required</help>
                <multi/>
                <valueHelp>
                  <format>&lt;value&gt;</format>
                  <description>Required value(s)</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
        <!--End of Req Attributes-->

        <!--Suff Attributes-->
        <tagNode name="suff">
          <properties>
            <help>Sufficient attributes</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Value required</help>
                <multi/>
                <valueHelp>
                  <format>&lt;value&gt;</format>
                  <description>Sufficient value(s)</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
        <!--End ofSuff Attributes-->

        <!--Admin Users-->
        <leafNode name="user">
          <properties>
            <help>Allowed admins for the identity provider</help>
            <multi/>
            <valueHelp>
              <format>&lt;username&gt;</format>
              <description>Username</description>
            </valueHelp>
          </properties>
        </leafNode>
        <!--End of Admin Users-->
      </children>
    </node>

    <node name="operator">
      <properties>
        <help>SAML Admin level configuration</help>
      </properties>
      <children>
        <!--Req Attributes-->
        <tagNode name="req">
          <properties>
            <help>Required attributes</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Value required</help>
                <multi/>
                <valueHelp>
                  <format>&lt;value&gt;</format>
                  <description>Required value(s)</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
        <!--End of Req Attributes-->

        <!--Suff Attributes-->
        <tagNode name="suff">
          <properties>
            <help>Sufficient attributes</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Value required</help>
                <multi/>
                <valueHelp>
                  <format>&lt;value&gt;</format>
                  <description>Sufficient value(s)</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
        <!--End ofSuff Attributes-->

        <!--Operator Users-->
        <leafNode name="user">
          <properties>
            <help>Allowed admins for the identity provider</help>
            <multi/>
            <valueHelp>
              <format>&lt;username&gt;</format>
              <description>Username</description>
            </valueHelp>
          </properties>
        </leafNode>
        <!--End of Operator Users-->
      </children>
    </node>
    <!--End of Levels-->
  </children>
</node>
<!-- include end -->
