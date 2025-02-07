import datetime
import re
import time

from aiohttp import ClientSession
import requests


class ValorantClientSession(ClientSession):
    """
    Emulates Valorant PC Client 
    """
    def __init__(self):
        super().__init__()
        # Set of headers that Riot Expects from a Val Client to pass with each request
        # Can be captured using Fiddler Capture
        self.riot_headers = {
            "User-Agent": "RiotClient/43.0.1.4195386.4190634 rso-auth (Windows; 10;;Professional, x64)",
            "X-Riot-ClientVersion": ValorantClientSession.get_client_version(),
            # X-Riot-ClientPlatform = base64 string to emulate the following:
            # {
            #     "platformType": "PC",
            #     "platformOS": "Windows",
            #     "platformOSVersion": "10.0.19042.1.256.64bit",
            #     "platformChipset": "Unknown"
            # } 
            "X-Riot-ClientPlatform": "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp"
        }

        self.is_authenticated = None

    # Gets up-to-date version from 3rd party API
    @staticmethod
    def get_client_version():
        client_version = "release-04.05-shipping-23-687347"
        try:
            response = requests.get('https://valorant-api.com/v1/version')
            payload = response.json()
            client_version = payload['data']['riotClientVersion']

        except Exception:
            print(f'Unable to get most recent client version, defaulting to client version: {client_version}')
        
        return client_version

    async def authenticate(self):
        username = input("Username: ")
        password = input("Password: ")
        print("\n")

        try:
            data = {
                "client_id":"play-valorant-web-prod",
                "nonce":"1",
                "redirect_uri":"https://playvalorant.com/opt_in",
                "response_type":"token id_token"
            }
            await self.post('https://auth.riotgames.com/api/v1/authorization', headers=self.riot_headers, json=data)

            data = {
                'type': 'auth',
                'username': username,
                'password': password
            }
            async with self.put('https://auth.riotgames.com/api/v1/authorization', headers=self.riot_headers ,json=data) as r:
                data = await r.json()

            pattern = re.compile('access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)')
            data = pattern.findall(data['response']['parameters']['uri'])[0]
            access_token = data[0]

            self.headers['Authorization'] = str.format(f'Bearer {access_token}')

            async with self.post('https://auth.riotgames.com/userinfo', headers=self.riot_headers, json={}) as r:
                data = await r.json()
            user_id = data['sub']

            async with self.post('https://entitlements.auth.riotgames.com/api/token/v1', headers=self.riot_headers, json={}) as r:
                data = await r.json()
            entitlements_token = data['entitlements_token']
            self.headers['X-Riot-Entitlements-JWT'] = entitlements_token

            self.is_authenticated = True
            self.user_id = user_id

        except Exception as e:
            await self.close()
            raise SystemExit("Incorrect Username / Password")
            
        return self

    # Get [Skin Names] from 3rd party -> transform to a map{uuid: skin name}
    # Normally would be in client's FileSystem 
    @staticmethod
    def get_map_of_skins():
        map_of_all_skins = {}
        
        res = requests.get(f'https://valorant-api.com/v1/weapons/skins')
        payload = res.json()
        
        for weapon in payload['data']:
            base_skin = weapon['levels'][0]
            map_of_all_skins[base_skin['uuid']] = base_skin['displayName']
        
        return map_of_all_skins
           
    # returns ([skin names], expiry time)
    async def get_store(self):
        user_store = []

        local_skins = ValorantClientSession.get_map_of_skins()

        if self.is_authenticated is not True:
            self.authenticate()

        # Get [Skin IDs] from Riot Server
        async with self.get(f'https://pd.na.a.pvp.net/store/v2/storefront/{self.user_id}', headers=self.riot_headers) as r:
            data = await r.json()
            riot_store = data["SkinsPanelLayout"]["SingleItemOffers"]
            expires_in = data["SkinsPanelLayout"]["SingleItemOffersRemainingDurationInSeconds"]
        
        # Correlate [Skin IDs] to local names 
        for skin_id in riot_store:
            skin_name = local_skins[skin_id]
            user_store.append(skin_name)
        
        # get time where store refreshes, in local time
        exp_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        print(user_store, "\n")
        print(f'expires at: {exp_date.strftime("%m-%d-%Y %I:%M:%S")} (Local Time Zone)')
        return (user_store, exp_date)
