# Wall-Clock-V2
<Info on what this project is here, maybe a picture>

## Bill of Materials
![Adafruit 1.2" 4-Digit 7-Segment Display w/I2C Backpack](/assets/1270-04.jpg)


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
