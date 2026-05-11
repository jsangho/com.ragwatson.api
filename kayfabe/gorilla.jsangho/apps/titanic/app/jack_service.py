from titanic.app.walter_reader import WalterReader
from titanic.app.rose_model import RoseModel

class JackService:
    def __init__(self):
        self.walter = WalterReader()
        self.rose = RoseModel()

    def get_training_model_name(self) -> str:
        return self.rose.model_path.stem
    