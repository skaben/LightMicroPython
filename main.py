##############################################################################################
# Управляющая программа для "люстры" нового поколения.
# Пока обработка только RGB - канала устройства, на основе будет допилена прошивка для 
# полного функционала.
#
# Управляющий топик - RGB и RGB<mac-address>. Ответы в топике RGBASK. Ответ на пинг не 
# реализован пока.
# 
# Формат фходной команды - JSON. Для RGB выглядит так:
# 
# {"RGB":"FF0000/3000/1000/00FF00/3000/2000/0000FF/3000/0/C"}
#         цвет1  вр.1 вр.2 цвет2  вр.1 вр.2 цвет3  вр.1 вр2 последовательность
# Количество цветов в одной последвоательности произвольно.
#
# Время 1 - время, сколько цвет находится "в статике" в миллисекундах. 0 не допускается. 
# Для этого показателя допускается указание диапазона времени в милолсекундах через "-",
# например 100-1000 - это означает, что каждый раз время свечения выбираестя случайно
# в заданном диапазоне.
#
# Время 2 - время "перехода" из одного цвета к следующему, меньще 1000 мс указывать не 
# рекомендуется. Допустимо указывать 0 - мгновенная смена цвета.
#
# Цвета обязательно указываются 6-значными 16-ричными значениями, скоращать нельзя.
#
##############################################################################################
import machine
import time
import math
import ujson
import network
import urandom

quantNum = 20

newCom = dict()
curCom = dict()
curCom['RGB'] = ''
curCom['STR'] = ''
curCom['LGT'] = ''
modeRGB = ''
lenRGB = 0
timeCurrentRGB = 0
countCurrentRGB = 0
colorRGB = []
timeStaticRGB = []
timeChangeRGB = []
timeSliceRGB = 0
quantCount = 0
quantFlag = 0
rD = 0
bD = 0
gD = 0

lastRGB = 0

redPin = machine.Pin(15, machine.Pin.OUT)
greenPin = machine.Pin(12, machine.Pin.OUT)
bluePin = machine.Pin(13, machine.Pin.OUT)

redPWM = machine.PWM(redPin, freq=1000)
greenPWM = machine.PWM(greenPin, freq=1000)
bluePWM = machine.PWM(bluePin, freq=1000)

def randint(min, max):
    span = max - min + 1
    div = 0x3fffffff // span
    offset = urandom.getrandbits(30) // div
    val = min + offset
    return val

def parse_command(newCom):
  global modeRGB,lenRGB,colorRGB,timeStaticRGB,timeChangeRGB,timeCurrentRGB
  global timeSliceRGB,curCom,rD,bD,gD
  if newCom['RGB'] != curCom['RGB']:
    # Меняем команду
    curCom['RGB'] = newCom['RGB']
    fields = curCom['RGB'].split('/')
    modeRGB = fields[len(fields)-1]
    lenRGB = int(len(fields)/3)
    del colorRGB[:]
    del timeStaticRGB[:]
    del timeChangeRGB[:]
    i = 0
    while i < lenRGB:
      colorRGB.append(fields[i*3])
      timeStaticRGB.append(fields[i*3+1])
      timeChangeRGB.append(int(fields[i*3+2]))
      i = i + 1
    rD = int(colorRGB[0][0:2],16)*4
    gD = int(colorRGB[0][2:4],16)*4
    bD = int(colorRGB[0][4:6],16)*4
    redPWM.duty(rD)
    greenPWM.duty(gD)
    bluePWM.duty(bD)
    timeRandomRGB = str(timeStaticRGB[0]).split('-')
    if len(timeRandomRGB) != 2:
      timeSRGB = int(timeRandomRGB[0])
    else:
      timeSRGB = int(randint(int(timeRandomRGB[0]), int(timeRandomRGB[1])))
    timeSliceRGB = timeSRGB
    countCurrentRGB = 0
    quantCount = 0
    quantFlag = 0
    timeCurrentRGB = time.ticks_ms()

def sub_cb(topic, msg):
  print((topic, msg))
  global newCom, myMAC, topic_sub, topic_sub_id
  if topic == topic_sub or topic == topic_sub_id:
    try:
      newCom = ujson.loads(msg)
    except:
      print ('Wrong command')
      time.sleep_ms(200)
      return
    parse_command(newCom)
    
def connect_and_subscribe():
  global client_id, mqtt_server, topic_sub, myMAC
  client = MQTTClient(client_id, mqtt_server)
  client.set_callback(sub_cb)
  client.connect()
  client.subscribe(topic_sub)
  client.subscribe(topic_sub_id)
  print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub))
  print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub_id))
  greenPin.value(0)  
  return client

def restart_and_reconnect():
  print('Failed to connect to MQTT broker. Reconnecting...')
  greenPin.value(1)
  time.sleep_ms(250)
  greenPin.value(0)
  time.sleep_ms(250)
  greenPin.value(1)
  time.sleep_ms(250)
  greenPin.value(0)
  time.sleep_ms(250)
  greenPin.value(1)
  time.sleep_ms(250)
  greenPin.value(0)
  time.sleep_ms(250)
  greenPin.value(1)
  time.sleep_ms(250)
  greenPin.value(0)
  time.sleep_ms(250)
  machine.reset()

try:
  client = connect_and_subscribe()
except OSError as e:
  restart_and_reconnect()

while True:
  try:
    client.check_msg()
    if lenRGB > 0:
      if (time.ticks_ms() - timeCurrentRGB) >= timeSliceRGB:
        # Смена цвета
        if modeRGB == 'C' and quantFlag == 0:
          numBefore = countCurrentRGB
          countCurrentRGB = (countCurrentRGB + 1) % lenRGB
        elif modeRGB == 'S' and quantFlag == 0:
          numBefore = countCurrentRGB
          countCurrentRGB += 1
          if countCurrentRGB >= lenRGB:
            lenRGB = 0
            curCom['RGB'] = ''
            continue
        if timeChangeRGB[numBefore] > 0 and quantFlag == 0 :
          # Плавная смена цвета. 
          timeSliceRGB = int(timeChangeRGB[numBefore]/quantNum)
          rDDelta = int((int(colorRGB[countCurrentRGB][0:2],16)*4 - int(colorRGB[numBefore][0:2],16)*4)/quantNum)
          gDDelta = int((int(colorRGB[countCurrentRGB][2:4],16)*4 - int(colorRGB[numBefore][2:4],16)*4)/quantNum)
          bDDelta = int((int(colorRGB[countCurrentRGB][4:6],16)*4 - int(colorRGB[numBefore][4:6],16)*4)/quantNum)
          quantFlag = 1
          quantCount = 1
          rD += rDDelta
          gD += gDDelta
          bD += bDDelta
        elif quantFlag == 1 and quantCount < quantNum:
          timeSliceRGB = int(timeChangeRGB[numBefore]/quantNum)
          quantCount += 1
          rD += rDDelta
          gD += gDDelta
          bD += bDDelta
        else:
          quantFlag = 0
          quantCount = 0
          rD = int(colorRGB[countCurrentRGB][0:2],16)*4
          gD = int(colorRGB[countCurrentRGB][2:4],16)*4
          bD = int(colorRGB[countCurrentRGB][4:6],16)*4
          timeRandomRGB = str(timeStaticRGB[countCurrentRGB]).split('-')
          print(timeRandomRGB)
          if len(timeRandomRGB) != 2:
            timeSRGB = int(timeRandomRGB[0])
          else:
            timeSRGB = randint(int(timeRandomRGB[0]), int(timeRandomRGB[1]))
          timeSliceRGB = timeSRGB
        redPWM.duty(rD)
        greenPWM.duty(gD)
        bluePWM.duty(bD)
        timeCurrentRGB = time.ticks_ms()
  except OSError as e:
    restart_and_reconnect()

