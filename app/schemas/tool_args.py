from pydantic import BaseModel

class GetOrderArgs(BaseModel):
    order_id: str

class GetShippingArgs(BaseModel):
    tracking_id: str

class NotifyArgs(BaseModel):
    order_id: str
    message: str
