from pydantic import BaseModel, constr, conlist


class StepPostBody(BaseModel):
    tracking: constr()
    responses: conlist(item_type=dict)
