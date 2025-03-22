import logging
from typing import Optional

import aiohttp


class LianderAPI:
    API_VERSION = "v1"
    API_LOGIN_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
        API_VERSION}/auth/login"
    API_AANSLUITINGEN_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
        API_VERSION}/aansluitingen"
    API_ME_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
        API_VERSION}/profielen/me"
    API_AANVRAAGGEGEVENS_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
        API_VERSION}/aanvraaggegevens"
    API_STORING_URL = "https://services1.arcgis.com/v6W5HAVrpgSg3vts/ArcGIS/rest/services/IStoringen_Productie_V7/FeatureServer/0/query?outFields=*&f=json&where=STORING_STATUS%20%3C%3E%20%27opgelost%27%20AND%20(STORING_GETROFFEN_POSTCODES%20LIKE%20%27%251741%20JB%25%27%20OR%20STORING_GETROFFEN_POSTCODES%20=%20%271741%27%20OR%20STORING_GETROFFEN_POSTCODES%20LIKE%20%271741;%25%27%20OR%20STORING_GETROFFEN_POSTCODES%20LIKE%20%27%25;1741%27%20OR%20STORING_GETROFFEN_POSTCODES%20LIKE%20%27%25;1741;%25%27)"
    API_AANSLUITING_URL = "https://mijn-liander-gateway.web.liander.nl/aansluitingen/aansluiting/871685920003629897"

    def __init__(self, username: str, password: str, session: Optional[aiohttp.ClientSession] = None):
        """
        Initializes the Liander API object.

        :param username: Username for authentication.
        :param password: Password for authentication.
        :param session: Optional aiohttp session.
        """
        self.username = username
        self.password = password
        self.session = session or aiohttp.ClientSession()
        self.jwt = None
        self.token = None
        self.refresh_token = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Set up console handler for logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    async def _authenticate(self) -> None:
        """
        Authenticates with the Liander API and stores the token.

        :raises Exception: If authentication fails.
        """
        try:
            self.logger.debug("Authenticating with the Liander API.")
            async with self.session.post(
                self.API_LOGIN_URL,
                json={"username": self.username, "password": self.password}
            ) as response:
                self.logger.debug("Request: %s %s",
                                  response.method, response.url)
                self.logger.debug("Request headers: %s",
                                  response.request_info.headers)
                self.logger.debug("Request body: %s", self.session)

                status = response.status
                response_text = await response.text()
                self.logger.debug("Response status: %s", status)
                self.logger.debug("Response body: %s", await response.json())
                response.raise_for_status()

                if status == 200:
                    data = await response.json()
                    self.jwt = data.get("jwt")
                    # if self.jwt:
                    #     self.logger.debug("Response jwt_token: %s", self.jwt)
                    self.token = data.get("access_token") or self.jwt
                    self.refresh_token = data.get("refreshToken")
                    # if self.token:
                    #     self.logger.debug("Response token: %s", self.token)
                    self.session.headers.update(
                        {"Authorization": f"Bearer {self.jwt}"})
                    self.logger.info(
                        "Successfully authenticated with Liander API.")
                else:
                    self.logger.error(
                        "Authentication failed with status code %s: %s", status, response_text)
                    raise Exception(f"Authentication failed: {status}")
        except aiohttp.ClientError as err:
            self.logger.error("Error during authentication: %s", err)
            raise Exception(f"Authentication error: {err}")

    async def _refresh_token(self) -> None:
        """
        Refreshes the authentication token if needed.
        """
        if self.token is None:
            self.logger.debug("Token is missing. Authenticating again.")
            await self._authenticate()

    async def _fetch_data(self, url: str) -> dict:
        """
        Fetches data from a given URL and logs details.

        :param url: The API endpoint URL.
        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        await self._refresh_token()
        try:
            self.logger.debug("Fetching data from URL: %s", url)
            async with self.session.get(url) as response:
                self.logger.debug("Request: %s %s",
                                  response.method, response.url)
                self.logger.debug("Request headers: %s",
                                  response.request_info.headers)

                status = response.status
                response_text = await response.text()
                self.logger.debug("Response status: %s", status)
                self.logger.debug("Response body: %s", response_text)

                if status == 200:
                    return await response.json()
                else:
                    self.logger.error(
                        "Failed to fetch data with status code %s: %s", status, response_text)
                    raise Exception(f"Failed to fetch data: {status}")
        except aiohttp.ClientError as err:
            self.logger.error("Error fetching data from %s: %s", url, err)
            raise Exception(f"Error fetching data: {err}")

    async def fetch_aansluitingen(self) -> dict:
        """
        Fetches aansluitingen data from the Liander API.

        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        return await self._fetch_data(self.API_AANSLUITINGEN_URL)

    async def fetch_profile(self) -> dict:
        """
        Fetches user profile data from the Liander API.

        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        return await self._fetch_data(self.API_ME_URL)

    async def fetch_aanvraaggegevens(self) -> dict:
        """
        Fetches aanvraaggegevens from the Liander API.

        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        return await self._fetch_data(self.API_AANVRAAGGEGEVENS_URL)

    async def fetch_storing(self) -> dict:
        """
        Fetches storing data from the external service.

        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        return await self._fetch_data(self.API_STORING_URL)

    async def fetch_aansluiting(self) -> dict:
        """
        Fetches specific aansluiting data from the Liander API.

        :return: Parsed JSON response.
        :raises Exception: If the request fails.
        """
        return await self._fetch_data(self.API_AANSLUITING_URL)

    async def log_out(self) -> None:
        """
        Logs out from the Liander API by invalidating the session.
        """
        try:
            self.logger.debug("Logging out from the Liander API.")
            logout_url = f"https://mijn-liander-gateway.web.liander.nl/api/{
                self.API_VERSION}/auth/logout"
            async with self.session.post(logout_url) as response:
                self.logger.debug("Request: %s %s",
                                  response.method, response.url)
                self.logger.debug("Request headers: %s",
                                  response.request_info.headers)

                status = response.status
                response_text = await response.text()
                self.logger.debug("Response status: %s", status)
                if response_text:
                    self.logger.debug("Response body: %s", response_text)

                if status in (200, 204):
                    self.logger.info("Successfully logged out.")
                else:
                    self.logger.warning(
                        "Failed to log out with status code %s: %s", status, response_text)
        except aiohttp.ClientError as err:
            self.logger.error("Error during logout: %s", err)
        finally:
            await self.session.close()
            self.token = None
            self.logger.debug("Session closed.")
