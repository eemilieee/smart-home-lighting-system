from machine import ADC, Pin
import time
import network
import requests

# date despre wi-fi
SSID = "wifi-arp"
PASSWORD = "acasa123"

# date despre server-ul flask
SERVER_IP = "192.168.0.243"
SERVER_PORT = 5000
URL = f"http://{SERVER_IP}:{SERVER_PORT}/submit"

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
    response = requests.post(url, json=data)
    print('Response status code:', response.status_code)
    print('Response text:', response.text)
    response.close()

wlan = connect_to_wifi(SSID, PASSWORD)

if wlan.isconnected():

    ldr = LDR(39)

    while True:
        value = ldr.value()
        print('Light intensity value = {}'.format(value))
        
        payload = {"light_intensity": int(value)}
        send_post_request(URL, payload)

        time.sleep(60)
