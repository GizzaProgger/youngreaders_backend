from pydantic import BaseModel, constr, conlist


class Comment(BaseModel):
    tracking: constr()
    responses: conlist(item_type=dict)
