""" 
CAR CONFIG 

This file is read by your car application's manage.py script to change the car
performance. 

EXMAPLE
-----------
import dk
cfg = dk.load_config(config_path='~/d2/config.py')
print(cfg.CAMERA_RESOLUTION)

"""


import os

#PATHS
CAR_PATH = PACKAGE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(CAR_PATH, 'data')
MODELS_PATH = os.path.join(CAR_PATH, 'models')

#VEHICLE
# 20 for NN, 10 for OpenCV
# need this to be programatically set
DRIVE_LOOP_HZ = 20
# DRIVE_LOOP_HZ = 5
# DRIVE_LOOP_HZ = 10
MAX_LOOPS = 100000

#CAMERA
# CAMERA_RESOLUTION = (160, 120) # ARD
CAMERA_RESOLUTION = (120, 160)
CAMERA_FRAMERATE = DRIVE_LOOP_HZ

#STEERING
STEERING_CHANNEL = 1
# manual max turns: 470 370 320
# manual calib: 450 375 300
STEERING_LEFT_PWM = 450
STEERING_STRAIGHT_PWM = 375
STEERING_RIGHT_PWM = 300

#THROTTLE
THROTTLE_CHANNEL = 0
THROTTLE_FORWARD_PWM = 450
THROTTLE_STOPPED_PWM = 380
THROTTLE_REVERSE_PWM = 310

#TRAINING
BATCH_SIZE = 128
TRAIN_TEST_SPLIT = 0.8


#JOYSTICK
USE_JOYSTICK_AS_DEFAULT = False
JOYSTICK_MAX_THROTTLE = 0.25
JOYSTICK_STEERING_SCALE = 1.0
AUTO_RECORD_ON_THROTTLE = True
