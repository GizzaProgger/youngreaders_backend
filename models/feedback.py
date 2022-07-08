from pydantic import BaseModel, NameEmail


class Feedback(BaseModel):
    email: NameEmail()
    name: str
    main_text: str
