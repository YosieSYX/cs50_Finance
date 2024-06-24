import os
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])
    bought = db.execute("SELECT * FROM portfolio WHERE user_id = ?;", session["user_id"])
    cash = rows[0]['cash']
    sum = cash
    # add stock name, add current lookup value, add total value
    for row in bought:
        current = lookup(row['symbol'])
        row['price'] = current['price']
        row['total'] = current['price'] * row['shares']

        # increment sum
        sum += row['total']

    return render_template("index.html", bought=bought, cash=cash, sum=sum)
    # query the api lookup for each symbol for which i own shares
    # multiple the current price(from the lookup) with the total number of shares i own for each stock to get my valuation for each asset
    # sum all my asssets to get my total valuation


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol") or not lookup(request.form.get("symbol")):
            return apology("Enter a symbol")
        if not request.form.get("shares"):
            return apology("Enter a share")
        else:
            symbol = request.form.get("symbol")
            shares = request.form.get("shares")
            try:
                shares = int(shares)
            except ValueError:
                return apology("INVALID SHARES")
            if not (shares > 0):
                return apology("INVALID SHARES")
            dict = lookup(symbol)
            cost = dict['price'] * shares
            rows = db.execute("SELECT * FROm users WHERE id = ?;", session["user_id"])
            cash = rows[0]['cash']
            current_time = datetime.now()
            if cash < cost:
                return apology("not enough money")
            row = db.execute(
                "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?;", session["user_id"], symbol)
            if len(row) == 0:
                db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES (?, ?, ?)",
                           session["user_id"], symbol, shares)
            else:
                oldshares = db.execute(
                    "SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?;", session["user_id"], symbol)
                oldshares = oldshares[0]["shares"]
                # add purchased shares to previous share number
                newshares = oldshares + shares
                # update shares in portfolio table
                db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?;",
                           newshares, session["user_id"], symbol)
            db.execute("UPDATE users SET cash = ? WHERE id = ?;",
                       (rows[0]['cash'] - cost), session["user_id"])
            db.execute("INSERT INTO transactions(user_id, Symbol, Shares, Price, Total, Datetime) VALUES(?, ?, ?, ?, ?, ?);",
                       session["user_id"], symbol, shares, dict['price'], cost, current_time)
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])
    history = db.execute("SELECT * FROM transactions WHERE user_id = ?;", session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Ensure Symbol is exists
        if not (lookup(request.form.get("symbol"))):
            return apology("INVALID SYMBOL")
        else:
            query = lookup(request.form.get("symbol"))
            return render_template("quoted.html", query=query)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation ")
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Ensure confirmation is the same as password
        if password != confirmation:
            return apology("Password and Confirmation does not match")
        count = db.execute("SELECT username FROM users WHERE username = ?;", name)
        # ensure the username does not already exist
        if len(count) != 0:
            return apology("username already exists")
        # Insert username into database
        id = db.execute("INSERT INTO users (username, hash, cash) VALUES (?, ?, ?);",
                        name, generate_password_hash(password), 10000)
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)
        rows = db.execute("SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?;",
                          session["user_id"], symbol)
        # return apology if symbol not owned
        if len(rows) != 1:
            return apology("must provide valid stock symbol")

        # return apology if shares not provided
        if not shares:
            return apology("must provide number of shares")

        # current shares of this stock
        oldshares = rows[0]['shares']
        shares = int(shares)
        if shares > oldshares:
            return apology("too much")
        # get current value of stock price times shares
        sold = quote['price'] * shares
        # add value of sold stocks to previous cash balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?;", session['user_id'])
        cash = cash[0]['cash']
        cash = cash + sold
        # update cash balance in users table
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", cash, session["user_id"])
        # subtract sold shares from previous shares
        newshares = oldshares - shares
        # get current time
        current_time = datetime.now()
        # if shares remain, update portfolio table with new shares
        if newshares > 0:
            db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?;",
                       newshares, session["user_id"], symbol)
        else:
            db.execute("DELETE FROM portfolio WHERE symbol = ? AND user_id = ?;",
                       symbol, session["user_id"])
        # update history table
        db.execute("INSERT INTO transactions (user_id, Symbol, Shares, Price, Datetime) VALUES (?, ?, ?, ?, ?);",
                   session["user_id"], symbol, 0-shares, quote['price'], current_time)

        # redirect to index page
        return redirect("/")
    else:
        current = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?;", session["user_id"])
        return render_template("sell.html", current=current)
