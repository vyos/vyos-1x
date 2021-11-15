
from . recipe import Recipe

class ConfigFile(Recipe):
    def __init__(self, session, command_file):
        super().__init__(session, command_file)

    # Define any custom processing of parameters here by overriding
    # save/load:
    #
    # def save(self):
    #     self.data = transform_data(self.data)
    #     super().save()
    # def load(self):
    #     self.data = transform_data(self.data)
    #     super().load()
