from flask import render_template, flash, redirect, url_for, request, jsonify
import requests
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, RequestForm, ReviewForm
from flask_login import current_user, login_user
from app.models import User, Pair, History, Review
from flask_login import logout_user, login_required
from werkzeug.urls import url_parse
from config import Config, API_KEY

#for record last visit time:
from datetime import datetime

@app.route('/')
@app.route('/index')
@login_required
def index():
    form = RequestForm()
    user = {}
    reviews = []
    return render_template('index.html', title='Home', reviews=reviews, form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    history = History.query.filter(History.user_id == user.id)
    sorted_history = history.order_by(History.time.desc())
    page = request.args.get('page', 1, type=int)
    reviews = current_user.reviews.paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('user',username=current_user.username, page=reviews.next_num) \
        if reviews.has_next else None
    prev_url = url_for('user', username=current_user.username, page=reviews.prev_num) \
        if reviews.has_prev else None
    return render_template('user.html', user=user, reviews=reviews.items, historys = sorted_history, next_url=next_url, prev_url=prev_url)


#For recording last visit time
@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


## FOR USER TO EDIT A PROF
@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)

## DOES API LOOKUP
@app.route('/pairs', methods=['POST','GET'])
def apiLookup():
    form = RequestForm()
    if form.validate_on_submit():
        wine = form.wine.data.title()
        food = form.food.data.title()
    else:
        return render_template("pairings.html", food = "Invalid entry", empty = "empty")

    if wine != "":
        url = "https://api.spoonacular.com/food/wine/dishes?wine=" + wine  + "&apiKey=" + API_KEY
        response = requests.get(url)
        foodpairings = list()
        if u'pairings' in response.json():
            for x in response.json()[u'pairings']:
                foodpairings.append(x.title())
        print(foodpairings)
        if not foodpairings:
            return render_template("pairings.html", wine = wine, empty = "empty")
        text = ""
        if u'text' in response.json():
            text = response.json()[u'text']
        return render_template("pairings.html", wine = wine, text = text, foodpairings = foodpairings)
    else:
        url = "https://api.spoonacular.com/food/wine/pairing?food=" + food + "&apiKey=" + API_KEY
        response = requests.get(url)
        winepairings = list()
        if u'pairedWines' in response.json():
            for x in response.json()[u'pairedWines']:
                winepairings.append(x.title())
        print(winepairings)
        if not winepairings:
            return render_template("pairings.html", food = food, empty = "empty")
        text = ""
        if u'pairingText' in response.json():
            text = response.json()[u'pairingText']
        return render_template("pairings.html", food = food, text = text, winepairings = winepairings)

## CALLED FROM JS AFTER USER PRESSES A PAIR
@app.route('/history')
@login_required
def history():
    wine = request.args.get('wine', 1)
    food = request.args.get('food', 1)

    print("food:" + food)
    print("wine:" + wine)

    ##Check if pairing already exists
    checkEntry = Pair.query.filter(Pair.wine == wine, Pair.food == food)
    if (len(checkEntry.all()) > 0):
        ## if already exists
        pair = checkEntry[0]
    else:
        pair = Pair(wine = wine, food = food)
        db.session.add(pair)
        db.session.commit()

    ## FIX FAVORITE THING ValidationError
    #add pairing to History
    u = User.query.get(current_user.id)
    print("id: " + u.username)
    #change favorites to be variable?
    history = History(pairing = pair, user = u)
    db.session.add(history)
    db.session.commit()
    print('added history??')
    print(pair.id)

    return jsonify({'pairid': pair.id})

@app.route('/pairing/<id>', methods=['GET', 'POST'])
@login_required
def pairing(id):

    pairings = History.query.filter(History.user_id == current_user.id)
    show_rating = True
    q = History.query.filter(History.user_id == current_user.id, History.pair_id == id).first()
    if q == None:
         show_rating = False

    form = ReviewForm()
    if form.validate_on_submit():
        review = Review(body = form.review.data, rating = form.rate.data, author = current_user, pairing = Pair.query.get(id))
        db.session.add(review)
        db.session.commit()

    pair = Pair.query.filter_by(id = id).first_or_404()
    reviews = Review.query.filter(Review.pair_id == id)

    page = request.args.get('page', 1, type=int)
    limited_reviews = reviews.paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('pairing',id=id, page=limited_reviews.next_num) \
        if limited_reviews.has_next else None
    prev_url = url_for('pairing',id=id, page=limited_reviews.prev_num) \
        if limited_reviews.has_prev else None

    return render_template('pair.html', pair=pair, reviews=limited_reviews.items, form = form, show = show_rating, next_url=next_url, prev_url=prev_url)
