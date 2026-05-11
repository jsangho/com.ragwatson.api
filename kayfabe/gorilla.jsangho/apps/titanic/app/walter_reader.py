import pandas as pd
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent
_CSV_PATH = _DATA_DIR / "Titanic-Dataset.csv"

class WalterReader:
    def __init__(self):
        self.df = pd.read_csv(_CSV_PATH)

    def get_data(self):
        # 인덱스 1번 행만 반환 (DataFrame 형태 유지)
        # pandas iloc은 0-based이므로 1번 행은 iloc[[1]]
        row = self.df.iloc[[4]].astype(object)
        return row.where(row.notna(), None)

    def get_count(self):
        total_passengers = int(len(df))
        return self.pd.DataFrame([{"total_passengers": total_passengers}])

    def get_count_survived(self):
        survived_passengers = int((df["Survived"] == 1).sum())
        return self.pd.DataFrame([{"survived_passengers": survived_passengers}])

    def get_count_dead(self):
        dead_passengers = int((df["Survived"] == 0).sum())
        return self.pd.DataFrame([{"dead_passengers": dead_passengers}])
