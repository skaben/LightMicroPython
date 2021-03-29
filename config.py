import machine
from network import WLAN
from ubinascii import hexlify

ENV = 'dev'  

cfg = {
    'broker_ip': '192.168.137.1',
    'client_id': hexlify(machine.unique_id()),
    'mac': hexlify(WLAN().config('mac')),
    'last_message': 0,
    'message_interval': 5,
    'counter': 0,
    'wlan_ssid': 'ArmyDep',  
    'wlan_password': 'z0BcfpHu',
    'quant_num': 50, 
    'port': 1883,
    'user': b'mqtt',
    'password': b'skabent0mqtt',
    'redK': 0.75,
    'greenK': 0.95,
    'blueK' : 1.0
}

colorTbl = {
    'red': 0.75,
    'green': 0.95,
    'blue': 1.0
}

pins = {
    'red': machine.Pin(15, machine.Pin.OUT),
    'green': machine.Pin(13, machine.Pin.OUT),
    'blue': machine.Pin(12, machine.Pin.OUT),
    'STR': machine.Pin(14, machine.Pin.OUT),  
    'LGT': machine.Pin(4, machine.Pin.OUT)  
}

topics = {
    'sub': b'RGB',
    'pub': b'RGBASK',
    'pub_id': b'RGBASK/' + cfg['mac'],
    'sub_id': b'RGB/' + cfg['mac']
}



