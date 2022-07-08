from pydantic import BaseModel, constr


class Result(BaseModel):
    tracking: constr()
    result: constr(min_length=1, max_length=255)
