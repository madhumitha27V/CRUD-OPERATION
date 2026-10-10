from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class StudentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    course: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    enrollment_date: date | None = None

    @field_validator("name", "phone", "course", "address", mode="before")
    @classmethod
    def trim_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            return value or None
        return value

    @model_validator(mode="after")
    def require_contact(self) -> StudentFields:
        if not self.email and not self.phone:
            raise ValueError("At least one of email or phone is required")
        return self


class StudentCreate(StudentFields):
    pass


class StudentReplace(StudentFields):
    pass


class StudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    course: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    enrollment_date: date | None = None

    @field_validator("name", "phone", "course", "address", mode="before")
    @classmethod
    def trim_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            return value or None
        return value

    @model_validator(mode="after")
    def require_changes(self) -> StudentUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "date_of_birth" in self.model_fields_set and self.date_of_birth is None:
            raise ValueError("date_of_birth cannot be null")
        return self


class StudentResponse(StudentFields):
    id: int


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be empty")
        return value


class AskResponse(BaseModel):
    answer: str
    model: str
    matching_student_count: int
    records_considered: int
    records_truncated: bool
