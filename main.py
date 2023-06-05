from dotenv import load_dotenv
import os
import base64
from requests import post
import json
from requests import get

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")

def get_token():
    url = 'https://accounts.spotify.com/api/token'
    auth_string = client_id + ':' + client_secret
    auth_string_bytes = auth_string.encode('utf-8')
    auth_string_b64 = str(base64.b64encode(auth_string_bytes), 'utf-8')

    headers = {
        'Authorization': 'Basic ' + auth_string_b64,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        'grant_type': 'client_credentials'
    }

    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result['access_token']
    return token

def get_auth_header(token):
    return {
        'Authorization': 'Bearer ' + token
    }

def search_for_artist(token, artist_name):
    url = 'https://api.spotify.com/v1/search'
    headers = get_auth_header(token)
    data = {
        'q': artist_name,
        'type': 'artist',
        'limit': 1
    }
    result = get(url, headers=headers, params=data)
    json_result = json.loads(result.content)
    if len(json_result['artists']['items']) == 0:
        print('No artist found')
        return None
    artist_id = json_result['artists']['items'][0]['id']
    return artist_id

search_name = input('Enter artist name: ')
artist_id = search_for_artist(access_token, search_name)

def get_songs_by_artist(token, artist_id):
    url = 'https://api.spotify.com/v1/artists/' + artist_id + '/top-tracks'
    headers = get_auth_header(token)
    data = {
        'country': 'US'
    }
    result = get(url, headers=headers, params=data)
    json_result = json.loads(result.content)
    songs = []
    for track in json_result['tracks']:
        songs.append(track['name'])
    return songs

songs = get_songs_by_artist(access_token, artist_id)
for idx, song in enumerate(songs):
    print(f'{idx+1}. {song}')

