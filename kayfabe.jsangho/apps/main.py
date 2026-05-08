from fastapi import FastAPI

from titanic.app.james import James

from doro.app.doro_director import DoroDirector

app = FastAPI(title="JSangHo Main Page")

@app.get("/")
def read_root():
    return {"message": "FAST API 메인 페이지", "docs": "/docs", "health": "ok"}

@app.get("/titanic/data")
def read_titanic_data():
    james = James()
    df = james.get_data()

    return df.to_dict(orient="records")

@app.get("/titanic/count")
def read_titanic_count():
    james = James()
    df = james.get_count()

    return df.to_dict(orient="records")

@app.get("/titanic/count/survived")
def read_titanic_count_survived():
    james = James()
    df = james.get_count_survived()

    return df.to_dict(orient="records")

@app.get("/titanic/count/dead")
def read_titanic_count_dead():
    james = James()
    df = james.get_count_dead()

    return df.to_dict(orient="records")


@app.get("/doro/data")
def read_doro_data():
    doro_director = DoroDirector()
    df = doro_director.get_data()

    return df.to_dict(orient="records")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.main:app", host="127.0.0.1", port=8000, reload=True)