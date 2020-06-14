from flask import ( Blueprint, flash, g, redirect, render_template,
    request, session, url_for, Flask, make_response
)
from werkzeug.exceptions import abort
from auth import login_required, admin_required 
from json import loads, dumps
from collections import OrderedDict
from db import users, conn, orders
from sqlalchemy import and_, select
from os import environ
from barcode import Code128
import datetime
from barcode.writer import ImageWriter
import assign
import io
import pdfkit
import base64
import qrcode
from send_confirmation import send_recieved_notification, send_bagged_notification
bp = Blueprint('view_all_orders', __name__)

@login_required
@admin_required
@bp.route('/allorders', methods=('GET', 'POST'))
def allOrders():
    itemsList = loads(conn.execute(users.select(users.c.id==g.user.foodBankId)).fetchone()['items'])
    ordersDict = getOrders(g.user.id)
    if request.method == "GET" and "assignall" in request.args.keys():
        assign.assignAllOrders(g.user.id)
        return redirect('/allorders')
    if request.method == "GET" and "volunteer" in request.args.keys():
        volunteerId = int(request.args.get("volunteer"))
        orderId = int(request.args.get("order"))
        bagged = conn.execute(select([orders.c.bagged]).where(orders.c.id==orderId)).fetchall()[0]
        conn.execute(orders.update(whereclause=orders.c.id==orderId).values(volunteerId=volunteerId))
        print("out of the thinmg")
        if bagged == 1:
            print("In the thing")
            conn.execute(orders.update(whereclause=orders.c.id==orderId).values(volunteerId=volunteerId))
            volunteerEmail = conn.execute(select([users.c.email]).where(users.c.id==volunteerId)).fetchone()[0]
            print("Volunteer email")
            userId = conn.execute(select([orders.c.userId]).where(orders.c.id==orderId)).fetchone()[0]
            address = conn.execute(select([users.c.address]).where(users.c.id==userId)).fetchone()[0]
            send_bagged_notification(reciever_email=volunteerEmail, orderId=orderId, address=address)
        return redirect("/allorders")
    if request.method == "POST":
        key = next(request.form.keys())
        print("Key: " + str(key))
        if "unassign" in key:
            orderId = int(key[len('unassign-'):])
            conn.execute(orders.update(whereclause=(orders.c.id==orderId)).values(volunteerId=None))
            ordersDict = getOrders(g.user.id)
        elif "bag" in key:
            orderId = int(key[len('bag-'):])
            query = select([orders.c.bagged]).where(orders.c.id==orderId)
            bagged = conn.execute(query).fetchone()[0]
            volunteerEmail = conn.execute(select([users.c.email]).where(users.c.id==select([orders.c.volunteerId]).where(orders.c.id==orderId))).fetchone()
            conn.execute(orders.update().where(orders.c.id==orderId).values(bagged=1))
            # If you refresh the page and resend data, it'll send 2 confirmation emails. This if statement prevents that.
            if (bagged != 1 and not volunteerEmail==None):
                date, userId = tuple(conn.execute(select([orders.c.date, orders.c.userId]).where(orders.c.id==orderId)).fetchone())
                address = conn.execute(select([users.c.address]).where(users.c.id==userId)).fetchone()[0]
                send_bagged_notification(volunteerEmail[0], orderId, address)
                ordersDict = getOrders(g.user.id)
        elif "barcode" in key:
            print("Text: " + request.form[key])
            baggedIds = request.form[key].split('\r\n')
            for order in baggedIds:
                conn.execute(orders.update().values(bagged=1).where(orders.c.id==order))
    volunteers = getVolunteers()
    today = datetime.date.today()
    checkedInVolunteers = conn.execute(users.select().where(users.c.checkedIn==str(today))).fetchall()
    return render_template("view_all_orders.html", orders=ordersDict, volunteers=volunteers, checkedIn=checkedInVolunteers)

@login_required
@admin_required
@bp.route('/shipping_labels', methods=('GET', 'POST'))
def generate_shipping_labels():
    volunteers = getVolunteers()
    ordersDict = getOrders(g.user.id)
    itemsList = loads(conn.execute(users.select(users.c.id==g.user.foodBankId)).fetchone()['items'])
    html = render_template("shipping-labels.html", orders=ordersDict, volunteers=volunteers)
    # Uncomment this line for debugging
    #return html
    pdf = pdfkit.from_string(html, False)
    response = make_response(pdf)
    response.headers['Content-type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline;'
    return response

# Returns a dictionary where the keys are the order ID's,
# and the values are dicts with attributes about that order (contents, email, etc.)
# All of these should be uncompleted orders, since an order is removed from a volunteer's
# list when it's completed.
def getOrders(adminId):
    # Get the ID's that our volunteer is assigned to
    orderIdList = conn.execute(select([orders.c.id]).where(and_(orders.c.foodBankId==g.user.id, orders.c.completed==0)).order_by(orders.c.date)).fetchall()
    toReturn = OrderedDict() # Sorted by date
    for orderIdProxy in orderIdList:
        orderId = orderIdProxy[0]
        toReturn[orderId] = {}
        order = conn.execute(orders.select().where(orders.c.id==orderId)).fetchone()
        user = conn.execute(users.select().where(users.c.id==order['userId'])).fetchone()
        # Add all our user's attributes to our order
        userColumns = conn.execute(users.select()).keys()
        userColumns.remove('id')
        for column in userColumns:
            toReturn[orderId][str(column)] = str(getattr(user, str(column)))
        # And all our order's attributes
        for column in conn.execute(orders.select()).keys():        
            toReturn[orderId][str(column)] = str(getattr(order, str(column)))
        toReturn[orderId]['itemsDict'] = loads(toReturn[orderId]['contents'])
        volunteerName = conn.execute(select([users.c.name], users.c.id==order.volunteerId)).fetchone()
        if not volunteerName is None:
            toReturn[orderId]['volunteerName'] = volunteerName[0]
            
    return toReturn 

def getVolunteers():
    proxy = conn.execute(users.select(and_(users.c.role=="VOLUNTEER", users.c.approved==True))).fetchall()
    dictList = []
    for volunteer in proxy:
        volunteerDict = {}
        columns = conn.execute(users.select()).keys()
        for column in columns:
            volunteerDict[column] = getattr(volunteer, column)
        volunteerDict['numOrders'] = len(conn.execute(orders.select(and_(orders.c.volunteerId==volunteer.id, orders.c.completed==0))).fetchall())
        dictList.append(volunteerDict)
    return dictList

def barcode_to_base64(orderId):
    imgByteArray = io.BytesIO()
    Code128(str(orderId) + "\n", writer=ImageWriter()).write(imgByteArray)
    return base64.b64encode(imgByteArray.getvalue()).decode()

def qrcode_to_base64(orderId):
    urlString = request.base_url[:-len('shipping_labels')] + 'auto_complete?orderId=' + str(orderId)
    imgByteArray = io.BytesIO()
    code = qrcode.make(urlString)
    code.save(imgByteArray, format="PNG")
    return base64.b64encode(imgByteArray.getvalue()).decode()