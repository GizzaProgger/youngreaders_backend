from pydantic import BaseModel, EmailStr


class Feedback(BaseModel):
    email: EmailStr
    name: str
    main_text: str
