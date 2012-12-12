#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

__author__ = "Kyle Gordon"
__copyright__ = "Copyright (C) Kyle Gordon"

import mosquitto
import os
import logging
import signal
import socket
import time
import sys

import mosquitto
import ConfigParser
import ow

from datetime import datetime, timedelta

# Read the config file
config = ConfigParser.RawConfigParser()
config.read("/etc/mqtt-owfs-temp/mqtt-owfs-temp.cfg")

# Use ConfigParser to pick out the settings
DEBUG = config.getboolean("global", "debug")
LOGFILE = config.get("global", "logfile")
MQTT_HOST = config.get("global", "mqtt_host")
MQTT_PORT = config.getint("global", "mqtt_port")

MQTT_TOPIC="/raw/" + socket.getfqdn()

POLLINTERVAL = config.getint("global", "pollinterval")
DEVICESFILE = config.get("global", "devicesfile")

# FIXME, have list of devices - ie
# kitchenpi.vpn.glasgownet.com, 4304, /28.C8D40D040000/temperature
# kitchenpi.vpn.glasgownet.com, 4304, /28.DDBF1D030000/temperature
# kitchenpi.vpn.glasgownet.com, 4304, /28.3C4F1D030000/temperature
# loftpi.vpn.glasgownet.com, 4304, /28.3C4F1D030000/temperature

owserver = "kitchenpi.vpn.glasgownet.com"

client_id = "Readmeter_%d" % os.getpid()
mqttc = mosquitto.Mosquitto(client_id)

LOGFORMAT = '%(asctime)-15s %(message)s'

if DEBUG:
    logging.basicConfig(filename=LOGFILE, level=logging.DEBUG, format=LOGFORMAT)
else:
    logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=LOGFORMAT)

logging.info('Starting mqtt-owfs-temp')
logging.info('INFO MODE')
logging.debug('DEBUG MODE')

def cleanup(signum, frame):
     """
     Signal handler to ensure we disconnect cleanly 
     in the event of a SIGTERM or SIGINT.
     """
     logging.info("Disconnecting from broker")
     # FIXME - This status topis too far up the hierarchy.
     mqttc.publish("/status/" + socket.getfqdn(), "Offline")
     mqttc.disconnect()
     logging.info("Exiting on signal %d", signum)
     sys.exit(signum)

def connect():
    """
    Connect to the broker, define the callbacks, and subscribe
    """
    result = mqttc.connect(MQTT_HOST, MQTT_PORT, 60, True)
    if result != 0:
        logging.info("Connection failed with error code %s. Retrying", result)
        time.sleep(10)
        connect()

    #define the callbacks
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect

    mqttc.subscribe(MQTT_TOPIC, 2)

def on_connect(result_code):
     """
     Handle connections (or failures) to the broker.
     """
     ## FIXME - needs fleshing out http://mosquitto.org/documentation/python/
     if result_code == 0:
        logging.info("Connected to broker")
        mqttc.publish("/status/" + socket.getfqdn(), "Online")
     else:
        logging.warning("Something went wrong")
        cleanup()

def on_disconnect(result_code):
     """
     Handle disconnections from the broker
     """
     if result_code == 0:
        logging.info("Clean disconnection")
        ow.finish
     else:
        logging.info("Unexpected disconnection! Reconnecting in 5 seconds")
        logging.debug("Result code: %s", result_code)
        time.sleep(5)
        connect()
        main_loop()

def on_message(msg):
    """
    What to do once we receive a message
    """
    logging.debug("Received: " + msg.topic)

def find_in_sublists(lst, value):
    for sub_i, sublist in enumerate(lst):
        try:
            return (sub_i, sublist.index(value))
        except ValueError:
            pass

    raise ValueError('%s is not in lists' % value)

class DevicesList():
    """
    Read the list of devices, and expand to include publishing state and current value
    """
    import csv
    datafile = open(DEVICESFILE, 'r')
    datareader = csv.reader(datafile)
    data = []
    for row in datareader:
        data.append(row)

def main_loop():
    """
    The main loop in which we stay connected to the broker
    """
    while mqttc.loop() == 0:
	logging.debug(("DeviceList.data is : %s") % (str(DevicesList.data)))
	item = 0
	for device in DevicesList.data:
            # Split up list into relevant parts for reuse
            owserver = DevicesList.data[item][0]
            owport = DevicesList.data[item][1]
            owpath = DevicesList.data[item][2]
	    logging.debug(("Querying %s on %s:%s") % (owpath, owserver, owport))

            # FIXME owserver to come from a list of devices, and their respective servers
            ow.init(owserver + ":" + owport)
            ow.error_level(ow.error_level.fatal)
            ow.error_print(ow.error_print.stderr)
        
            # FIXME This possibly needs done for each 1-wire host
            # Split it off to the connect() function
            # Enable simultaneous temperature conversion
            ow._put('/simultaneous/temperature','1')
            
            # Create sensor object
            sensor = ow.Sensor(owpath)
            
            #Query sensor state
            logging.debug(("Sensor %s : %s") % (owpath, sensor.temperature))
	    mqttc.publish(MQTT_TOPIC + owpath, sensor.temperature)
	    item += 1
	
	time.sleep(POLLINTERVAL)
    
# Use the signal module to handle signals
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# Connect to the broker and enter the main loop
connect()
main_loop()
