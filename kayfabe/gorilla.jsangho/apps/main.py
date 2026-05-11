from fastapi import FastAPI

from titanic.app.james_controller import JamesController

from doro.app.doro_director import DoroDirector

app = FastAPI(title="JSangHo Main Page")

@app.get("/")
def read_root():
    return {"message": "FAST API 메인 페이지", "docs": "/docs", "health": "ok"}

@app.get("/titanic/data")
def read_titanic_data():
    james = JamesController()
    df = james.get_data()

    return df.to_dict(orient="records")

@app.get("/titanic/count")
def read_titanic_count():
    james = JamesController()
    df = james.get_count()

    return df.to_dict(orient="records")

@app.get("/titanic/count/survived")
def read_titanic_count_survived():
    james = JamesController()
    df = james.get_count_survived()

    return df.to_dict(orient="records")

@app.get("/titanic/count/dead")
def read_titanic_count_dead():
    james = JamesController()
    df = james.get_count_dead()

    return df.to_dict(orient="records")

@app.get("/titanic/tree")
def read_titanic_tree():
    james = JamesController()
    has_model = james.has_decision_tree_model()
    return {"model": "titanic_decision_tree", "exists": bool(has_model)}

@app.get("/titanic/model")
def read_titanic_model():
    james = JamesController()
    return {"model_name": james.get_model_name()}


@app.get("/doro/data")
def read_doro_data():
    doro_director = DoroDirector()
    df = doro_director.get_data()

    return df.to_dict(orient="records")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.main:app", host="127.0.0.1", port=8000, reload=True)