
from . session import Session

class RemoveFirewallAddressGroupMembers(Session):
    def __init__(self, session, data):
        super().__init__(session, data)

    # Define any custom processing of parameters here by overriding
    # configure:
    #
    # def configure(self):
    #     self._data = transform_data(self._data)
    #     super().configure()
    #     self.clean_up()

    def configure(self):
        super().configure()

        group_name = self._data['name']
        path = ['firewall', 'group', 'address-group', group_name]
        self.delete_path_if_childless(path)
