from pydantic import BaseModel, constr


class Comment(BaseModel):
    quote_id: constr()
    content: constr(min_length=1, max_length=255)
