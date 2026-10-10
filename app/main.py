import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query, Response, status

from app.database import get_connection, initialize_database, row_to_dict
from app.ollama import generate_answer, retrieve_student_context
from app.schemas import (
    AskRequest,
    AskResponse,
    StudentCreate,
    StudentReplace,
    StudentResponse,
    StudentUpdate,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Students Database CRUD API",
    description=(
        "Create, list, retrieve, update, and delete student records, with an "
        "optional Ollama-powered natural-language question endpoint."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/ask", response_model=AskResponse, tags=["AI"])
def ask_students(request: AskRequest) -> AskResponse:
    try:
        context = retrieve_student_context(request.question)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        answer, model = generate_answer(request.question, context)
    except httpx.ConnectError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cannot connect to Ollama. Start Ollama and confirm it is "
                "listening at OLLAMA_BASE_URL."
            ),
        ) from error
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail="Ollama did not respond before the request timed out",
        ) from error
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Ollama returned HTTP {error.response.status_code}; "
                "confirm the configured model is installed."
            ),
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502, detail="The request to Ollama failed"
        ) from error
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=502, detail="Ollama returned an invalid response"
        ) from error

    return AskResponse(
        answer=answer,
        model=model,
        matching_student_count=context["matching_student_count"],
        records_considered=len(context["students"]),
        records_truncated=context["records_truncated"],
    )


def _get_student_or_404(student_id: int) -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return row_to_dict(row)


def _handle_duplicate_email(error: sqlite3.IntegrityError) -> None:
    if "students.email" in str(error).lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this email already exists",
        ) from error
    raise error


@app.post(
    "/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["students"],
)
def create_student(student: StudentCreate) -> dict:
    values = student.model_dump(mode="json")
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO students ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            student_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        _handle_duplicate_email(error)
    return _get_student_or_404(student_id)


@app.get("/students", response_model=list[StudentResponse], tags=["students"])
def list_students(
    name: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    course: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    born_after: date | None = None,
    born_before: date | None = None,
) -> list[dict]:
    conditions = []
    parameters: list[str] = []
    if name is not None:
        conditions.append("name LIKE ? COLLATE NOCASE")
        parameters.append(f"%{name.strip()}%")
    if course is not None:
        conditions.append("course LIKE ? COLLATE NOCASE")
        parameters.append(f"%{course.strip()}%")
    if born_after is not None:
        conditions.append("date_of_birth > ?")
        parameters.append(born_after.isoformat())
    if born_before is not None:
        conditions.append("date_of_birth < ?")
        parameters.append(born_before.isoformat())

    query = "SELECT * FROM students"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_dict(row) for row in rows]


@app.get(
    "/students/{student_id}", response_model=StudentResponse, tags=["students"]
)
def get_student(student_id: int) -> dict:
    return _get_student_or_404(student_id)


def _update_student(student_id: int, values: dict) -> dict:
    existing = _get_student_or_404(student_id)
    updated = {**existing, **values}
    if not updated["email"] and not updated["phone"]:
        raise HTTPException(
            status_code=422,
            detail="At least one of email or phone must remain set",
        )

    normalized_values = {
        key: (value.isoformat() if isinstance(value, date) else value)
        for key, value in values.items()
    }
    assignments = ", ".join(f"{key} = ?" for key in normalized_values)
    try:
        with get_connection() as connection:
            connection.execute(
                f"UPDATE students SET {assignments} WHERE id = ?",
                (*normalized_values.values(), student_id),
            )
    except sqlite3.IntegrityError as error:
        _handle_duplicate_email(error)
    return _get_student_or_404(student_id)


@app.put(
    "/students/{student_id}", response_model=StudentResponse, tags=["students"]
)
def replace_student(student_id: int, student: StudentReplace) -> dict:
    values = student.model_dump(mode="json")
    return _update_student(student_id, values)


@app.patch(
    "/students/{student_id}", response_model=StudentResponse, tags=["students"]
)
def update_student(student_id: int, student: StudentUpdate) -> dict:
    values = student.model_dump(exclude_unset=True, mode="json")
    return _update_student(student_id, values)


@app.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["students"],
)
def delete_student(student_id: int) -> Response:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM students WHERE id = ?", (student_id,)
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
