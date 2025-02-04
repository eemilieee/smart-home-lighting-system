from machine import ADC, Pin
import time
import network
import urequests
import socket
import ssl
import ujson

# date despre wi-fi
SSID = "wifi-arp"
PASSWORD = "acasa123"

# date despre server-ul flask
SERVER_IP = "192.168.0.243"
SERVER_PORT = 5000
URL = f"https://{SERVER_IP}:{SERVER_PORT}/submit"

class LDR:

    def __init__(self, pin):
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_6DB)

    def read(self):
        return self.adc.read()

    def value(self):
        return 100 * self.read() / 4095

def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    
    while not wlan.isconnected():
        print('Connecting to network...')
        time.sleep(1)
        
    print('Network config:', wlan.ifconfig())
    return wlan

def send_post_request(url, data):
    response = urequests.post(url, json=data)
    print('Response status code:', response.status_code)
    print('Response text:', response.text)
    response.close()
    
def connect_to_socket():
    addr = socket.getaddrinfo(SERVER_IP, SERVER_PORT)[0][-1]

    sock = socket.socket()
    sock.connect(addr)
    sock = ssl.wrap_socket(sock)
    
    return sock
    
def send_to_socket(sock, data):
    json_data = ujson.dumps(data)
    packet = (
        f"POST /submit HTTP/1.1\r\n"
        f"Host: {SERVER_IP}:{SERVER_PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(json_data)}\r\n"
        f"\r\n"
        f"{json_data}"
    )

    sock.write(packet.encode('utf-8'))
    resp = sock.readline().decode('utf-8').strip()
    print(resp)
    

wlan = connect_to_wifi(SSID, PASSWORD)

if wlan.isconnected():

    ldr = LDR(39)

    while True:
        value = ldr.value()
        print('Light intensity value = {}'.format(value))
        
        payload = {"light_intensity": int(value)}
        # send_post_request(URL, payload)

        sock = connect_to_socket()
        send_to_socket(sock, payload)
        sock.close()

        time.sleep(60)
