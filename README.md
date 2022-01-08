# Wall-Clock-V2

Installation Steps
1. [Install the OS](https://www.raspberrypi.com/software/) on the Raspberry Pi. The latest 'light' version of the OS should be fine. I suggest setting up the system to run [headless](https://www.tomshardware.com/reviews/raspberry-pi-headless-setup-how-to,6028.html), otherwise you will need a keyboard and monitor for the next steps. All the commands after this assume you are logged into the RPi over SSH.
2. Run the configuration utility by connecting over SSH and typing 'sudo raspi-config'. In this menu, you will want to do a few things
   - Change the default password
   - Set the timezone
   - Turn on I2C
3. Install dependencies
   - `sudo apt update`
   - `sudo apt upgrade`
   - I2C Tools: `sudo apt install python-smbus i2c-tools`
   - Python package manager: `sudo apt install python3-pip`
   - Samba: `sudo apt install samba samba-common-bin`
4. Install Python dependencies
   - Display: `sudo pip3 install adafruit-circuitpython-ht16k33`
   - Temp/pressure/humidity sensor: `sudo pip3 install adafruit-circuitpython-bme280`
   - Light sensor: `sudo pip3 install adafruit-circuitpython-veml7700`
   - Neopixel: `sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel`
   - [PAHO](https://pypi.org/project/paho-mqtt/) for MQTT functionality: `pip3 install paho-mqtt`
5. Set up Samba (only needed if you want an easy way to view/change the software)
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

   
    
