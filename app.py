from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import pickle
import pandas as pd
import random
import os
import requests

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import urllib.parse  # For URL encoding

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database("your_database_name")
collection = db["your_collection_name"]

# Test connection
try:
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB!")
except Exception as e:
    print(f"❌ Connection failed: {e}")


# Load the pickled files
movies_list = pd.compat.pickle_compat.load(open(r'movie_list.pkl', 'rb'))
similarity = pd.compat.pickle_compat.load(open(r'similarity.pkl', 'rb'))
popularity_models = pd.compat.pickle_compat.load(open(r'popularity_models.pkl', 'rb'))

# Convert movies list to DataFrame
movies_df = movies_list

# TMDB API Key
TMDB_API_KEY = "c1f2ed1b9413000a1a7141f5db0b80ca"

# Function to recommend movies
def recommend_movie(movie_title):
    try:
        index = movies_df[movies_df['title'] == movie_title].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
        recommendations = [movies_df.iloc[i[0]] for i in distances[1:6]]  # Exclude the first (itself)
        return recommendations
    except IndexError:
        return ["Movie not found! Please try another title."]

# Function to fetch movie posters
def fetch_poster(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=c1f2ed1b9413000a1a7141f5db0b80ca&language=en-US"
        data = requests.get(url, timeout=5)
        data.raise_for_status()
        poster_path = data.json().get('poster_path')
        return f"https://image.tmdb.org/t/p/w500/{poster_path}" if poster_path else None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching poster: {e}")
        return None


# Home Page
@app.route('/')
def home():
    if 'user' in session:
        random_movies = []
        random_movie_titles = random.sample(list(movies_df['title']), 36)

        for title in random_movie_titles:
            movie = movies_df[movies_df['title'] == title].iloc[0]
            movie_id = movie['movie_id']
            poster = fetch_poster(movie_id)
            random_movies.append({'title': title, 'poster': poster})

        return render_template('index.html', random_movies=random_movies, user=session['user'])
    flash("Please login to access the movie recommendation system.", "error")
    return redirect(url_for('login'))

# Recommendation Route
@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if 'user' not in session:
        flash("Please login to access this feature.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        movie_name = request.form['movie_name']
        recommendations = recommend_movie(movie_name)
        recommended_movie_posters = []

        for movie in recommendations:
            movie_id = movie['movie_id']
            poster = fetch_poster(movie_id)
            recommended_movie_posters.append({'title': movie['title'], 'poster': poster})

        return render_template('recommend.html', recommendations=recommended_movie_posters, movie_titles=movies_df['title'].values)

    return render_template('recommend.html', movie_titles=movies_df['title'].values)

# Popular Movies Route
@app.route('/popular', methods=['GET', 'POST'])
def popular():
    if 'user' not in session:
        flash("Please login to access this feature.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        selected_year = int(request.form['year'])
        popular_movies = popularity_models.get(selected_year, pd.DataFrame())
        movie_details = []

        for _, movie in popular_movies.iterrows():
            poster = fetch_poster(movie['id'])
            movie_details.append({'title': movie['original_title'], 'poster': poster, 'popularity': movie['popularity']})

        return render_template('popular.html', years=popularity_models.keys(), movies=movie_details, selected_year=selected_year)

    return render_template('popular.html', years=popularity_models.keys(), movies=[], selected_year=None)

# Register Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if the user already exists
        if users_collection.find_one({'email': email}):
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))

        # Insert the new user into MongoDB with hashed password
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({'name': name, 'email': email, 'password': hashed_password})
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find the user in MongoDB
        user = users_collection.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user'] = user['name']  # Store user's name in session
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password!', 'error')

    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
