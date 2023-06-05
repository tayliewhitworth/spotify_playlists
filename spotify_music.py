import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, redirect, url_for, session
from dotenv import load_dotenv
import os

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
secret_key = os.getenv("SECRET_KEY")

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
app.secret_key = secret_key

TOKEN_INFO = 'token_info'

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)



@app.route('/redirect')
def redirect_page():
    session.clear()
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('create_playlist', _external=True))

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
            return('Playlist Created Successfully!')


    return '''
        <form method="post">
            <label for="playlist_name">Playlist Name:</label>
            <input type="text" id="playlist_name" name="playlist_name" required>
            <input type="submit" value="Create Playlist">
        </form>
    '''



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

app.run(debug=True)
