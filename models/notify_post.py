from pydantic import BaseModel, constr, EmailStr


class NotifyPostBody(BaseModel):
    receiver_email: EmailStr
    topic: constr(min_length=1, max_length=100)
    message: constr(min_length=1, max_length=255)
