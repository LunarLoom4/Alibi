from fastapi import FastAPI


# Creating an instance of the FastAPI class
app = FastAPI(title = "Alibi")

# Defining an endpoint to check that the server is up and running
@app.get("/api/health/")
def health():
    return {"status": "OK!"}
