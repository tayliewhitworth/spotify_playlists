import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, redirect, url_for, session, render_template
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
    # work on this function and fix it - where I left off
    try:
        token_info = get_token()
    except:
        print('User not logged in')
        return redirect('/')

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']
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
