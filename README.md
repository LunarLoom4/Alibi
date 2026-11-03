# Alibi

A multiplayer murder mystery game where AI agents exclusive to each suspect answer questions from the detectives about the night of the crime.
The game logic decides the truth. The LLM only puts that truth into words.

## Run the Backend

The Backend needs Python 3.15. All commands run in PowerShell from the `backend/` folder.

1. Create the Virtual Environment and activate it:

    ```powershell
    py -3.15 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

2. Install the exact locked Versions, then the Project itself with its Development Tools:

    ```powershell
    python -m pip install -r requirements.lock
    python -m pip install -e ".[dev]"
    ```

3. Start the Server, then open http://127.0.0.1:8000/docs/ in a Browser:

    ```powershell
    uvicorn alibi.main:app --reload --reload-dir src
    ```

4. Run the Tests:

    ```powershell
    python -m pytest
    ```