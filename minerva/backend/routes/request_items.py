from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask
)
from werkzeug.exceptions import abort
from minerva.backend.routes.auth import login_required
from minerva.backend.apis.db import users, conn, items
from minerva.backend.apis.email import send_request_confirmation
from json import loads, dumps
import datetime
from sqlalchemy import select, and_
from os import environ
from minerva.backend.apis.order_assignment import refreshOrdering
from sys import path
import json

bp = Blueprint('request_items', __name__)
strf = "%A, %B %d" # will output dates in the format like "May 31"

# request seems like it's a reserved word somewhere or something,
# so use request_items instead everywhere.
@bp.route('/request_items', methods=('GET', 'POST'))
@login_required
def request_items():
    foodBank =conn.execute(users.select(users.c.id==g.user.foodBankId)).fetchone()
    itemsList = conn.execute(select([items.c.name]).where(items.c.foodBankId==g.user.foodBankId)).fetchall()
    description = foodBank['requestPageDescription']
    if request.method == "POST":
        itemsOrdered = []
        for item in request.form:
            itemsOrdered.append(item)

        send_request_confirmation(g.user['email'], itemsOrdered, "date strftime would go here")

        oldOrder = conn.execute(orders.select().where(and_(orders.c.userId==g.user.id, orders.c.completed==0))).fetchone()
        if oldOrder != None:
            volunteer = conn.execute(users.select().where(users.c.id==oldOrder.volunteerId)).fetchone()
            if volunteer != None:
                conn.execute(orders.update(orders.c.userId==g.user.id).values(completed=1))
                refreshOrdering(volunteer)
        # insert new order into the orders table
        orderId = conn.execute(orders.insert(), contents=dumps(itemsOrdered), completed=0, bagged=0, userId=g.user.id, foodBankId=g.user.foodBankId).inserted_primary_key[0]
        return redirect("/success")
    categories = []
    return render_template("request_items.html", items=itemsList, categories=categories, dates="availableDates() would go here", description=description)

def availableDates():
    numDays = 10 # number of available days to display
    toReturn = []
    currentDay = datetime.date.today() + datetime.timedelta(days=1)
    whereClauses = {"sunday":users.c.sunday, "monday":users.c.monday,
                "tuesday":users.c.tuesday, "wednesday":users.c.wednesday,
                "thursday":users.c.thursday, "friday":users.c.friday,
                "saturday":users.c.saturday}
    while len(toReturn) < numDays:
        dayOfWeek = currentDay.strftime("%A").lower()
        volunteers = conn.execute(users.select(whereclause=and_(whereClauses[dayOfWeek]==True, users.c.foodBankId==g.user.foodBankId, users.c.approved==True))).fetchall()
        maxOrders = conn.execute(select([users.c.maxOrders]).where(users.c.id==g.user.foodBankId)).fetchone()[0]
        eligibleVolunteers = []
        for volunteer in volunteers:
            ordersList = conn.execute(orders.select(whereclause=(and_(orders.c.volunteerId==volunteer.id, orders.c.completed==0)))).fetchall()
            if len(ordersList) < maxOrders:
                eligibleVolunteers.append(volunteer)
        if len(eligibleVolunteers) > 0:
            toReturn.append(currentDay)
        currentDay = currentDay + datetime.timedelta(days=1)

    return toReturn
