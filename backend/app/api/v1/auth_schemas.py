from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cookie: str
    expires_at: int
