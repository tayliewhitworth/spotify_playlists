import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, redirect, url_for, session, render_template
from dotenv import load_dotenv
import os
import random
from string import ascii_uppercase
from flask_socketio import SocketIO, emit, join_room, leave_room, send

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
secret_key = os.getenv("SECRET_KEY")

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
app.secret_key = secret_key
socketio = SocketIO(app)

rooms = {}

TOKEN_INFO = 'token_info'

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)


@app.route('/redirect')
def redirect_page():
    session.clear()
    code = request.args.get('code')
    spotify_oauth = create_spotify_oauth()
    # token_info = create_spotify_oauth().get_access_token(code)
    token_info = spotify_oauth.get_cached_token()

    if token_info is None:
        token_info = spotify_oauth.refresh_access_token(code)


    session[TOKEN_INFO] = token_info
    return redirect(url_for('playlists', _external=True))

@app.route('/playlists')
def playlists():
    try:
        token_info = get_token()
    except:
        print('User not logged in')
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    playlists = sp.current_user_playlists()['items']
    playlist_names = [playlist['name'] for playlist in playlists]
    return render_template('playlists.html', playlists=playlist_names)

@app.route('/playlist/<playlist_name>')
def playlist(playlist_name):
    try:
        token_info = get_token()
    except:
        print('User not logged in')
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    playlists = sp.current_user_playlists()['items']
    playlist_id = None
    for playlist in playlists:
        if playlist['name'] == playlist_name:
            playlist_id = playlist['id']
            break
    if not playlist_id:
        return '''
            <script>
                alert('Playlist not found!');
                window.location.href = '/playlists';
            </script>
        '''
    tracks = sp.playlist_tracks(playlist_id)['items']
    track_names = [track['track']['name'] for track in tracks]
    return render_template('playlist.html', playlist_name=playlist_name, tracks=track_names)

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    try:
        token_info = get_token()
    except:
        print('User not logged in')
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']
    user_response = ''

    bot_questions = {
        'artist': 'Who is your favorite artist?',
        'genre': 'What is your favorite genre?',
        'song': 'What is your favorite song?',
        'confirm': 'Would you like to save these tracks to a new playlist called: My Favorites?'
    }

    if 'chatbot_state' not in session:
        session['chatbot_state'] = 'artist'

    if request.method == 'POST':
        user_response = request.form.get('user_response')
        session['chatbot_responses'][session['chatbot_state']] = user_response

        if session['chatbot_state'] == 'song':
            seed_artist = sp.search(q='artist:' + session['chatbot_responses']['artist'], type='artist')['artists']['items'][0]['id']
            seed_genre = session['chatbot_responses']['genre']
            seed_track = sp.search(q='track:' + session['chatbot_responses']['song'], type='track')['tracks']['items'][0]['id']

            recommendations = sp.recommendations(seed_artists=[seed_artist], seed_genres=[seed_genre], seed_tracks=[seed_track], limit=10)

            session['recommended_tracks'] = [track['id'] for track in recommendations['tracks']]
            session['chatbot_state'] = 'confirm'

        elif session['chatbot_state'] == 'confirm' and user_response.lower() in ['yes', 'y']:
            user_playlists = sp.current_user_playlists()['items']
            playlist_id = None
            for playlist in user_playlists:
                if playlist['name'] == 'My Favorites':
                    playlist_id = playlist['id']
                    break
            if not playlist_id:
                new_playlist = sp.user_playlist_create(user_id, 'My Favorites', public=True)
                playlist_id = new_playlist['id']

            sp.user_playlist_add_tracks(user_id, playlist_id, session['recommended_tracks'])

            session.pop('chatbot_state')
            session.pop('chatbot_responses')
            session.pop('recommended_tracks')

            return redirect(url_for('playlists', _external=True))
        
        elif session['chatbot_state'] == 'confirm' and user_response.lower() in ['no', 'n']:
            session.pop('chatbot_state')
            session.pop('chatbot_responses')
            session.pop('recommended_tracks')

            return redirect(url_for('playlists', _external=True))
        else:
            session['chatbot_state'] = 'genre' if session['chatbot_state'] == 'artist' else 'song'

    if 'chatbot_responses' not in session:
        session['chatbot_responses'] = {}

    bot_question = bot_questions[session['chatbot_state']]

    return render_template('chatbot.html', bot_question=bot_question, user_response=user_response)


@app.route('/createplaylist', methods=['GET', 'POST'])
def create_playlist():
    try:
        token_info = get_token()
    except:
        print('User not logged in')
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']

    if request.method == 'POST':
        playlist_name = request.form.get('playlist_name')
        if playlist_name:
            current_user_playlists = sp.current_user_playlists()['items']
            for playlist in current_user_playlists:
                if playlist['name'] == playlist_name:
                    return '''
                        <script>
                            alert('Playlist already exists!');
                            window.location.href = '/createplaylist';
                        </script>
                    '''
            sp.user_playlist_create(user_id, playlist_name, True)
            return redirect(url_for('playlists', _external=True))


    return render_template('createplaylist.html')

@app.route('/chatrooms', methods=['GET', 'POST'])
def chatrooms():
    session.clear()
    if request.method == "POST":
        name = request.form.get('name')
        code = request.form.get('code')
        join = request.form.get('join', False)
        create = request.form.get('create', False)

        if not name:
            return render_template('chatrooms.html', error='Please enter a name to continue', code=code, name=name)
        
        if join != False and not code:
            return render_template('chatrooms.html', error='Please enter a room code to continue', code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {'members': 0, 'messages': []}
        elif code not in rooms:
            return render_template('chatrooms.html', error='Room does not exist', code=code, name=name)
        
        session['name'] = name
        session['room'] = room
        return redirect(url_for('chatroom', _external=True))
    
    return render_template('chatrooms.html')

@app.route('/chatroom')
def chatroom():
    room = session.get('room')
    if room is None or session.get('name') is None or room not in rooms:
        return redirect(url_for('chatrooms', _external=True))
    
    return render_template('chatroom.html', code=room, messages=rooms[room]['messages'])

@socketio.on('message')
def message(data):
    room = session.get('room')
    if room not in rooms:
        return
    
    content = {
        'name': session.get('name'),
        'message': data['data'],
    }
    send(content, to=room)
    rooms[room]['messages'].append(content)
    print(f'{session.get("name")} said: {data["data"]}')

@socketio.on('connect')
def connect(auth):
    room = session.get('room')
    name = session.get('name')
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({'name': name, 'message': f'{name} has joined the room'}, to=room)
    rooms[room]['members'] += 1
    print(f'{name} has joined the room {room}')

@socketio.on('disconnect')
def disconnect():
    room = session.get('room')
    name = session.get('name')
    leave_room(room)

    if room in rooms:
        rooms[room]['members'] -= 1
        if rooms[room]['members'] <= 0:
            del rooms[room]


    send({'name': name, 'message': f'{name} has left the room'}, to=room)
    print(f'{name} has left the room {room}')



def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        redirect(url_for('login', _external=False))

    now = int(time.time())

    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        token_info = create_spotify_oauth().refresh_access_token(token_info['refresh_token'])

    return token_info


def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=url_for('redirect_page', _external=True),
        scope="user-library-read playlist-modify-public playlist-read-private",
        cache_path='token.txt'
    )

def generate_unique_code(length):
    while True:
        code = ''
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        if code not in rooms:
            break

    return code

# app.run(debug=True)
if __name__ == '__main__':
    socketio.run(app, debug=True)