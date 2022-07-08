from pydantic import BaseModel, NameEmail, constr


class NotifyPostBody(BaseModel):
    receiver_email: NameEmail()
    topic: constr(min_length=1, max_length=100)
    message: constr(min_length=1, max_length=255)
