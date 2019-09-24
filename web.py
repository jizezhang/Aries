import requests
import logging
import contextlib
from io import BytesIO
from .storage import StorageObject
from lxml import etree
from urllib import request
logger = logging.getLogger(__name__)


class WebAPI:
    """Provides method to access web API.

    This class uses python requests package.
    See https://2.python-requests.org/en/master/user/advanced/#request-and-response-objects

    Attributes:
        base_url: The base URL for all API endpoint.
        If base_url is specified, relative URL can be used to make requests.
        Relative URL will be appended to base URL when making the requests.
    
    """
    def __init__(self, base_url="", **kwargs):
        self.kwargs = kwargs
        self.headers = {}

        base_url = base_url
        if base_url.startswith("http://") or base_url.startswith("https://"):
            self.base_url = base_url
        else:
            raise ValueError("Base URL should start with http:// or https://")

    def add_header(self, **kwargs):
        self.headers.update(kwargs)

    def get(self, url, **kwargs):
        """Makes a get request.
        Use keyword arguments to specify the query strings in the request.
        
        Args:
            url (str): The URL/Endpoint of the API.
                This can be a relative URL if base_url is specified in initialization.
        
        Returns: A Response Object
        """
        url = self.build_url(url, **kwargs)
        logger.debug("Requesting data from %s" % url)
        response = requests.get(url, headers=self.headers)
        logger.debug("Response code: %s" % response.status_code)
        return response

    def get_json(self, url, **kwargs):
        return self.get(url, **kwargs).json()

    def post(self, url, data, **kwargs):
        url = self.build_url(url, **kwargs)
        logger.debug("Posting data to %s" % url)
        response = requests.post(url, json=data, headers=self.headers)
        logger.debug("Response code: %s" % response.status_code)
        return response

    def post_json(self, url, data, **kwargs):
        return self.post(url, data, **kwargs).json()

    def delete(self, url, **kwargs):
        url = self.build_url(url, **kwargs)
        logger.debug("Deleting data from %s" % url)
        response = requests.delete(url, headers=self.headers)
        return response

    def build_url(self, url, **kwargs):
        """Builds the URL/Endpoint for a request.
        Keyword arguments are converted to query string in the URL.
        
        Args:
            url (str): The URL/Endpoint of the API.
            If url is relative url, it will be appended to the base_url.
            If url is absolute URL (starts with https:// or http://), the base_url will be ignored.
        
        Returns:
            str: The absolute URL/Endpoint of the API with query string.
        """
        url = url
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "%s%s" % (self.base_url, url)
        query_dict = self.kwargs.copy()
        query_dict.update(kwargs)
        return self.append_query_string(url, **query_dict)
    
    @staticmethod
    def append_query_string(url, **kwargs):
        """Appends query string to a URL

        Query string is specified as keyword arguments.
        
        Args:
            url (str): URL
        
        Returns:
            str: URL with query string.
        """
        if kwargs and "?" not in url:
            url += "?"
        for key, val in kwargs.items():
            if "?" not in url:
                url += "?"
            url += "&%s=%s" % (key, val)
        return url


class HTML:
    def __init__(self, uri):
        self.uri = uri

    def read(self):
        obj = StorageObject(self.uri)
        if obj.scheme in ["http", "https"]:
            r = requests.get(self.uri)
            content = r.content
        else:
            with open(self.uri, 'r') as f:
                content = f.read()
        return content

    @staticmethod
    def __tags_to_list(parent, tag):
        elements = parent.findall(".//%s" % tag)
        if not elements:
            return None
        results = []
        for element in elements:
            text = element.text if element.text else ""
            results.append(text + ''.join(etree.tostring(e).decode() for e in element))
        return results

    @staticmethod
    def __append_data(to_list, parent, tag):
        data = HTML.__tags_to_list(parent, tag)
        if data:
            to_list.append(data)

    def get_tables(self):
        """Gets the data of of HTML tables in the web page as a list of dictionary.
        
        Returns:
            list: A list of dictionary, each contain data from a table in the web page.
            Each dictionary has two keys: "headers" and "data".
            Both "headers" and "data" are 2D lists.
        """
        content = self.read()
        html = etree.parse(BytesIO(content), etree.HTMLParser())
        html_tables = html.findall('.//table')
        data_tables = []
        
        for html_table in html_tables:
            table = {
                "headers": [],
                "data": []
            }
            rows = html_table.findall(".//tr")
            for row in rows:
                self.__append_data(table["headers"], row, "th")
                self.__append_data(table["data"], row, "td")
            data_tables.append(table)
        return data_tables

# # Use requests package to download via HTTP
# def download(url, file_path):
#     response = requests.get(url, stream=True)
#     if response.status_code != 200:
#         return response.status_code
#     logger.debug("Response code: %s" % response.status_code)
#     logger.debug("Downloading data from %s" % url)
#     with open(file_path, 'wb') as f:
#         for chunk in response.iter_content(chunk_size=1024):
#             if chunk:
#                 f.write(chunk)
#     logger.debug("Data saved to %s" % file_path)
#     return response.status_code


def download(url, file_path):
    """Downloads a file from a URL response.

    Args:
        url (str): The URL of the file to be downloaded.
        file_path (str): The path to store the file.

    Returns: None

    """
    url_response = request.urlopen(url)
    with open(file_path, 'wb') as out_file:
        with contextlib.closing(url_response) as fp:
            logger.debug("Downloading data from %s" % url)
            block_size = 1 << 16
            while True:
                block = fp.read(block_size)
                if not block:
                    break
                out_file.write(block)
