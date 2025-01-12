from standardbackend.helpers.thread import Thread
from standardbackend.utils import pretty_print_messages
import logging

# Configure logging to print to stdout with colors
logging.basicConfig(
    level=logging.INFO,
    format="\033[36m%(asctime)s\033[0m - \033[32m%(name)s\033[0m - \033[1;33m%(levelname)s\033[0m - %(message)s",
)

# Set up logging
logger = logging.getLogger(__name__)


# # Chain of tool interactions
# analysis_thread = Thread()
# messages = analysis_thread.send_message("What's my current CPU usage? Use the tool!")
# # Then ask for analysis of that data
# messages = analysis_thread.send_message(
#     "Based on the CPU usage you just checked, would you recommend running a heavy computation task right now? Why?"
# )
# pretty_print_messages(messages)


class FakeDatabase:
    def __init__(self):
        self.customers = [
            {
                "id": "1213210",
                "name": "John Doe",
                "email": "john@gmail.com",
                "phone": "123-456-7890",
                "username": "johndoe",
            },
            {
                "id": "2837622",
                "name": "Priya Patel",
                "email": "priya@candy.com",
                "phone": "987-654-3210",
                "username": "priya123",
            },
            {
                "id": "3924156",
                "name": "Liam Nguyen",
                "email": "lnguyen@yahoo.com",
                "phone": "555-123-4567",
                "username": "liamn",
            },
            {
                "id": "4782901",
                "name": "Aaliyah Davis",
                "email": "aaliyahd@hotmail.com",
                "phone": "111-222-3333",
                "username": "adavis",
            },
            {
                "id": "5190753",
                "name": "Hiroshi Nakamura",
                "email": "hiroshi@gmail.com",
                "phone": "444-555-6666",
                "username": "hiroshin",
            },
            {
                "id": "6824095",
                "name": "Fatima Ahmed",
                "email": "fatimaa@outlook.com",
                "phone": "777-888-9999",
                "username": "fatimaahmed",
            },
            {
                "id": "7135680",
                "name": "Alejandro Rodriguez",
                "email": "arodriguez@protonmail.com",
                "phone": "222-333-4444",
                "username": "alexr",
            },
            {
                "id": "8259147",
                "name": "Megan Anderson",
                "email": "megana@gmail.com",
                "phone": "666-777-8888",
                "username": "manderson",
            },
            {
                "id": "9603481",
                "name": "Kwame Osei",
                "email": "kwameo@yahoo.com",
                "phone": "999-000-1111",
                "username": "kwameo",
            },
            {
                "id": "1057426",
                "name": "Mei Lin",
                "email": "meilin@gmail.com",
                "phone": "333-444-5555",
                "username": "mlin",
            },
        ]

        self.orders = [
            {
                "id": "24601",
                "customer_id": "1213210",
                "product": "Wireless Headphones",
                "quantity": 1,
                "price": 79.99,
                "status": "Shipped",
            },
            {
                "id": "13579",
                "customer_id": "1213210",
                "product": "Smartphone Case",
                "quantity": 2,
                "price": 19.99,
                "status": "Processing",
            },
            {
                "id": "97531",
                "customer_id": "2837622",
                "product": "Bluetooth Speaker",
                "quantity": 1,
                "price": "49.99",
                "status": "Shipped",
            },
            {
                "id": "86420",
                "customer_id": "3924156",
                "product": "Fitness Tracker",
                "quantity": 1,
                "price": 129.99,
                "status": "Delivered",
            },
            {
                "id": "54321",
                "customer_id": "4782901",
                "product": "Laptop Sleeve",
                "quantity": 3,
                "price": 24.99,
                "status": "Shipped",
            },
            {
                "id": "19283",
                "customer_id": "5190753",
                "product": "Wireless Mouse",
                "quantity": 1,
                "price": 34.99,
                "status": "Processing",
            },
            {
                "id": "74651",
                "customer_id": "6824095",
                "product": "Gaming Keyboard",
                "quantity": 1,
                "price": 89.99,
                "status": "Delivered",
            },
            {
                "id": "30298",
                "customer_id": "7135680",
                "product": "Portable Charger",
                "quantity": 2,
                "price": 29.99,
                "status": "Shipped",
            },
            {
                "id": "47652",
                "customer_id": "8259147",
                "product": "Smartwatch",
                "quantity": 1,
                "price": 199.99,
                "status": "Processing",
            },
            {
                "id": "61984",
                "customer_id": "9603481",
                "product": "Noise-Cancelling Headphones",
                "quantity": 1,
                "price": 149.99,
                "status": "Shipped",
            },
            {
                "id": "58243",
                "customer_id": "1057426",
                "product": "Wireless Earbuds",
                "quantity": 2,
                "price": 99.99,
                "status": "Delivered",
            },
            {
                "id": "90357",
                "customer_id": "1213210",
                "product": "Smartphone Case",
                "quantity": 1,
                "price": 19.99,
                "status": "Shipped",
            },
            {
                "id": "28164",
                "customer_id": "2837622",
                "product": "Wireless Headphones",
                "quantity": 2,
                "price": 79.99,
                "status": "Processing",
            },
        ]

    def get_user(self, key, value):
        if key in {"email", "phone", "username"}:
            for customer in self.customers:
                if customer[key] == value:
                    return customer
            return f"Couldn't find a user with {key} of {value}"
        else:
            raise ValueError(f"Invalid key: {key}")

        return None

    def get_order_by_id(self, order_id):
        for order in self.orders:
            if order["id"] == order_id:
                return order
        return None

    def get_customer_orders(self, customer_id):
        return [order for order in self.orders if order["customer_id"] == customer_id]

    def cancel_order(self, order_id):
        order = self.get_order_by_id(order_id)
        if order:
            if order["status"] == "Processing":
                order["status"] = "Cancelled"
                return "Cancelled the order"
            else:
                return "Order has already shipped.  Can't cancel it."
        return "Can't find that order!"


from standardbackend.tools.base import Tool
from pydantic import BaseModel


class GetUserInput(BaseModel):
    key: str
    value: str


class GetOrderInput(BaseModel):
    order_id: str


class CancelOrderInput(BaseModel):
    order_id: str


class GetCustomerOrdersInput(BaseModel):
    customer_id: str


db = FakeDatabase()


def fail_tool(input):
    raise Exception("Not implemented")


tools = [
    Tool(
        name="get_user",
        description="Get a user by their email, phone, or username",
        input_schema=GetUserInput,
        execute=lambda input: db.get_user(input.key, input.value),
    ),
    Tool(
        name="get_order",
        description="Get an order by its ID",
        input_schema=GetOrderInput,
        execute=lambda input: db.get_order_by_id(input.order_id),
    ),
    Tool(
        name="cancel_order",
        description="Cancel an order by its ID",
        input_schema=CancelOrderInput,
        execute=lambda input: db.cancel_order(input.order_id),
    ),
    Tool(
        name="get_customer_orders",
        description="Get all orders for a customer by their ID",
        input_schema=GetCustomerOrdersInput,
        execute=lambda input: db.get_customer_orders(input.customer_id),
    ),
]

from standardbackend.tools.python_code_runner import python_tool
from pathlib import Path
import os


class GetDesktopFilesInput(BaseModel):
    pass


def get_desktop_files():
    desktop_path = os.path.join(Path.home(), "Desktop")
    try:
        files = os.listdir(desktop_path)
        return {"files": files, "path": desktop_path}
    except Exception as e:
        return {"error": str(e)}


tools.append(
    Tool(
        name="get_desktop_files",
        description="Get a list of all files on the user's desktop",
        input_schema=GetDesktopFilesInput,
        execute=lambda input: get_desktop_files(),
    )
)

# also make it able to run python scripts
tools.append(python_tool)

t = Thread(
    tools=tools,
)
messages = t.send_message(
    "Can you get the files on my desktop? make a graph of how many of each type i have"
)
pretty_print_messages(messages)
