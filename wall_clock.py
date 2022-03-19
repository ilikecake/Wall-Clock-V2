
import os
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
# The config file must be located in the working directory of the program.
# TODO: Does it make sense to read these from the config file into local variables, or should I just use them directly from the config file??
config = configparser.ConfigParser()
cwd = os.getcwd()
ConfigFileLocation = cwd+"/wall_clock.ini"

#TODO: Get rid of except all statements. I need to say what errors to except

#Check if the config file is present. Exit if it is not found.
try:
    config.read_file(open(ConfigFileLocation, "r"))
except:
    sys.exit("Failed reading config file at " + ConfigFileLocation)

LBO_Reset_Count = int(config['DEFAULT']['LBOResetLimit'])
LoopDelayTime = int(config['DEFAULT']['TickTime'])
DisplayBrightness = float(config['DEFAULT']['DisplayBrightness'])

TempUnits = config['DEFAULT']['TempUnits']
PressureUnits = config['DEFAULT']['PressureUnits']
AMPM = config.getboolean('DEFAULT', 'AMPM')

UseBME280 = config.getboolean('DEFAULT', 'UseBME280')
UseVEML7700 = config.getboolean('DEFAULT', 'UseVEML7700')

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

I2C_Timeout_Val = 10    #Number of times to try sending I2C communication before exiting. TODO: Should this be defined in the config?

#Set up the Neopixel
#Note: the script must be run as root in order for neopixel code to work
pixel_pin = board.D18   #NeoPixels must be connected to D10, D12, D18 or D21 to work.
num_pixels = 1          #The number of NeoPixels
ORDER = neopixel.GRB    #The order of the pixel colors - RGB or GRB. For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER)

#Global values for the pixel color.
#TODO: The server should probably initialize these on connect somehow, but I am not sure how to make that happen.
PixelRedVal = 0
PixelGreenVal = 255
PixelBlueVal = 0
PixelBrightness = 100
PixelOn = False
PixelUpdate = False

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

def ReadSensorData(BME280_class, VEML7700_class):
    #Read from sensors, handle occasional I2C errors.
        
    #BME280
    if UseBME280:
        TimeoutCount = 0
        while TimeoutCount<I2C_Timeout_Val:
            try:
                #TODO: Taking these three readings performes three separate data conversions on the device, but it appears that only one is needed. Check to see if I can fix this later.
                RoomTemp = BME280_class.temperature       #C
                BarometricPress = BME280_class.pressure   #millibar
                RoomHumidity = BME280_class.humidity      #RH%
                break
            except OSError:
                print("I2C Error #"+str(TimeoutCount)+" when reading from BME280")
            TimeoutCount = TimeoutCount + 1
        
        if TimeoutCount >= I2C_Timeout_Val:
            #Failed to communicate over I2C
            OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
            sys.exit("I2C Failure reading from BME280")
        
        #Unit conversion if needed
        if TempUnits == "F":
            RoomTemp = RoomTemp*(9.0/5.0)+32.0
        if PressureUnits == "inHg":
            BarometricPress = BarometricPress / 33.864
    
    #VEML7700
    if UseVEML7700:
        TimeoutCount = 0
        while TimeoutCount<I2C_Timeout_Val:
            try:
                LightLevel = VEML7700_class.lux           #Lux
                break
            except OSError:
                print("I2C Error #"+str(TimeoutCount)+" when reading from VEML7700")
            TimeoutCount = TimeoutCount + 1
        
        if TimeoutCount >= I2C_Timeout_Val:
            #Failed to communicate over I2C
            OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
            sys.exit("I2C Failure reading from VEML7700")
    
    #CPU Temperature
    CPUTemp = GetCPUTemp()              #C
    
    #Unit conversion if needed
    if TempUnits == "F":
        CPUTemp = CPUTemp*(9.0/5.0)+32.0
    
    return(RoomTemp, BarometricPress, RoomHumidity, LightLevel, CPUTemp)

def MQTT_SendData(BME280_class, VEML7700_class):
    if UseMQTT and (MQTT_Server_status == 0):
        (RoomTemp, BarometricPress, RoomHumidity, LightLevel, CPUTemp) = ReadSensorData(BME280_class, VEML7700_class)
        client.publish(MQTT_Data_Topic_Temp, payload="{:.2f}".format(RoomTemp), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Pressure, payload="{:.2f}".format(BarometricPress), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Humidity, payload="{:.2f}".format(RoomHumidity), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Light, payload="{:.2f}".format(LightLevel), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_CPUTemp, payload="{:.2f}".format(CPUTemp), qos=0, retain=False)
        client.publish(MQTT_Data_Topic_Availability, payload="online", qos=0, retain=False)

def MQTT_ReportPowerStatus(PowerStatus):
    if UseMQTT and (MQTT_Server_status == 0):
        if PowerStatus == True:
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

def UpdateDisplay(CurrentTime, DisplayObject):
    TimeoutCount = 0
    while TimeoutCount<I2C_Timeout_Val:
        try:
            if AMPM:
                #Use AM/PM
                TimeString = CurrentTime.strftime("%I%M")
                if TimeString[0] == '0':
                    DisplayObject[0] = ' '
                else:
                    DisplayObject[0] = TimeString[0]
            else:
                #24 hour time
                TimeString = CurrentTime.strftime("%H%M")
                DisplayObject[0] = TimeString[0]
            
            DisplayObject[1] = TimeString[1]
            DisplayObject[2] = TimeString[2]
            DisplayObject[3] = TimeString[3]
            DisplayObject.colon = True
            DisplayObject.brightness = DisplayBrightness  #Set display brightness
            break
        except OSError:
            print("I2C Error #"+str(TimeoutCount)+" in UpdateDisplay")
            
        TimeoutCount = TimeoutCount + 1
        
    if TimeoutCount >= I2C_Timeout_Val:
        #Failed to communicate over I2C
        OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
        sys.exit("I2C Failure in UpdateDisplay")

def main():
    global PixelUpdate
    
    signal.signal(signal.SIGINT, signal_handler)    #Catch Control+C
    signal.signal(signal.SIGTERM, signal_handler)   #Catch the exit command from systemd. SIGTERM is sent from systemd when 'systemctl stop <service>' is called.
    
    #Set up GPIO to sense power and low battery
    # VUSB goes high when USB power is lost
    # LBO should go high when the battery is low
    # EN_I2C controls the I2C to the display. Set to True to enable.
    VUSB = digitalio.DigitalInOut(board.D15)
    LBO = digitalio.DigitalInOut(board.D14)
    EN_I2C = digitalio.DigitalInOut(board.D17)
    
    VUSB.direction = digitalio.Direction.INPUT
    VUSB.pull = None
    LBO.direction = digitalio.Direction.INPUT
    LBO.pull = None
    EN_I2C.direction = digitalio.Direction.OUTPUT
    EN_I2C.DriveMode = digitalio.DriveMode.PUSH_PULL
    EN_I2C.value = True

    LBO_Count = 0
    
    #Initialize I2C devices
    i2c = board.I2C()       #TODO: Can this fail? Probably not worth worrying about...
    time.sleep(1)
    
    #Try to initialize BME280
    if UseBME280:
        TimeoutCount = 0
        while TimeoutCount<I2C_Timeout_Val:
            try:
                bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
                break
            except:
                print("I2C Error #"+str(TimeoutCount)+" when initializing BME280")
            TimeoutCount = TimeoutCount + 1
        
        if TimeoutCount >= I2C_Timeout_Val:
            #Failed to communicate over I2C
            OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
            sys.exit("Failed to initialize BME280")

    #Try to initialize VEML7700
    if UseVEML7700:
        TimeoutCount = 0
        while TimeoutCount<I2C_Timeout_Val:
            try:
                veml7700 = adafruit_veml7700.VEML7700(i2c)
                break
            except:
                print("I2C Error #"+str(TimeoutCount)+" when initializing VEML7700")
            TimeoutCount = TimeoutCount + 1
        
        if TimeoutCount >= I2C_Timeout_Val:
            #Failed to communicate over I2C
            OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
            sys.exit("Failed to initialize VEML7700")
    
    #Try to initialize the display
    TimeoutCount = 0
    while TimeoutCount<I2C_Timeout_Val:
        try:
            display = BigSeg7x4(i2c)
            break
        except:
            print("I2C Error #"+str(TimeoutCount)+" when initializing display")
        TimeoutCount = TimeoutCount + 1
    
    if TimeoutCount >= I2C_Timeout_Val:
        #Failed to communicate over I2C
        OnShutdown()    #If this fails, the OnShutdown might also fail, but try it anyway.
        sys.exit("Failed to initialize display")
    
    #Initializing the RGB led to off. TODO: Is this what I want?
    pixels.fill((0, 0, 0))
    pixels.show()
    
    #Connect to the MQTT server and send initial data. Connection errors or disabling MQTT is handled inside the MQTT functions.
    MQTT_Connect()
    MQTT_SendData(bme280, veml7700)
    #TODO: Is there a way to request the RGB LED status from the server? maybe using the availability topic?

    #Display time on the display
    now = datetime.now()
    UpdateDisplay(now, display)
    OldMin = now.strftime("%M")
    OldHour = now.strftime("%H")

    while True:
        now = datetime.now()
        
        #Once per minute
        if now.strftime("%M") != OldMin:
            OldMin = now.strftime("%M")
            UpdateDisplay(now, display)
            MQTT_SendData(bme280, veml7700)     #Send data to MQTT server

        #Once per hour
        if now.strftime("%H") != OldHour:
            OldHour = now.strftime("%H")
            #Try to reconnect to the MQTT server.
            # This function should behave properly if the connection is already active or MQTT is disabled.
            # This reconnection stuff is untested. It is called on initial connection, so it *should* work,
            # but I don't have a good way to test it.
            MQTT_Connect()      
        
        #Inform the MQTT server if power is lost
        #The pin value is low if USB power is present
        MQTT_ReportPowerStatus(not VUSB.value)
        
        #Monitor LBO from the powerboost and shutdown if LBO is low for a certain number of counts.
        # I did not want noise on the LBO line to shutdown the Pi unnessecarially.
        # I therefore require a certain number of LBO readings before doing a shutdown
        # With the default tick rate of 1s and LBO_Reset_Count = 10, this will execute a shutdown after ~10sec.
        #TODO: Check if power is available, LBO count should only increase if LBO is high and power is off.
        if LBO.value == True:
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
    
    #Try to blank the display. This might fail if we are having I2C communication issues.
    # Ignore errors, we are quitting anyway. Try as hard as we can to exit gracefully.
    TimeoutCount = 0
    while TimeoutCount<I2C_Timeout_Val:
        try:
            display.fill(0)
            break
        except:
            pass
        TimeoutCount = TimeoutCount + 1

def signal_handler(sig, frame):
    OnShutdown()
    sys.exit(0)

if __name__ == "__main__":
    main()