
from subprocess import call
import configparser
import signal
import sys
import time
from datetime import datetime
import board
import digitalio
import neopixel
from adafruit_ht16k33.segments import BigSeg7x4
from adafruit_bme280 import basic as adafruit_bme280
import adafruit_veml7700
import paho.mqtt.client as mqtt

#Import configuration and set up globals
#TODO: Does it make sense to read these from the config file into local variables, or should I just use them directly from the config file??
config = configparser.ConfigParser()
config.read('/home/pi/software/wall_clock.ini')     #TODO: Do I need the full path here?

LBO_Reset_Count = int(config['DEFAULT']['LBOResetLimit'])
LoopDelayTime = int(config['DEFAULT']['TickTime'])
DisplayBrightness = float(config['DEFAULT']['DisplayBrightness'])

TempUnits = config['DEFAULT']['TempUnits']
PressureUnits = config['DEFAULT']['PressureUnits']
AMPM = config.getboolean('DEFAULT', 'AMPM')

UseMQTT = config.getboolean('MQTT', 'UseMQTT')
MQTT_Server_IP = config['MQTT']['ServerIP']
MQTT_Server_Port = int(config['MQTT']['port'])
MQTT_Server_User = config['MQTT']['User']
MQTT_Server_Password = config['MQTT']['Password']
MQTT_Data_Topic = config['MQTT']['DataTopicHeader']
MQTT_Status_Topic = config['MQTT']['StatusTopicHeader']

MQTT_Data_Topic_Temp = MQTT_Data_Topic + "temp"
MQTT_Data_Topic_Pressure = MQTT_Data_Topic + "pressure"
MQTT_Data_Topic_Humidity = MQTT_Data_Topic + "humidity"
MQTT_Data_Topic_Light = MQTT_Data_Topic + "light"
MQTT_Data_Topic_CPUTemp = MQTT_Data_Topic + "CPUTemp"
MQTT_Data_Topic_Availability = MQTT_Data_Topic + "availability"
MQTT_Data_Topic_Power = MQTT_Data_Topic + "HasPower"

MQTT_Status_Topic_Subscription = MQTT_Status_Topic + "#"
MQTT_Status_Topic_ONOFF = MQTT_Status_Topic + "light/switch"
MQTT_Status_Topic_Brightness = MQTT_Status_Topic + "brightness/set"
MQTT_Status_Topic_RGB = MQTT_Status_Topic + "rgb/set"




#Initialize I2C devices
i2c = board.I2C()
time.sleep(1)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
veml7700 = adafruit_veml7700.VEML7700(i2c)
display = BigSeg7x4(i2c)

#Set up the Neopixel
#Note: the script must be run as root in order for neopixel code to work
pixel_pin = board.D18   #NeoPixels must be connected to D10, D12, D18 or D21 to work.
num_pixels = 1          #The number of NeoPixels
ORDER = neopixel.RGB    #The order of the pixel colors - RGB or GRB. For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER)

#Global values for the pixel color.
#TODO: The server should probably initialize these on connect somehow, but I am not sure how to make that happen.
PixelRedVal = 0
PixelGreenVal = 255
PixelBlueVal = 0
PixelBrightness = 100
PixelOn = False
PixelUpdate = False

#Set up GPIO to sense power and low battery
# VUSB goes low when USB power is lost
# LBO should go low when the battery is low
VUSB_Pin = board.D15
LBO_Pin = board.D14
VUSB = digitalio.DigitalInOut(VUSB_Pin)
LBO = digitalio.DigitalInOut(LBO_Pin)
VUSB.direction = digitalio.Direction.INPUT
VUSB.pull = None
LBO.direction = digitalio.Direction.INPUT
LBO.pull = None
#TODO: Shut down when we have been on battery for a while?

client = mqtt.Client()
MQTT_Server_status = 255

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    global MQTT_Server_status
    #print("Connected with result code "+str(rc))
    MQTT_Server_status = rc
    
    if rc == 0:
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(MQTT_Status_Topic_Subscription)

#The callback for when a PUBLISH message is received from the server.
# Sets the requested status of the RGB LED to the global variables. The actual update to the LED state occurs in the main function.
def on_message(client, userdata, msg):
    global PixelRedVal
    global PixelGreenVal
    global PixelBlueVal
    global PixelBrightness
    global PixelOn
    global PixelUpdate

    #print(msg.topic+" "+str(msg.payload))

    if msg.topic == MQTT_Status_Topic_RGB:
        integers = [int(i) for i in msg.payload.split(b',')]
        PixelRedVal = integers[0]
        PixelGreenVal = integers[1]
        PixelBlueVal = integers[2]
        PixelUpdate = True
    elif msg.topic == MQTT_Status_Topic_Brightness:
        PixelBrightness = int(msg.payload)
        PixelUpdate = True
    elif msg.topic == MQTT_Status_Topic_ONOFF:
        if(msg.payload == b'ON'):
            PixelOn = True
            PixelUpdate = True
        elif(msg.payload == b'OFF'):
            PixelOn = False
            PixelUpdate = True

def on_disconnect(client, userdata, rc):
    #I don't think this is useful. This event does not occur when the server goes down. (that I can tell)
    # I am not sure what other conditions cause a disconnect event. I am leaving this here incase it is useful.
    # The network loop should reconnect automatically in the event of a network error.
    # If client is calling disconnect, it will generally be on exit, so nothing needs to be done here.
    MQTT_Server_status = 253

#Return CPU Temperature  
def GetCPUTemp():
    try:
        f = open("/sys/class/thermal/thermal_zone0/temp", "r")
        CPU_Temp_C = float(f.readline())/1000.
    except:
        CPU_Temp_C = 0
    finally:
        f.close()

    return CPU_Temp_C

def MQTT_SendData():
    if UseMQTT and (MQTT_Server_status == 0):
        RoomTemp = bme280.temperature       #C
        BarometricPress = bme280.pressure   #millibar
        RoomHumidity = bme280.humidity      #RH%
        CPUTemp = GetCPUTemp()              #C
        LightLevel = veml7700.lux           #Lux
        
        if TempUnits == "F":
            RoomTemp = RoomTemp*(9.0/5.0)+32.0
            CPUTemp = CPUTemp*(9.0/5.0)+32.0
        
        if PressureUnits == "inHg":
            BarometricPress = BarometricPress / 33.864
        
    
        client.publish(MQTT_Data_Topic_Temp, payload="{:.2f}".format(RoomTemp), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Pressure, payload="{:.2f}".format(BarometricPress), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Humidity, payload="{:.2f}".format(RoomHumidity), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Light, payload="{:.2f}".format(LightLevel), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_CPUTemp, payload="{:.2f}".format(CPUTemp), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Availability, payload="online", qos=0, retain=False)

def MQTT_ReportPowerStatus():
    if UseMQTT and (MQTT_Server_status == 0):
        if VUSB.value == 1:
            client.publish(MQTT_Data_Topic_Power, payload="TRUE", qos=0, retain=False)
        else:
            client.publish(MQTT_Data_Topic_Power, payload="FALSE", qos=0, retain=False)

def MQTT_Shutdown():
    if UseMQTT and (MQTT_Server_status == 0):
        client.publish(MQTT_Data_Topic_Availability, payload="offline", qos=0, retain=False)
        client.disconnect()
        client.loop_stop()

def MQTT_Connect():
    global client
    global MQTT_Server_status
    TimeoutCount = 0
    
    if UseMQTT and (MQTT_Server_status > 0):
        #Connect to MQTT server and spawn child process to handle network traffic
        # This function can be called when the connection is active.
        client.username_pw_set(MQTT_Server_User, MQTT_Server_Password)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        try:
            client.connect(MQTT_Server_IP, MQTT_Server_Port, 60)
        except:
            #The connect function fails if the IP address is wrong (maybe for other reasons also). 
            # Catch this here and indicate the the connection is inactive.
            MQTT_Server_status = 254
            #print("Connection Failed")
        else:
            client.loop_start()
            while (TimeoutCount < 50) and (MQTT_Server_status > 250):
                #Wait for status from the on_connect callback.
                # The on_connect function sets the MQTT_Server_status flag to the return code.
                # This does not nessecarially mean the connection was successful.
                # Timeout after .1*50 = ~5 sec
                time.sleep(.1)   #Make sure the connection is established before continuing
                TimeoutCount = TimeoutCount + 1
            if MQTT_Server_status > 0:
                #Something failed when connecting to MQTT server. Stop the network loop.
                # The main loop should retry this connection periodically
                client.loop_stop()

def UpdateDisplay(CurrentTime):
    TimeoutCount = 0
    while TimeoutCount<10:
        try:
            if AMPM:
                #Use AM/PM
                TimeString = CurrentTime.strftime("%I%M")
                if TimeString[0] == '0':
                    display[0] = ' '
                else:
                    display[0] = TimeString[0]
            else:
                #24 hour time
                TimeString = CurrentTime.strftime("%H%M")
                display[0] = TimeString[0]
            
            display[1] = TimeString[1]
            display[2] = TimeString[2]
            display[3] = TimeString[3]
            display.colon = True
            break
        except OSError:
            print(CurrentTime.strftime("%H:%M"), ": OS Error", TimeoutCount)
            
        TimeoutCount = TimeoutCount + 1

def main():
    global PixelUpdate
    global display
    signal.signal(signal.SIGINT, signal_handler)    #Catch Control+C
    signal.signal(signal.SIGTERM, signal_handler)   #Catch the exit command from systemd. SIGTERM is sent from systemd when 'systemctl stop <service>' is called.
    
    LBO_Count = 0
    
    #Initializing the RGB led to off. TODO: Is this what I want?
    pixels.fill((0, 0, 0))
    pixels.show()
    
    #Connect to the MQTT server and send initial data. Connection errors or disabling MQTT is handled inside the MQTT functions.
    MQTT_Connect()
    MQTT_SendData()
    #TODO: Is there a way to request the RGB LED status from the server? maybe using the availability topic?

    #Display time on the display
    display.brightness = DisplayBrightness  #Set display brightness
    now = datetime.now()
    UpdateDisplay(now)
    OldMin = now.strftime("%M")
    OldHour = now.strftime("%H")

    while True:
        now = datetime.now()
        
        #Once per minute
        if now.strftime("%M") != OldMin:
            OldMin = now.strftime("%M")
            UpdateDisplay(now)
            MQTT_SendData()     #Send data to MQTT server

        #Once per hour
        if now.strftime("%H") != OldHour:
            OldHour = now.strftime("%H")
            #Try to reconnect to the MQTT server.
            # This function should behave properly if the connection is already active or MQTT is disabled.
            # This reconnection stuff is untested. It is called on initial connection, so it *should* work,
            # but I don't have a good way to test it.
            MQTT_Connect()      
        
        #Inform the MQTT server if power is lost
        MQTT_ReportPowerStatus()
        
        #Monitor LBO from the powerboost and shutdown if LBO is low for a certain number of counts.
        # I did not want noise on the LBO line to shutdown the Pi unnessecarially.
        # I therefore require a certain number of LBO readings before doing a shutdown
        # With the default tick rate of 1s and LBO_Reset_Count = 10, this will execute a shutdown after ~10sec.
        if LBO.value == 0:
            if LBO_Count > LBO_Reset_Count:
                #Shutdown
                OnShutdown()
                call("sudo shutdown -h now", shell=True)
            else:
                LBO_Count = LBO_Count + 1
        elif LBO_Count > 0:
                LBO_Count = LBO_Count - 1
        
        #Change the color of the status pixel. The callback will indicate the MQTT server wants to change the pixel color
        # by setting PixelUpdate to true. The new pixel values are saved in the global pixel variables.
        # Note that the pixel change will occur on the next tick of the main loop from when the change command is recieved.
        # If the tick rate is too low, this may take a while.
        if PixelUpdate:
            if (not PixelOn) or (PixelBrightness == 0):
                pixels.fill((0, 0, 0))
            else:
                pixels.fill((int(PixelRedVal*(PixelBrightness/255)), int(PixelGreenVal*(PixelBrightness/255)), int(PixelBlueVal*(PixelBrightness/255))))
            pixels.show()
            PixelUpdate = False
            
        time.sleep(LoopDelayTime)   #This controls the 'tick rate' of the main loop.

#Run this if the service is shutting down.
def OnShutdown():
    #Send a offline command over MQTT and disconnect
    MQTT_Shutdown()
    #Turn off the display and RGB LED.
    pixels.fill((0, 0, 0))
    pixels.show()
    display.fill(0)

def signal_handler(sig, frame):
    OnShutdown()
    sys.exit(0)

if __name__ == "__main__":
    main()