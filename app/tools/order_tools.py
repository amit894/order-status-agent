from .registry import registry
from .schemas.tool_args import GetOrderArgs, GetShippingArgs, NotifyArgs

# In-memory mocked databases
_ORDERS = {"A-1029": {"tracking_id": "TRK-8810", "status": "shipped"}}
_SHIPMENTS = {"TRK-8810": {"location": "Bengaluru hub", "eta": "2026-06-16"}}
_SENT = []

@registry.register(
    name="get_order",
    description="Look up an order by its order id.",
    schema=GetOrderArgs
)
def get_order(order_id: str) -> dict:
    if order_id not in _ORDERS:
        return {"error": f"order '{order_id}' not found"}
    return _ORDERS[order_id]

@registry.register(
    name="get_shipping",
    description="Get shipping location and ETA by TRACKING id (not order id).",
    schema=GetShippingArgs
)
def get_shipping(tracking_id: str) -> dict:
    if tracking_id not in _SHIPMENTS:
        return {"error": f"tracking id '{tracking_id}' not found"}
    return _SHIPMENTS[tracking_id]

@registry.register(
    name="notify_customer",
    description="Send a message to the customer about their order.",
    schema=NotifyArgs
)
def notify_customer(order_id: str, message: str) -> dict:
    _SENT.append({"order_id": order_id, "message": message})
    return {"sent": True}
