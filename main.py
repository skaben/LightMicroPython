import machine
import time
import ujson
import network
import urandom
import umqttsimple
import config
import webrepl

pwm = dict()
ping_msg = b''

hostName = b'Light' + config.cfg['client_id']

station = network.WLAN(network.STA_IF)
station.active(True)
station.config(dhcp_hostname=hostName)


def wifi_init():
    station.active(True)
    station.config(dhcp_hostname=hostName)
    station.connect(config.cfg['wlan_ssid'], config.cfg['wlan_password'])
    while station.isconnected() == False:
        for x in range(6):
            pwm['red'].duty(1023)
            time.sleep(.25)
            pwm['red'].duty(0)
            time.sleep(.25)
    print('Connection successful')
    print(station.ifconfig())
    webrepl.start()


def randint(min, max):
    span = int(max) - int(min) + 1
    div = 0x3fffffff // span
    offset = urandom.getrandbits(30) // div
    val = int(min) + offset
    return val


def reset_out():
    config.pins['STR'].value(0)
    config.pins['LGT'].value(0)
    try:
        for color in pwm:
            pwm[color].duty(0)
    except:
        print('cannot set PWM, check config:\n{}'.format(pwm))
        return None


def set_pwm():
    try:
        for color in pwm:
            pwm[color].duty(int(manage_seq['RGB'][color]*config.colorTbl[color]))
    except:  # noqa
        print('cannot set PWM, check config:\n{}'.format(pwm))
        return None


def _hex(slice: str):
    return int(int(slice, 16) * 4)


def create_peripheral():
    peripheral_dict = {
        'len': 0,
        'mode': '',
        'onoff': [],
        'time_static': [],
        'time_current': 0,
        'time_slice': 0,
        'count': 0,
        'last': 0,
        'current_command': []
    }
    return peripheral_dict


manage_seq = dict()
manage_seq['LGT'] = create_peripheral()
manage_seq['STR'] = create_peripheral()
manage_seq['RGB'] = create_peripheral()

manage_seq['RGB'].update({
            'mqtt_conn': False,
            'color': [],
            'red': 0,
            'green': 0,
            'blue': 0,
            'delta': {'red': 0,'green': 0,'blue': 0},
            'time_change': [],
            'quant': {'num': config.cfg['quant_num'], 'count': 0, 'flag': 0},
})


def time_phase(time_change):
    t = time_change.split('-')
    if len(t) < 2:
        return int(t[0])
    else:
        return randint(t[0],t[1])


def manage_rgb(payload, chan_name):
    if len(payload) < 4 or (len(payload)-1)%3 != 0:
        return
    cList = set(payload) & set(manage_seq[chan_name]['current_command'])
    if len(payload) == len(cList):
        print("Already executed")
        return
    manage_seq[chan_name]['current_command'] = payload 
    manage_seq[chan_name].update({
        'mode': payload[-1],  
        'len': int((len(payload)-1)/3),  
        'color': [],
        'time_static': [],
        'time_change': [],
        'count': 0,
        'time_current': time.ticks_ms(),
    })
    for i in range(manage_seq[chan_name]['len']):
        manage_seq[chan_name]['color'].append(payload[i * 3])
        manage_seq[chan_name]['time_static'].append(payload[i * 3 + 1])
        manage_seq[chan_name]['time_change'].append(payload[i * 3 + 2])
    manage_seq[chan_name]['time_slice'] = time_phase(manage_seq[chan_name]['time_static'][0])
    manage_seq[chan_name]['time_current'] = time.ticks_ms()
    manage_seq[chan_name]['quant']['count'] = 0
    manage_seq[chan_name]['quant']['flag'] = 0
    manage_pwm(0)


def manage_discr(payload, chan_name):
    if len(payload) < 3 or (len(payload)-1)%2 != 0:
        return
    cList = set(payload) & set(manage_seq[chan_name]['current_command'])
    if len(payload) == len(cList):
        print("Already executed")
        return
    manage_seq[chan_name]['current_command'] = payload 
    manage_seq[chan_name].update({
        'mode': payload[-1],  
        'len': int((len(payload)-1)/2),
        'onoff': [],
        'time_static': [],
        'count': 0,
    })
    manage_seq[chan_name]['time_change'] = []
    for i in range(manage_seq[chan_name]['len']):
        manage_seq[chan_name]['onoff'].append(payload[i * 2])
        manage_seq[chan_name]['time_static'].append(payload[i * 2 + 1])
    config.pins[chan_name].value(int(manage_seq[chan_name]['onoff'][manage_seq[chan_name]['count']]))
    manage_seq[chan_name]['time_slice'] = time_phase(str(manage_seq[chan_name]['time_static'][0]))


def exec_discr(chan_name):
    if (time.ticks_ms() - manage_seq[chan_name]['time_current']) >= manage_seq[chan_name]['time_slice']:
        if manage_seq[chan_name]['mode'] == 'C':
            manage_seq[chan_name]['count'] = (manage_seq[chan_name]['count'] + 1) % manage_seq[chan_name]['len']
        elif manage_seq[chan_name]['mode'] == 'S':
            manage_seq[chan_name]['count'] += 1
            if manage_seq[chan_name]['count'] >= manage_seq[chan_name]['len']:
                manage_seq[chan_name]['len'] = 0
                manage_seq[chan_name]['current_command'] = []
                return
        manage_seq[chan_name]['time_slice'] = time_phase(manage_seq[chan_name]['time_static'][manage_seq[chan_name]['count']])
        config.pins[chan_name].value(int(manage_seq[chan_name]['onoff'][manage_seq[chan_name]['count']]))
        manage_seq[chan_name]['time_current'] = time.ticks_ms()


def parse_command(new_command):
    for cmd, val in manage_seq.items():
        data = new_command.get(cmd) 
        if not data:
            continue
        if data != val.get('current_command'):
            payload = data.split('/')
            if payload[0] == 'RESET':
                machine.reset()
            else:
                if cmd == 'RGB':
                    manage_rgb(payload, cmd)
                else:
                    manage_discr(payload, cmd)


def mqtt_callback(topic, msg):
    global ping_msg
    if topic in (config.topics['sub'], config.topics['sub_id']):
        try:
            cmd = ujson.loads(msg)
            datahold = cmd.get('datahold')
            parse_command(datahold)
            return 
        except:
            time.sleep(.2)
            return
    elif (topic == config.topics['sub_ping']):
        ping_msg = msg


def connect_and_subscribe():
    bList = str(station.ifconfig()[0]).split('.')
    bList[-1] = '254'
    brokerIP = '.'.join(bList)
    server = brokerIP
    port = config.cfg.get('port')
    user = config.cfg.get('user')
    password = config.cfg.get('password')
    client = umqttsimple.MQTTClient(config.cfg.get('client_id'), server, port, user, password, keepalive=30)
    client.set_callback(mqtt_callback)
    try:
        client.connect()
    except:
        manage_seq['RGB']['mqtt_conn'] = False
        return client
    sub_topics = [config.topics[t] for t in config.topics if 'sub' in t]
    for t in sub_topics:
        client.subscribe(t)
    print('connected to {}, subscribed to {}'.format(server, sub_topics))
    try:
        cmd_out = '{"timestamp":1}'
        client.publish(config.topics['pub'], cmd_out)
        manage_seq['RGB']['mqtt_conn'] = True
    except:
        manage_seq['RGB']['mqtt_conn'] = False
        restart_and_reconnect()
    reset_out()
    return client


def send_pong(msg, client):
    client.publish(config.topics['pub_id_pong'], msg)
    return


def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    if station.isconnected() == False:
        print('WiFi connection lost!')
        wifi_init()
    for x in range(6):
        pwm['green'].duty(1023)
        time.sleep(.25)
        pwm['green'].duty(0)
        time.sleep(.25)


def manage_pwm_delta(prev_idx):
    rgb_seq = manage_seq['RGB']
    quant = rgb_seq['quant']

    if quant['flag'] == 0:
        idx = rgb_seq['count']
        color_now = rgb_seq['color'][idx]
        color_prev = rgb_seq['color'][prev_idx]

        delta_red = int((_hex(color_now[:2]) - _hex(color_prev[:2])) / quant['num'])
        delta_green = int((_hex(color_now[2:4]) - _hex(color_prev[2:4])) / quant['num'])
        delta_blue = int((_hex(color_now[4:6]) - _hex(color_prev[4:6])) / quant['num'])

        rgb_seq['delta']['red'] = delta_red
        rgb_seq['delta']['green'] = delta_green
        rgb_seq['delta']['blue'] = delta_blue

        quant['flag'] = 1

    quant['count'] += 1

    for key in rgb_seq['delta']:
        rgb_seq[key] += rgb_seq['delta'][key]

    set_pwm()


def manage_pwm(idx):
    _color = manage_seq['RGB']['color']
    manage_seq['RGB']['red'] = _hex(_color[idx][:2])
    manage_seq['RGB']['green'] = _hex(_color[idx][2:4])
    manage_seq['RGB']['blue'] = _hex(_color[idx][4:6])
    set_pwm()


def mqtt_init():
    manage_seq['RGB']['mqtt_conn'] = False
    while not manage_seq['RGB']['mqtt_conn']:
        restart_and_reconnect()
        client = connect_and_subscribe()
    return client


def main():
    global pwm
    global ping_msg
    pwm = {p: machine.PWM(config.pins[p], freq=1000) for p in config.pins if p in ('red', 'green', 'blue')}
    reset_out()
    wifi_init()
    client = mqtt_init()    
    while True:
        try:
            client.check_msg()
        except OSError as e:
            client = mqtt_init()    
        if ping_msg != b'':
            send_pong(ping_msg, client)
            ping_msg = b''
        if manage_seq['RGB'].get('len') > 0:
            if (time.ticks_ms() - manage_seq['RGB']['time_current']) >= manage_seq['RGB']['time_slice']:
                before = manage_seq['RGB']['count']
                manage_seq['RGB']['time_current'] = time.ticks_ms()
                if manage_seq['RGB']['quant']['flag'] == 0:
                    if manage_seq['RGB']['mode'] == 'C':
                        manage_seq['RGB']['count'] = (before + 1) % manage_seq['RGB']['len']
                    elif manage_seq['RGB']['mode'] == 'S':
                        manage_seq['RGB']['count'] += 1
                        if manage_seq['RGB']['count'] >= manage_seq['RGB']['len']:
                            manage_seq['RGB']['len'] = 0
                            continue
                    try:
                        tc = int(manage_seq['RGB'].get('time_change')[before])
                        if tc > 0:
                            manage_seq['RGB']['time_slice'] = int(tc/manage_seq['RGB']['quant']['num'])
                            manage_pwm_delta(before)
                        else:
                            manage_seq['RGB']['time_slice'] = time_phase(manage_seq['RGB']['time_static'][manage_seq['RGB']['count']])
                            manage_pwm(manage_seq['RGB']['count'])
                    except IndexError:
                        print('index error in RGB conf')
                elif manage_seq['RGB']['quant']['flag'] == 1:
                    manage_pwm_delta(before)
                    if manage_seq['RGB']['quant']['count'] >= manage_seq['RGB']['quant']['num']:
                        manage_seq['RGB']['quant']['count'] = 0
                        manage_seq['RGB']['quant']['flag'] = 0
                        manage_seq['RGB']['time_slice'] = time_phase(manage_seq['RGB']['time_static'][manage_seq['RGB']['count']])
                        continue
        if manage_seq['STR'].get('len') > 0:
            exec_discr('STR')
        if manage_seq['LGT'].get('len') > 0:
            exec_discr('LGT')


main()
