'''
Example:
  import dk
  cfg = dk.load_config(config_path='~/donkeycar/donkeycar/parts/RLConfig.py')
  print(cfg.CAMERA_RESOLUTION)
'''


MODE_COMPLEX_LANE_FOLLOW = 0 
MODE_SIMPLE_LINE_FOLLOW = 1 
# MODE_STEER_THROTTLE = MODE_COMPLEX_LANE_FOLLOW
MODE_STEER_THROTTLE = MODE_SIMPLE_LINE_FOLLOW

# SWITCH_TO_NN = 15000
# SWITCH_TO_NN = 9000
SWITCH_TO_NN = 3000
# SWITCH_TO_NN = 7500
# SWITCH_TO_NN = 50
# UPDATE_NN = 1000
UPDATE_NN = 500

THROTTLE_CONSTANT = 0
# THROTTLE_CONSTANT = .3

STATE_EMERGENCY_STOP = 0
STATE_NN = 1
STATE_OPENCV = 2
STATE_MODEL_TRANSFER_STARTED = 3

EMERGENCY_STOP = 0.000001
DISABLE_EMERGENCY_STOP = True

TURNADJ = .02
# DESIREDPPF = 35
DESIREDPPF = 20
# MAXBATADJ  = .10
# BATADJ  = .001
MAXBATADJ  = .000  # simulation doesn't have battery
BATADJ  = .000     # simulation doesn't have battery
RL_MODEL_PATH = "~/d2/models/rlpilot"
MAXBATCNT = 1000

MAXBATCNT  = 1000
# MAX_ACCEL = 10
MAX_ACCEL  = 3

CHECK_THROTTLE_THRESH = 20
MAXLANEWIDTH = 400  # should be much smaller
MIN_DIST_FROM_CENTER = 20

# client to server
MSG_NONE                 = -1
MSG_GET_WEIGHTS          = 1
MSG_ANGLE_THROTTLE_ROI   = 2
MSG_REWARD_ROI           = 3

# server to client
MSG_RESULT               = 4
MSG_WEIGHTS              = 5

# RLPi States
RLPI_READY1 = 1
RLPI_READY2 = 2
RLPI_WAITING = 3

PORT_RLPI = 5557
PORT_CONTROLPI = 5558

# each of throttle's 15 slots is worth the following (6 max throttle)
THROTTLE_INCREMENT = .4
ANGLE_INCREMENT = 1       # pass angle bin back and forth

SAVE_MOVIE = False
