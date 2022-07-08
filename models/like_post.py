from pydantic import BaseModel, constr


class LikePostBody(BaseModel):
    quote_id: constr()
    tracking: constr()

