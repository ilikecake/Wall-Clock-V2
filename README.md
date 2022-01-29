# Wall-Clock-V2
<Info on what this project is here, maybe a picture>

## Bill of Materials

### Commercial Parts
The main parts of the clock are.
| Part | Description |
| --- | --- |
| [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/)<br>Available from multiple places. You want the version without the GPIO header. | img |
| [Adafruit 1.2" 4-Digit 7-Segment Display w/I2C Backpack](https://www.adafruit.com/product/1270) | <img src="https://github.com/ilikecake/Wall-Clock-V2/blob/main/assets/1270-04.jpg" height="100"> |
| [PowerBoost 1000 Charger](https://www.adafruit.com/product/2465) | img |
| [Lithium Ion Polymer Battery, 1200mAh](https://www.adafruit.com/product/258) | img |
| [VEML7700 Light Sensor](https://www.adafruit.com/product/4162) | img |
| [BME280 Temperature/Pressure/Humidity Sensor](https://www.sparkfun.com/products/13676) | img |
| [Breadboard-friendly NeoPixel](https://www.adafruit.com/product/1312) | img |

### Fasteners and misc hardware
Various fasteners are needed to put this project together.
| Part | Quantity | Location |
| --- | --- | --- |
| [#4-40 FHMS, .5” Length](https://www.mcmaster.com/92210A110/) | 4 | Case to back |
| [#4-40 Nut](https://www.mcmaster.com/91841A005/) | 4 | Case to back |
| [#2-56 FHMS, .25” Length](https://www.mcmaster.com/91771A104/) | 2 | Power Switch |
| [#2-56 PHMS, .1875” Length](https://www.mcmaster.com/91772A076/) | 2 | PowerBoost |
| [#2-56 Nut](https://www.mcmaster.com/91841A003/) | 4 | Power Switch, PowerBoost |
| [#2 Self Tapping Screw, .1875” Length](https://www.mcmaster.com/99461A710/) | 10 | Power Entry, Sensors, Neopixel, Battery Holder |
| [M2.5 PHMS, 5mm Length](https://www.mcmaster.com/92000A103/) | 3 | RPi |
| [M2.5 Nut](https://www.mcmaster.com/91828A113/) | 3 | RPi |
| [#0-80 SHCS, .5” Length](https://www.mcmaster.com/92196A070/) | 4 | Midframe |
| [#0 Washer](https://www.mcmaster.com/90107A001/) | 4 | Midframe |
| [#0-80 Nut](https://www.mcmaster.com/91841A115/) | 4 | Midframe |
| [Plastic for Window, .125" thick](https://www.mcmaster.com/8505K721-8505K111/) | 1 | Window, Cut to 1.625"x4.36" |

### Custom PCBs
This project uses a few simple custom PCBs. These parts will require a bit of relativly easy surface mount soldering.
| Part | Description |
| --- | --- |
| [USB Power Entry PCB](https://oshpark.com/shared_projects/DeTFANqL) | img |
| [Interface PCB](https://oshpark.com/shared_projects/3Y6FiWnK) | img |
| Various Loose Components | img |
| Wire, 24 gauge and 30 gauge | img |




<Add a BOM here>

## Making interface PCBs.
This project uses a few simple custom PCBs. <more info here someday>

## Wiring
<How to wire up all the bits>

## 3D printing the case
<Links to the case files and instructions on how to print>

## Software Installation Steps
### Basic Setup and Dependencies
1. [Install the OS](https://www.raspberrypi.com/software/) on the Raspberry Pi. The latest 'light' version of the OS should be fine. I suggest setting up the system to run [headless](https://www.tomshardware.com/reviews/raspberry-pi-headless-setup-how-to,6028.html), otherwise you will need a keyboard and monitor for the next steps. All the commands after this assume you are logged into the RPi over SSH.
2. Run the configuration utility by connecting over SSH and typing `sudo raspi-config`. In this menu, you will want to do a few things
   - Change the default password
   - Set the timezone
   - Turn on I2C
3. Install dependencies
   - `sudo apt update`
   - `sudo apt upgrade`
   - I2C Tools: `sudo apt install python-smbus i2c-tools`
   - Python package manager: `sudo apt install python3-pip`
   - Samba: `sudo apt install samba samba-common-bin`
   - Git: `sudo apt install git`
4. Set up Git username and password (do I need to do this to just download stuff?)
   - `git config --global user.name "<Your Name Here>"`
   - `git config --global user.email "<Your Email Address Here>"`
5. Install Python dependencies
   - Display: `sudo pip3 install adafruit-circuitpython-ht16k33`
   - Temp/pressure/humidity sensor: `sudo pip3 install adafruit-circuitpython-bme280`
   - Light sensor: `sudo pip3 install adafruit-circuitpython-veml7700`
   - Neopixel: `sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel`
   - [PAHO](https://pypi.org/project/paho-mqtt/) for MQTT functionality: `pip3 install paho-mqtt`
6. Set up Samba (only needed if you want an easy way to view/change the software)
   - Open the config file: `sudo nano /etc/samba/smb.conf` Add the following to the end of the config file to define a share:
     ```
     [share]
     Comment = Pi shared folder
     Path = /home/pi
     Writeable = Yes
     create mask = 0777
     directory mask = 0777
     Public = no
     ```
   - Save and close the config file.
   - Add a Samba user: `sudo smbpasswd -a pi` chose a password that you will use to log in over Samba.
   - Restart the service to get everything to take effect: `sudo systemctl restart smbd`
### Get the software
1. Clone repo <add steps on how to do this...>
2. Change the 'wall_clock-TEMPLATE.ini' file to provide the info for your MQTT server. Save the file as 'wall_clock.ini'
3. Open 'wallclock.service' and check
   - Check the line `WorkingDirectory=`. Make sure the path is the full path to the folder with the .py script and .ini file.
   - Check the line `ExecStart=`. Make sure this line correctly points to the python3 executable and has the correct location of the wall_clock.py file.
4. Copy 'wallclock.service' to `/lib/systemd/system/`. You may (will probably) need root privleges for this.
5. Ensure that 'wall_clock.py' is executable: `chmod +x /home/pi/software/wall_clock.py`
6. Set permissions for the 'wallclock.service' file: `sudo chmod 644 /lib/systemd/system/wallclock.service`
7. Restart systemd: `sudo systemctl daemon-reload`
8. Enable the service:
   - To turn on the service now: `sudo systemctl start wallclock.service`
   - To enable the service to start on boot: `sudo systemctl enable wallclock.service`
   
### Power Saving Info
Some things on the Raspberry Pi can be disabled to conserve power. This device is designed to be powered from a fixed source, so power consumption is not critical. However, minimizing power consumption will allow for more time on the battery backup, and reduce the heat generated inside the case by the hardware.
- Disable HDMI
  - In '/boot/config.txt', change `dtoverlay=vc4-kms-v3d` to `dtoverlay=vc4-fkms-v3d`
  - Run `/usr/bin/tvservice -o` to disable HDMI (-p to re-enable).
  - Add this to the end of `/etc/rc.local` to disable HDMI on boot.
- Turn off bluetooth 
  - In '/boot/config.txt', add `dtoverlay=disable-bt` to disable the hardware.
  - Run `sudo systemctl disable hciuart.service` and `sudo systemctl disable bluetooth.service` to disable the software.

I measure ~150mA power consumption on the 5V line with the above changes. This equates to ~7 hour on-time with a 1200mAh battery. Internal temperature on the CPU is ~95F. <Check this later when the case is closed>

## Notes:
- The software must run as root. This a limitation of the Adafruit Neopixel library on Raspberry Pi.
