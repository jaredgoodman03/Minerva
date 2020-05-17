from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask
)
from werkzeug.exceptions import abort
from auth import login_required
from db import users, conn, orders
from send_conformation import send_request_conformation
from json import loads, dumps
from sqlalchemy import select

itemsList = loads(open("items.json", "r").read())
categories = set()
for item in itemsList.values():
    categories.add(item['subcategory'])
bp = Blueprint('request_items', __name__)

# request seems like it's a reserved word somewhere or something,
# so use request_items instead everywhere.
@bp.route('/request_items', methods=('GET', 'POST'))
@login_required
def request_items():
    if request.method == "POST":
        itemsDict = {} # Used for email conformation script
        for item in itemsList.values():
            name = item['name']
            quantity = request.form[name + "-quantity"]
            itemsDict[name] = quantity

        send_request_conformation(g.user['email'], itemsDict)
        # insert new order into the orders table
        orderId = conn.execute(orders.insert(), contents=dumps(itemsDict), completed=0, userId=g.user.id, foodBankId=g.user.foodBankId).inserted_primary_key[0]
        # TODO: remove this code when we finish page that lets you assign orders to volunteers
        # Right now, we assign the order to volunteer example
        exampleOrders = loads(conn.execute(select([users.c.assignedOrders]).where(users.c.email=="volunteerexample@mailinator.com")).fetchone()[0])
        exampleOrders.append(orderId)
        print(exampleOrders)
        conn.execute(users.update().where(users.c.email=="volunteerexample@mailinator.com").values(assignedOrders=dumps(exampleOrders))) 
        return redirect("/success")
    
    return render_template("request_items.html", items = itemsList.values(), categories=categories)

