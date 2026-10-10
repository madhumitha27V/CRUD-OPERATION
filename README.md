# Students Database CRUD API

A small REST API for managing student records, built with FastAPI and SQLite. It
supports create, list/filter, retrieve, replace, partial update, and delete
operations. It also includes an optional Ollama-powered natural-language
question endpoint. The model receives only records retrieved by fixed,
parameterized backend queries; it cannot run SQL.

## Requirements

- Python 3.10 or newer
- pip

## Install and run

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API creates `students.db` in the project root on first startup. To use a
different location, set `STUDENTS_DB_PATH` before starting the server.

## API documentation

With the server running, open:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

## Optional Ollama question answering

Install and start [Ollama](https://ollama.com/download), then download the
default local model:

```powershell
ollama pull llama3.2:1b
```

Ollama normally runs as a local service. If it is not already running, start it
in another terminal:

```powershell
ollama serve
```

The API defaults to `http://localhost:11434` and model `llama3.2:1b`. Override
these before starting the API if needed:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2:1b"
uvicorn app.main:app --reload
```

Ask a question with `POST /ask`:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"How many students are there?"}'

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"List students born after 2005."}'
```

The backend handles count questions and birth-year/date filters itself using
safe, parameterized SQLite queries, then supplies up to 100 matching students
(ID, name, date of birth, and course only) to Ollama. Contact details and
addresses are never sent to the model. Unsupported questions receive the
student list as context, and the model is instructed not to invent information.
If Ollama is unavailable or the configured model is missing, the API returns an
explicit error. Use dummy student data when demonstrating the AI feature.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/students` | Create a student |
| `GET` | `/students` | List students; supports `name`, `course`, `born_after`, and `born_before` filters |
| `GET` | `/students/{student_id}` | Retrieve one student |
| `PUT` | `/students/{student_id}` | Replace all student fields |
| `PATCH` | `/students/{student_id}` | Update only supplied fields |
| `DELETE` | `/students/{student_id}` | Delete a student |
| `POST` | `/ask` | Ask a question about student records using Ollama |

Student records require a name, date of birth, and at least one contact field
(`email` or `phone`). Dates must use `YYYY-MM-DD`. Email addresses are unique.
Missing records return `404`; duplicate emails return `409`; invalid input
returns `422`.

## Example requests

Create a student:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/students `
  -ContentType "application/json" `
  -Body '{"name":"Asha Rao","date_of_birth":"2005-04-12","email":"asha@example.com","course":"Computer Science"}'
```

List students born after a date:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/students?born_after=2005-01-01"
```

Partially update and delete:

```powershell
Invoke-RestMethod -Method Patch `
  -Uri http://127.0.0.1:8000/students/1 `
  -ContentType "application/json" `
  -Body '{"course":"Data Science"}'

Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:8000/students/1
```

## Run tests

```powershell
python -m pytest
```

The test suite uses a temporary SQLite database and mocks Ollama requests, so
it does not require a running model or real student information.
