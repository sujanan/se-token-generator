import sys
import socket
import signal
import requests
import threading
import webbrowser
from abc import ABCMeta, abstractmethod

class HttpVerb:
    GET = 1,
    POST = 2

class Param(object):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def prompt(self):
        raise NotImplementedError

    @abstractmethod
    def input(self):
        raise NotImplementedError

class DefaultValueParam(Param):

    def __init__(self, name, value):
        super(DefaultValueParam, self).__init__(name)
        self.value = value

    def prompt(self):
        pass

    def input(self):
        return self.value

class NoChoiceParam(Param):

    def __init__(self, name):
        super(NoChoiceParam, self).__init__(name)

    def prompt(self):
        return "{}: ".format(self.name)

    def input(self):
        return raw_input(self.prompt()).strip() 

class ChoiceParam(Param):

    def __init__(self, name, choices):
        self.choices = choices 
        super(ChoiceParam, self).__init__(name)

    def prompt(self):
        choices_prompt = ["[{}] {}".format(i, self.choices[i]) for i in range(len(self.choices))]
        return "{} ({}): ".format(self.name, ",".join(choices_prompt))

    def input(self):
        value = raw_input(self.prompt()).strip()
        selected_choices = [self.choices[int(c)] for c in value.split(",")]
        return ",".join(selected_choices)

class Config(object):

    def __init__(self, endpoint, http_verb, params):
        self.endpoint = endpoint
        self.http_verb = http_verb
        self.params = params

    def split_url(self, url, param_values={}):
        for u in url.split("?")[1].split("&"):
            key_and_val = u.split("=")
            key = key_and_val[0]
            val = key_and_val[1]
            for p in self.params:
                if key == p.name:
                    param_values[key] = val
        return param_values 

    def param_values(self, values={}):
        for p in self.params:
            if not p.name in values:
                values[p.name] = p.input()
        return values

    def build_url(self, params):
        formatted_params = ["{}={}".format(key, params[key]) for key in params]
        return "{}?{}".format(self.endpoint, "&".join(formatted_params))

class OauthFlowHandler(object):

    def __init__(self, step1_config, step2_config, step3_config, port=3001):
        self.host = "localhost"
        self.port = port
        self.step1_config = step1_config 
        self.step2_config = step2_config
        self.step3_config = step3_config

    def shutdown(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            pass

    def start(self):
        query_params = self.step1_config.param_values()

        url = self.step1_config.build_url(query_params)
        webbrowser.open(url)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            print("error: Could not bind to port {}".format(self.port))
            self.shutdown()
            sys.exit(1)

        self.socket.listen(5)
        (client, address) = self.socket.accept()    
        client.settimeout(60)

        data = client.recv(1024).decode()
        query_params = self.step2_config.split_url(data.split(" ")[1], query_params)
        client.send(self._generate_headers(200).encode()) 
        client.close()
        
        query_params = self.step3_config.param_values(query_params)
        print(query_params)
        r = requests.post(self.step3_config.endpoint, data=query_params, headers={"content-type": "application/x-www-form-urlencoded"})
        print(r.text.split)

    def _generate_headers(self, response_code):
        header = ""
        if response_code == 200:
            header += "HTTP/1.1 200 OK\n"
        elif response_code == 404:
            header += "HTTP/1.1 404 Not Found\n"

        header += "Connection: close\n\n"
        return header


SETP1 = Config(
        "https://stackoverflow.com/oauth", 
        HttpVerb.GET, 
        [NoChoiceParam("client_id"), DefaultValueParam("redirect_uri", "http://localhost:3001/stackapp"), ChoiceParam("scope", ["read_inbox", "no_expiry", "write_access", "private_info"])])

SETP2 = Config("localhost:3001/stackapp", HttpVerb.GET, [NoChoiceParam("code")])

SETP3 = Config("https://stackoverflow.com/oauth/access_token", HttpVerb.POST, [
        NoChoiceParam("client_id"),
        NoChoiceParam("client_secret"),
        NoChoiceParam("code"),
        NoChoiceParam("redirect_uri")])

oauthFlowHandler = OauthFlowHandler(SETP1, SETP2, SETP3)

def shutdownHandler(sig, unused):
    oauthFlowHandler.shutdown()
    sys.exit(1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdownHandler)
    oauthFlowHandler.start()
