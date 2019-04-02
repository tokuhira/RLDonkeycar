# https://stackoverflow.com/questions/45531074/how-to-merge-lines-after-houghlinesp
import numpy as np
import cv2
import math
import os
import copy
import donkeycar as dk
from stat import S_ISREG, ST_MTIME, ST_MODE, ST_CTIME, ST_ATIME
from donkeycar.parts.datastore import Tub

# todo:
# smooth turns
# handle sharp angles
# 3rd line?
# add minimal throttle control

#############################

class HoughBundler:
    '''Clasterize and merge each cluster of cv2.HoughLinesP() output
    a = HoughBundler()
    foo = a.process_lines(houghP_lines, binary_image)
    '''

    def get_orientation(self, line):
        '''get orientation of a line, using its length
        https://en.wikipedia.org/wiki/Atan2
        '''
        orientation = math.atan2(((line[3]) - (line[1])), (line[2] - (line[0])))
        deg = math.degrees(orientation)
        #  deg:    0  45  90 135 180 -135 -90 -45
        #  ret:   45  90 135 180  45   90 135

        if deg < 0:
          deg += 180
        elif deg < 180:
          pass
        elif deg > 180:
          deg = deg - 180
#     # print("DEG %d" % deg)
        return deg

    def checker(self, line_new, line_old):
        '''Check if line have enough distance and angle to be count as similar
        '''
        # for debugging
        # mindist = 400
        # minangle = 400
        # Parameters to play with
        # min_distance_to_merge = 40   # near
        # min_distance_to_merge2 = 5  # far 
        # max_y = 70
        # max_y = max(line_old[0][1], line_old[1][1], line_new[0][1], line_new[1][1])
        # max_y = 70 - max(line_old[1], line_old[3], line_new[1], line_new[3])
        max_y = max(line_old[1], line_old[3], line_new[1], line_new[3])
        # max_y = max(line_old[0][1], line_old[1][1], line_new[0][1], line_new[1][1])
        min_distance_to_merge = int(max_y / 2) + 5
        # min_distance_to_merge = int(max_y) + 5
        # print("max_y %d dist %d" % (max_y,min_distance_to_merge))
     
        min_angle_to_merge = 20
        # min_angle_to_merge = 30
        # min_angle_to_merge = 40
        if self.get_distance(line_old, line_new) < min_distance_to_merge:
          # check the angle between lines
          orientation_new = self.get_orientation(line_new)
          orientation_old = self.get_orientation(line_old)
          angle = abs(orientation_new - orientation_old)
          # if self.get_distance(line_old, line_new) < mindist:
          #   mindist = self.get_distance(line_old, line_new) 
          #   if minangle > angle:
          #     minangle = angle
          # if all is ok -- line is similar to others in group
          if abs(orientation_new - orientation_old) < min_angle_to_merge:
            # print("angle %d %d %d dist %d" % (orientation_new, orientation_old, min_angle_to_merge, self.get_distance(line_old, line_new)))
            return True
          # print("angle %d %d %d dist %d - NO MERGE" % (orientation_new, orientation_old, min_angle_to_merge, self.get_distance(line_old, line_new)))
        return False

    def DistancePointLine(self, point, line):
        """Get distance between point and line
        http://local.wasp.uwa.edu.au/~pbourke/geometry/pointline/source.vba
        """
        px, py = point
        x1, y1, x2, y2 = line

        def lineMagnitude(x1, y1, x2, y2):
            'Get line (aka vector) length'
            lineMagnitude = math.sqrt(math.pow((x2 - x1), 2) + math.pow((y2 - y1), 2))
            return lineMagnitude

        LineMag = lineMagnitude(x1, y1, x2, y2)
        if LineMag < 0.00000001:
            DistancePointLine = 9999
            return DistancePointLine

        u1 = (((px - x1) * (x2 - x1)) + ((py - y1) * (y2 - y1)))
        u = u1 / (LineMag * LineMag)

        if (u < 0.00001) or (u > 1):
            #// closest point does not fall within the line segment, take the shorter distance
            #// to an endpoint
            ix = lineMagnitude(px, py, x1, y1)
            iy = lineMagnitude(px, py, x2, y2)
            if ix > iy:
                DistancePointLine = iy
            else:
                DistancePointLine = ix
        else:
            # Intersecting point is on the line, use the formula
            ix = x1 + u * (x2 - x1)
            iy = y1 + u * (y2 - y1)
            DistancePointLine = lineMagnitude(px, py, ix, iy)

        return DistancePointLine

    def get_distance(self, a_line, b_line):
        """Get all possible distances between each dot of two lines and second line
        return the shortest
        """
        dist1 = self.DistancePointLine(a_line[:2], b_line)
        dist2 = self.DistancePointLine(a_line[2:], b_line)
        dist3 = self.DistancePointLine(b_line[:2], a_line)
        dist4 = self.DistancePointLine(b_line[2:], a_line)

        return min(dist1, dist2, dist3, dist4)

    def merge_lines_pipeline_2(self, lines):
        'Clusterize (group) lines'
        groups = []  # all lines groups are here
        # first line will create new group every time
        groups.append([lines[0]])
        # if line is different from existing gropus, create a new group
        merge_groups = []

        # print("line len %d" % len(lines))
        for line_new in lines[1:]:
          groupnum = -1
          mergegroup = []
          for group in groups:
            groupnum += 1
            for line_old in group:
              # print("----")
              # print(line_new)
              # print(line_old)
              if self.checker(line_new, line_old):
                mergegroup.append(groupnum)
                break
          mergegrouplen = len(mergegroup)
          # print("mg len %d" % mergegrouplen)
          if mergegrouplen == 0 or len(group) == 0:
            # add group
            groups.append([line_new])
          else:
            # merge all groups that line is in into mergegroup[0]
            for i in range(mergegrouplen-2):
              groups[mergegroup[0]].extend(groups[mergegroup[mergegrouplen-i-1]])
              del(groups[mergegroup[mergegrouplen-i-1]])
            # print("merged line into %d groups" % mergegrouplen)
            # add line to merged group
            groups[mergegroup[0]].append(line_new)
          # print("groups_len %d" % len(groups))
        # print("groups len %d" % len(groups))
        return groups

    def merge_lines_segments1(self, lines):
        """Sort lines cluster and return first and last coordinates
        """
        orientation = self.get_orientation(lines[0])

        # special case
        if(len(lines) == 1):
            return [lines[0][:2], lines[0][2:]]

        # [[1,2,3,4],[]] to [[1,2],[3,4],[],[]]
        points = []
        for line in lines:
            points.append(line[:2])
            points.append(line[2:])
        # if vertical
        # if 45 < orientation < 135:
        # if 15 < orientation < 165:
        if 15 < orientation < 165:
            #sort by y
            points = sorted(points, key=lambda point: point[1])
        else:
            #sort by x
            points = sorted(points, key=lambda point: point[0])

        # return first and last point in sorted group
        # [[x,y],[x,y]]
        return [points[0], points[-1]]

    def process_lines(self, lines):
        '''Main function for lines from cv.HoughLinesP() output merging
        for OpenCV 3
        lines -- cv.HoughLinesP() output
        img -- binary image
        '''
        lines_x = []
        lines_y = []
        # for every line of cv2.HoughLinesP()
        global bestrl, bestll, bestcl, bestvx, bestvy, curconf, curpos
        ll = False
        cl = False
        rl = False
        # print(bestll)
        # print(lines)
        # print("------")
        if lines is not None and bestrl is not None and bestcl is not None and bestll is not None:
            for line_i in [l[0] for l in lines]:
              # print(line_i)
              linell = (bestll[0][0],bestll[0][1], bestll[1][0], bestll[1][1])
              linecl = (bestcl[0][0],bestcl[0][1], bestcl[1][0], bestcl[1][1])
              linerl = (bestrl[0][0],bestrl[0][1], bestrl[1][0], bestrl[1][1])
              if self.checker(line_i, linell):
                ll = True
                lines_y.append(line_i)
              elif self.checker(line_i, linerl):
                rl = True
                lines_y.append(line_i)
              elif self.checker(line_i, linecl):
                cl = True
                lines_y.append(line_i)
              '''
              if rl and cl and ll:
                print("checker ll cl rl")
              elif cl and ll:
                print("checker ll cl   ")
              elif rl and ll:
                print("checker ll    rl")
              elif rl and cl:
                print("checker    cl rl")
              else:
                print("checker         ")
              '''
        if lines is not None and not (rl and cl and ll):
            lines_y = []
            for line_i in [l[0] for l in lines]:
                orientation = self.get_orientation(line_i)
                # print("post checker: orientation %d"% orientation)
                # if vertical
                if 15 < orientation < 165:
                    lines_y.append(line_i)
                else:
                    lines_x.append(line_i)
        elif lines is None: 
          return None

        lines_y = sorted(lines_y, key=lambda line: line[1])
        lines_x = sorted(lines_x, key=lambda line: line[0])
        merged_lines_all = []

        # for each cluster in vertical and horizantal lines leave only one line
        # for i in [lines_x, lines_y]:
        for i in [lines_y]:
                if len(i) > 0:
                    groups = self.merge_lines_pipeline_2(i)
                    merged_lines = []
                    # print(groups)
                    for group in groups:
                        merged_lines.append(self.merge_lines_segments1(group))

                    merged_lines_all.extend(merged_lines)
                    # print(merged_lines)

      # print("num merged lines %d " % len(merged_lines_all))
        return merged_lines_all

    def line_follower(self, lines):
        global width, height

        midpix = width / 2
        mindist = 10000
        minangle = 90
        cl = None
        if lines is not None:
          for line_i in [l[0] for l in lines]:
            angle = self.get_orientation(line_i)
            dist = math.hypot(line_i[0] - midpix, line_i[1] - height)
            dist2 = math.hypot(line_i[2] - midpix, line_i[3] - height)
            llen = math.hypot(line_i[0] - line_i[2], line_i[1] - line_i[3])
            # dist = math.hypot(line_i[0][0] - midpix, line_i[0][1] - height)
            # dist2 = math.hypot(line_i[1][0] - midpix, line_i[1][1] - height)
            # llen = math.hypot(line_i[1][0] - line_i[0][1], line_i[1][1] - line_i[0][1])
            mind = min(dist, dist2)

            ANGLE_THRESH = 60
            DIST_THRESH = 100
            # DIST_THRESH = 30
            # print("mind %d mindist %d angle %d minangle %d llen %d" % (mind, mindist, angle, minangle, llen))
            if ((mind < mindist or abs(angle-90) < minangle) and 
                llen > 10 and
                mind < DIST_THRESH and abs(angle-90) < ANGLE_THRESH):
              if ((mind < mindist and abs(angle-90) < minangle) or
               (abs(mindist - mind) > 2*abs((abs(angle-90) - minangle))) or
               (2*abs(mindist - mind) < abs((abs(angle-90) - minangle)))):
                mindist = mind
                minangle = abs(angle-90)
                cl = copy.deepcopy(line_i)
                cl = [[cl[0],cl[1]],[cl[2],cl[3]]]
        return cl

class ThrottleBase:
  def __init__(self):
    global minthrottle, ch_th_seq, emergency_stop, frame, cfg

    cfg = dk.load_config(config_path=os.path.expanduser('~/donkeycar/donkeycar/parts/RLConfig.py'))
    emergency_stop = False
    minthrottle = 0
    ch_th_seq = 0
    self.resetThrottleInfo()
    frame = None

  def optflow(self, old_frame, new_frame):
    # cap = cv.VideoCapture('slow.flv')
    # params for ShiTomasi corner detection
    feature_params = dict( maxCorners = 100,
                           qualityLevel = 0.3,
                           minDistance = 7,
                           blockSize = 7 )
    # Parameters for lucas kanade optical flow
    lk_params = dict( winSize  = (15,15),
                      maxLevel = 2,
                      criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    # Create some random colors
    color = np.random.randint(0,255,(100,3))
    # Take first frame and find corners in it
    # ret, old_frame = cap.read()
    old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)
    p0 = cv2.goodFeaturesToTrack(old_gray, mask = None, **feature_params)
    # Create a mask image for drawing purposes
    mask = np.zeros_like(old_frame)

    frame_gray = cv2.cvtColor(new_frame, cv2.COLOR_BGR2GRAY)
    # calculate optical flow
    p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)
    # Select good points
    good_new = p1[st==1]
    good_old = p0[st==1]
    # draw the tracks
    dist = 0
    numpts = 0
    frame1 = new_frame
    for i,(new,old) in enumerate(zip(good_new,good_old)):
        a,b = new.ravel()
        c,d = old.ravel()
        dist += math.hypot(a-c,b-d)
        numpts += 1
        # mask = cv2.line(mask, (a,b),(c,d), color[i].tolist(), 2)
        # frame1 = cv2.circle(frame1,(a,b),5,color[i].tolist(),-1)
    # img = cv2.add(new_frame,mask)
    # cv2.imshow('frame',img)
    # k = cv2.waitKey(30) & 0xff
    # Now update the previous frame and previous points
    # old_gray = frame_gray.copy()
    p0 = good_new.reshape(-1,1,2)
    # cv2.destroyAllWindows()
    if numpts != 0:
      dist /= numpts
    else:
      dist = 0
    print("optflow dist %f minthrot %d maxthrot %d" % (dist,minthrottle,maxthrottle))
    # note: PPF also used to ensure that moving
    # tried 0.75, 0.9, 1
    # OPTFLOWTHRESH = 0.8
    if dist > cfg.OPTFLOWTHRESH:
      return True
    else:
      return False

  def setEmergencyStop(self, TF):
      global emergency_stop
      emergency_stop = TF
      # turn off Emergency Stop for now
      if cfg.DISABLE_EMERGENCY_STOP:
        emergency_stop = False
      if emergency_stop:
        self.resetThrottleInfo()

  def emergencyStop(self):
      global emergency_stop
      return emergency_stop

  def setMinMaxThrottle(self, new_frame):
    global minthrottle, maxthrottle, check_throttle 
    global frame, battery_adjustment

    if frame is None:
      frame = new_frame
      print("frame is None")
      return False
    print("minthrottle %d" % minthrottle)
    if self.optflow(frame, new_frame):
      # car is moving, set maxthrottle if we need to
      if maxthrottle < 0:
        # if previouly not moving.
        # minthrottle += 2
        maxthrottle = minthrottle + 10
      check_throttle = False
      frame = new_frame
      return True
    # we're not moving. Reset maxthrottle. Reset throttle via optflow.
    frame = new_frame
    minthrottle += cfg.OPTFLOWINCR
    maxthrottle = -1
    return False

  def getThrottleInfo(self):
    global minthrottle, maxthrottle, battery_adjustment
    return minthrottle, maxthrottle, battery_adjustment

  def resetThrottleInfo(self):
    global minthrottle, maxthrottle, check_throttle, battery_adjustment
    global battery_count, ch_th_seq , cfg

    # take about a second to find new minthrottle
    minthrottle = max(cfg.MINMINTHROT, (minthrottle-1))
    maxthrottle = -1
    battery_adjustment = 0
    battery_count = 0
    ch_th_seq += 1
    check_throttle = True

  def throttleCheckInProgress(self):
    global maxthrottle, check_throttle
    if maxthrottle < 0 or check_throttle:
      return True
    return False

  def adjustForBattery(self,pixPerFrame = -1):
    global battery_adjustment, ch_th_seq, maxthrottle, battery_count
    # DESIREDPPF = 35
    # MAXBATADJ  = .10
    # MAXBATCNT  = 1000
    ch_th_seq = 0  # postpone opt flow throttle check
    if pixPerFrame > 0 and pixPerFrame < cfg.DESIREDPPF and battery_adjustment < cfg.MAXBATADJ and maxthrottle > 0:
      battery_adjustment += cfg.BATADJ
      print("BATTERY ADJUSTMENT %f" % battery_adjustment)
      battery_count = 0
    else:
      battery_count += 1
      if battery_count > cfg.MAXBATCNT:
        print("BATTERY ADJUSTMENT %f" % battery_adjustment)
        battery_count = 0
        battery_adjustment += .01

  def checkThrottle(self,expected_throttle):
      global battery_adjustment, ch_th_seq, maxthrottle
      ch_th_seq += 1
      # CHECK_THROTTLE_THRESH = 20
      if ch_th_seq % cfg.CHECK_THROTTLE_THRESH == 0 and expected_throttle >= minthrottle / 100:
        check_throttle = True
        print("CHECK THROTTLE")
        return False
      else:
        # print("seq %d th %f minth %f" % (ch_th_seq, expected_throttle, minthrottle))
        return True

class LaneLines:

  #############################
  # derived from https://bryceboe.com/2006/10/23/line-segment-intersection-algorithm/

  def ccw(self, A,B,C):
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
  # return (C.y-A.y) * (B.x-A.x) > (B.y-A.y) * (C.x-A.x)

  # Return true if line segments AB and CD intersect
  def intersect(self, line1, line2):
    A = line1[0]
    B = line1[1]
    C = line2[0]
    D = line2[1]
    return self.ccw(A,C,D) != self.ccw(B,C,D) and self.ccw(A,B,C) != self.ccw(A,B,D)

  ###############
  # where infinite lines would intersect
  def intersection (self, line1, line2):
    D = (line1[0][0] - line1[1][0]) * (line2[0][1] - line2[1][1]) - (line1[0][1] - line1[1][1]) * (line2[0][0] - line2[1][0])
    A = (line1[0][0] *line1[1][1]) - (line1[0][1] *line1[1][0])
    B = (line2[0][0] *line2[1][1]) - (line2[0][1] *line2[1][0])
    # print(line1)
    # print(line2)
    if D != 0:
      x = int (A * (line2[0][0] - line2[1][0]) - B*(line1[0][0] - line1[1][0]) ) / D
      y = int (A * (line2[0][1] - line2[1][1]) - B*(line1[0][1] - line1[1][1]) ) / D
      # print("intersect %d %d" % (x,y))
      return x, y
    else:
      # print("no intersect")
      return -1000, -1000

  #############################
  # from https://github.com/dmytronasyrov/CarND-LaneLines-P1/blob/master/P1.ipynb
  def getROI(self,img):
    global width, height, roiheight
    # w 160 h 120
    # remove top 40 - 50 lines
    # croptop = 45
    croptop = 44
    
    width = img.shape[1]
    height = img.shape[0]
    roiheight = height - croptop
    # print("w %d h %d" % (width, height))
    roi_img = img[croptop:height, 0:width]
    return roi_img

  # find potential vanishing point and lane width
  def vanishing_point2(self, line1, line2):
    global roiheight, width, laneWidth, donkeyvpangle

    midpix = int(width / 2)
    x,y = self.intersection(line1,line2)
    donkeyvpl = ((midpix, roiheight),(x,y))
    donkeyvpangle = self.orientation(donkeyvpl)

    # find width
    if donkeyvpangle < 90:
      slope = donkeyvpangle + 90
    else:
      slope = donkeyvpangle - 90
    slope = math.tan(math.radians(slope))

    # if donkeyvpangle != 90:
    dkvpy =  midpix - roiheight * slope
    donkeyhorizline =  ((midpix, roiheight),(0, dkvpy))
    # else:
      # donkeyhorizline =  ((line3[0][0], roiheight),(0, roiheight))
    l1x, l1y = self.intersection(donkeyhorizline,line1)
    l2x, l2y = self.intersection(donkeyhorizline,line2)

    lanewidth1 = math.hypot(l1x - l2x, l1y - l2y)
  # print("vp2: x %d y %d lane width %f LW %f" % (x,y,lanewidth1, laneWidth))
    return x,y, donkeyvpangle, lanewidth1


  # if 3 lines have same vanishing point, then we are confident of result
  # we can also compute width of track and pixels per frame speed
  def vanishing_point(self, line1, line2, line3):
    global roiheight, width, pixPerFrame, PPFx, PPFy, maxppfy, laneWidth 
    global dklinept, VPx, VPy, donkeyvpangle

    maxdiffallowed = 10
    x12,y12 = self.intersection(line1,line2)
    x13,y13 = self.intersection(line1,line3)
    x23,y23 = self.intersection(line2,line3)
    if x12 == -1000 or y12 == -1000 or x13 == -1000 or y13 == -1000 or x23 == -1000 or y23 == -1000:
      # print("VP False ")
      return False, -1000, -1000
    xmaxdif = max(abs(x12-x13), abs(x12-x23), abs(x13-x23) )
    ymaxdif = max(abs(y12-y13), abs(y12-y23), abs(y13-y23)) 
    ###############
    # find lane width, and transformed parallel L/C/R lines
    ###############
    midpix = int(width / 2)
    vpx = int((x12+x13+x23)/3)
    vpy = int((y12+y13+y23)/3)
    donkeyvpl = ((midpix, roiheight),(vpx,vpy))
    donkeyvpangle = self.orientation(donkeyvpl)
    if (VPx is None):
      VPx = vpx
      VPy = vpy
    else:
      VPx = .8*VPx + .2*vpx
      VPy = .8*VPy + .2*vpy
    if donkeyvpangle < 90:
      slope = donkeyvpangle + 90
    else:
      slope = donkeyvpangle - 90
    slope = math.tan(math.radians(slope))

    ###############
    # find transfomed pixels per frame 
    ###############

    if PPFx is None:
      maxppfy = 0
      if line2[1][1] >= roiheight - 1:
      # print("point1y > point0y: PASS")
        pass
      elif (line2[0][1] < line2[1][1]):
        # most likely TRUE
      # print("point1y > point0y")
        PPFx = line2[1][0]
        PPFy = line2[1][1]
      else:
        # most likely FALSE
        # should add identical logic here too
        PPFx = line2[0][0]
        PPFy = line2[0][1]
      # print("point0y %d > point1y %d !!!" % (PPFy, line2[1][1]))
    else:
      if (line2[0][1] < line2[1][1]):
        if line2[1][1] < roiheight - 1:
          # note 15, 75, 90 right triangle
          ppfx = line2[1][0] - PPFx
          ppfy = line2[1][1] - PPFy
          if ppfy > 0:
            if ppfy > maxppfy:
              maxppfy = ppfy
            # pixPerFrame = math.hypot(ppfx, ppfy)
          # print("point1y %d > point0y: PPF %f" %(line2[1][1], maxppfy))
        else:
          # the closer we get to the next dash, the higher the num pix.
          # use weighted average of max to estimate birds-eye view num pix
          if pixPerFrame < 0:
            pixPerFrame = maxppfy
          elif maxppfy > 0:
            pixPerFrame = .8*pixPerFrame + .2*maxppfy
          # print("reset PPF: PPF = %d" % pixPerFrame)

          # adjust for battery depletion
          global TB
          TB.adjustForBattery(pixPerFrame)

          #reset
          PPFx = None
          PPFy = None
          maxppfy = 0
        PPFx = line2[1][0]
        PPFy = line2[1][1]
      else:
        # Most likely False, but not always
        # should add identical logic here too
        PPFx = line2[0][0]
        PPFy = line2[0][1]
      # print("point0y %d > point1y %d !!!" % (PPFy, line2[1][1]))

    # get y intersect
    # if donkeyvpangle != 90:
    y =  midpix - roiheight * slope
    donkeyhorizline =  ((midpix, roiheight),(0, y))

    l1x, l1y = self.intersection(donkeyhorizline,line1)
    l2x, l2y = self.intersection(donkeyhorizline,line2)
    l3x, l3y = self.intersection(donkeyhorizline,line3)
    # donkeyvpangle
    lanewidth1 = math.hypot(l1x - l2x, l1y - l2y)
    lanewidth2 = math.hypot(l3x - l2x, l3y - l2y)
    lanewidth3 = math.hypot(l3x - l1x, l3y - l1y)
    dklinept = ((l1x,l1y),(l2x,l2y),(l3x,l2y),(midpix,roiheight),(vpx,vpy))
    if abs(lanewidth1 + lanewidth2 - lanewidth3) < 5: 
      # print("lw : %f, %f = %f + %f, %f angle %f" % (lanewidth3, lanewidth2 + lanewidth1, lanewidth2, lanewidth1, lanewidth3/2, donkeyvpangle))
      lw = lanewidth3
    elif abs(lanewidth1 - lanewidth2 - lanewidth3) < 5: 
      # print("lw : %f, %f = %f + %f, %f angle %f" % (lanewidth1, lanewidth2 + lanewidth3, lanewidth2, lanewidth3, lanewidth1/2, donkeyvpangle))
      lw = lanewidth1
    elif abs(lanewidth2 - lanewidth1 - lanewidth3) < 5: 
      # print("lw : %f, %f = %f + %f, %f angle %f" % (lanewidth2, lanewidth1 + lanewidth3, lanewidth1, lanewidth3, lanewidth2/2, donkeyvpangle))
      lw = lanewidth2
    else:
      lw = -1
    
    if xmaxdif < maxdiffallowed and ymaxdif < maxdiffallowed:
      MAXLANEWIDTH = 400  # should be much smaller
      if lw >=0 and lw < MAXLANEWIDTH and 60 < donkeyvpangle < 120:
        if laneWidth < 0:
          laneWidth = lw/2
        else:
          laneWidth = .8 * laneWidth + .2*lw/2
    # print("lane width %f" % laneWidth)
    
    # print("VP True %d %d" % ( int((x12+x13+x23)/3), int((y12+y13+y23)/3)))
      return True, vpx, vpy
    else:
      # print("VP False %d %d" % (xmaxdif, ymaxdif))
      return False, xmaxdif, ymaxdif

  def is_vanishing_point(self):
    global bestrl, bestll, bestcl
    VP = False
    if bestll is not None and bestcl is not None and bestrl is not None:
      VP, x, y = self.vanishing_point(bestll, bestcl, bestrl)
    return VP

  def is_vanishing_point2(self):
    global bestrl, bestll, bestcl, laneWidth
    # print("laneWidth %d" % laneWidth)
    if laneWidth < 0:
      return True
    if bestcl is not None and bestrl is not None:
      x,y, dkvp2angle, lanewidth1 = self.vanishing_point2(bestcl,bestrl)
      # print("vp2a: x %d y %d lane width %f LW %f" % (x,y,lanewidth1, laneWidth))
      return True
    if bestcl is not None and bestll is not None:
      x,y, dkvp2angle, lanewidth1 = self.vanishing_point2(bestll,bestcl)
      # print("vp2b: x %d y %d lane width %f LW %f" % (x,y,lanewidth1, laneWidth))
      return True
    return False

  def linelen(self,line):
     if line is None:
       return -1
     return math.hypot(line[0][0] - line[1][0], line[0][1] - line[1][0])

  def orientation(self, line):
     hb = HoughBundler()
     line_a = (line[0][0], line[0][1], line[1][0], line[1][1])
     return hb.get_orientation(line_a)

  def check(self, line1, line2):
        hb = HoughBundler()
        lineA = (line1[0][0],line1[0][1], line1[1][0], line1[1][1])
        lineB = (line2[0][0],line2[0][1], line2[1][0], line2[1][1])
        return hb.checker(lineA, lineB)

  def closestX(self, line):
      if (line[0][1] < line[0][1]):
        x = line[0][0]
      else:
        x = line[1][0]
      return x

  def steerByLine(self, line):
      global width, laneWidth

      angle = self.orientation(line)
      denom = 40
      midpix = int(width / 2)
      if angle < 60:
        steering = 1
      elif angle > 120:
        steering = -1
      elif angle <= 90:
        steering = min(max( ((self.closestX(line) + laneWidth)/2 - midpix) / denom, -1),1)
      elif angle > 90:
        steering = min(max( ((self.closestX(line) - laneWidth)/2 - midpix) / denom, -1),1)
      return steering


  def setSteerThrottle(self, pos, ll, cl, rl, conf):
    global width, height, lline, cline, rline, roiheight, laneWidth, TB

    steering = 0.0
    minthrottle, maxthrottle, battery_adjustment = TB.getThrottleInfo()
    if TB.throttleCheckInProgress():
      # still initiallizing min/max throttle
      throttle = minthrottle
    else:
      throttle = minthrottle + conf
      if throttle > maxthrottle:
        throttle = maxthrottle
      # print("throt %f conf %f minth %f maxthrottle %d" % (throttle, conf, minthrottle, maxthrottle))
    # for self,sim
    throttle /= 100
    midpix = int(width / 2)

    str = "lw %d " % laneWidth
    if ll is not None:
      str += "; l %d - %d " % (ll[0][0], ll[1][0])
    if cl is not None:
      str += "; c %d - %d " % (cl[0][0], cl[1][0])
    if rl is not None:
      str += "; r %d - %d " % (rl[0][0], rl[1][0])
    # rl and ll can be same!
    # cl and rl can be reversed!
    # lw varies too much
    # print(str)
    if cl is not None:
      angle = self.orientation(cl)
      denom = 40
      steering = min(max((self.closestX(cl) - midpix) / denom,-1),1)
      llen = self.linelen(cl)
      if angle < 60 and llen > 20:
        steering = 1
      elif angle > 120 and llen > 20:
        steering = -1
      # steering = self.steerByLine(cl, 0)
    elif ll is not None and rl is not None:
      llsteering = self.steerByLine(ll)
      rlsteering = self.steerByLine(rl)
      steering = (llsteering + rlsteering) / 2
      # steering = ( ((self.closestX(ll) + self.closestX(rl))/2 - midpix) / 80)
    elif ll is not None :
      steering = self.steerByLine(ll)
    elif rl is not None :
      steering = self.steerByLine(rl)
    '''
    Mapping: 
      do projection for the Lines only.
      Factor in speed, steering
      Get total speed/steering

    Remove pictures/movies
    '''
    # if on a turn, need to add throttle
    if abs(steering ) > .9:
      throttle += cfg.TURNADJ
      # print("TurnAdj %f BatAdj %f" % (cfg.TURNADJ, battery_adjustment))
    elif abs(steering ) > .8:
      throttle += cfg.TURNADJ / 2
      # print("TurnAdj %f BatAdj %f" % (cfg.TURNADJ/2, battery_adjustment))
    # else:
      # print("TurnAdj 0.00 BatAdj %f" % battery_adjustment)
    throttle += battery_adjustment

    if pos == 0 or pos == 6:
      throttle = 0.0

    return conf, steering, throttle 

  def setCurPos(self, bestll, bestcl, bestrl, pos):
    global width, height, laneWidth

    # ARD TODO: not right, depends on angle of lines

    midpix = width / 2
    curpos = -1
    #  -|---|---|
    #  0|123|345|6
    if bestcl is not None and bestrl is not None and bestll is not None:
      difx = (bestcl[0][0] - bestll[0][0]) / 3
      difx2 = (bestrl[0][0] - bestcl[0][0]) / 3
      if midpix <= (bestll[0][0]):
        curpos = 0
        print("0a")
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)
        # print("bestrl")
        # print(bestrl)
      elif midpix <= (bestll[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestll[0][0] + 2*difx) :
        curpos = 2
      elif midpix <= (bestcl[0][0] + difx2) :
        curpos = 3
      elif midpix <= (bestcl[0][0] + 2*difx2) :
        curpos = 4
      elif midpix <= (bestrl[0][0]) :
        curpos = 5
      else:
        print("6a")
        curpos = 6
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)
        # print("bestrl")
        # print(bestrl)

    elif bestll is not None and bestcl is not None and bestrl is None:
      difx = (bestcl[0][0] - bestll[0][0]) / 3
      if midpix <= (bestll[0][0]):
        curpos = 0
        print("0b")
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)
      elif midpix <= (bestll[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestll[0][0] + 2*difx) :
        curpos = 2
      elif midpix < (bestcl[0][0] + difx ) :
        curpos = 3
      elif midpix <= (bestcl[0][0] + 2*difx) :
        curpos = 4
      elif midpix <= (bestcl[0][0] + 3*difx) :
        curpos = 5
      else:
        print("6b")
        curpos = 6
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)

    elif bestll is None and bestcl is not None and bestrl is not None:
      difx = (bestrl[0][0] - bestcl[0][0]) / 3
      if midpix < (bestcl[0][0] - 3*difx) :
        curpos = 0
        print("0c")
        # print("bestcl")
        # print(bestcl)
        # print("bestrl")
        # print(bestrl)
      elif midpix <= (bestcl[0][0] - 2*difx) :
        curpos = 1
      elif midpix <= (bestcl[0][0] - difx) :
        curpos = 3
      elif midpix <= (bestcl[0][0] + 2*difx) :
        curpos = 4
      elif midpix <= (bestrl[0][0] + 6*difx) :
        curpos = 5
      else:
        curpos = 6
        print("6c")
        # print("bestcl")
        # print(bestcl)
        # print("bestrl")
        # print(bestrl)

    elif bestll is not None and bestcl is not None and bestrl is None:
      print("setCurPos: huh?")
      difx = (bestrl[0][0] - bestcl[0][0]) / 3
      if midpix < (bestll[0][0] ) :
        print("0d")
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)
        curpos = 0
      elif midpix <= (bestll[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestll[0][0] + 2*difx) :
        curpos = 2
      elif midpix <= (bestll[0][0] + 4*difx) :
        curpos = 3
      elif midpix <= (bestcl[0][0] + 2*difx) :
        curpos = 4
      elif midpix <= (bestrl[0][0] + 6*difx) :
        curpos = 5
      else:
        print("6d")
        # print("bestll")
        # print(bestll)
        # print("bestcl")
        # print(bestcl)
        curpos = 6

    elif bestll is not None and bestcl is None and bestrl is not None:
      difx = (bestrl[0][0] - bestll[0][0]) / 6
      if midpix < (bestll[0][0]):
        curpos = 0
        print("0e")
        # print("bestll")
        # print(bestll)
        # print("bestrl")
        # print(bestrl)
      elif midpix <= (bestll[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestll[0][0] + 2*difx) :
        curpos = 2
      elif midpix <= (bestrl[0][0] - 2*difx) :
        curpos = 3
      elif midpix <= (bestrl[0][0] - difx) :
        curpos = 4
      elif midpix <= (bestrl[0][0] ):
        curpos = 5
      else:
        curpos = 6
        print("6e")
        # print("bestll")
        # print(bestll)
        # print("bestrl")
        # print(bestrl)

    elif bestll is not None and bestcl is None and bestrl is None:
      difx = laneWidth / 3
      if midpix < (bestll[0][0] ) :
        curpos = 0
        print("0f")
        # print("bestll")
        # print(bestll)
      elif midpix <= (bestll[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestll[0][0] + 2*difx) :
        curpos = 2
      elif midpix <= (bestll[0][0] + 4*difx) :
        curpos = 3
      elif midpix <= (bestll[0][0] + 5*difx) :
        curpos = 4
      elif midpix <= (bestll[0][0] + 6*difx) :
        curpos = 5
      else:
        curpos = 6
        print("6f")
        # print("bestll")
        # print(bestll)

    elif bestll is None and bestcl is not None and bestrl is None:
      difx = laneWidth / 3
      if midpix < (bestcl[0][0] ) :
        curpos = 0
        print("0g")
        # print("bestcl")
        # print(bestcl)
      elif midpix <= (bestcl[0][0] + difx) :
        curpos = 1
      elif midpix <= (bestcl[0][0] + 2*difx) :
        curpos = 2
      elif midpix <= (bestcl[0][0] + 4*difx) :
        curpos = 3
      elif midpix <= (bestcl[0][0] + 5*difx) :
        curpos = 4
      elif midpix <= (bestcl[0][0] + 6*difx) :
        curpos = 5
      else:
        curpos = 6
        print("6g")
        # print("bestcl")
        # print(bestcl)

    elif bestll is None and bestcl is None and bestrl is not None:
      difx = laneWidth / 3
      if midpix <= (bestrl[0][0] - 6*difx) :
        curpos = 0
        print("0h")
        # print("bestrl")
        # print(bestrl)
      elif midpix <= (bestrl[0][0] - 5*difx) :
        curpos = 1
      elif midpix <= (bestrl[0][0] - 4*difx) :
        curpos = 2
      elif midpix <= (bestrl[0][0] - 2*difx) :
        curpos = 3
      elif midpix <= (bestrl[0][0] - difx) :
        curpos = 4
      elif midpix < (bestrl[0][0] ) :
        curpos = 5
      else:
        curpos = 6
        print("6h")
        # print("bestrl")
        # print(bestrl)

    if curpos == 6 and pos <= 1:
      curpos = 0
    elif curpos == 0 and pos >= 5:
      curpos = 6
    elif (curpos - pos) > 1:
      curpos = pos + 1
    elif (curpos - pos) < -1:
      curpos = pos - 1

  # print("curpos %d pos %d" %(curpos, pos))
    return curpos

  def strpos(self, pos):
    if pos == 0:
      return "off course left"
    elif pos == 1:
      return "near left line"
    elif pos == 2:
      return "left of center"
    elif pos == 3:
      return "center"
    elif pos == 4:
      return "right of center"
    elif pos == 5:
      return "near right line"
    elif pos == 6:
      return "off course right"

  def lrcsort(self, lines):
    global lline, rline, cline 

    # curpos ('l/r/c of l/r/c line': 0-8
    curlline = []
    currline = []
    curcline = []
    lassigned = False
    rassigned = False
    cassigned = False
    # print("lines:")
    # print(lines)
    unassigned = []
    if lines is not None:
      for line in lines:
        lassigned = False
        rassigned = False
        cassigned = False
        # print("lines:")
        if line is not None:
            for i in range(3):
              # check the easy way first
              # are we close to one of the last 3 readings
              if lline[i] is not None and self.check(lline[i], line):
              # print("lcheck")
                curlline.append(line )
                lassigned = True
                break
              elif rline[i] is not None and self.check(rline[i], line):
              # print("rcheck1")
                currline.append(line )
                rassigned = True
                break
              elif cline[i] is not None and self.check(cline[i], line):
                # ARD TODO: problem if cl was really rl or ll
                curcline.append(line )
                cassigned = True
                break
            if not (cassigned or rassigned or lassigned):
              # print(line)
            # print("unassigned")
              unassigned.append(line )

      for line in unassigned:
      # for line_i in unassigned:
       # for line in line_i:
        # print("line: %d %d" % (((line[1][1]) - (line[0][1])), (line[1][0] - (line[0][0]))))
        # print(line)
        deg = self.orientation(line)
      # print("lrc: deg %d" % deg)
        if deg <= 90:
          if not lassigned:
          # print("lrc: append ll")
            curlline.append(line )
        elif deg > 90 and deg < 180:
          if not rassigned:
          # print("lrc: append rl")
            currline.append(line )
        if not cassigned:
        # print("lrc: append cl")
          curcline.append(line )
    return currline, curlline, curcline
  
  def lrclines(self, currline, curlline, curcline, roi):
    global TB
    global lline, rline, cline, conf, pos, throttle, steering, conf, width, height
    global bestrl, bestll, bestcl, bestvx, bestvy, curconf, curpos
    global VPx, VPy, laneWidth, dklinept, donkeyvpangle

    maxpix = width 
    midpix = maxpix / 2
    rllen = len(currline)
    lllen = len(curlline)
    cllen = len(curcline)
    done = False
    bestrl = None
    bestll = None
    bestcl = None
    bestvx = 10000
    bestvy = 10000
    bestvprl = None
    bestvpll = None
    bestvpcl = None
    curconf = 0
    curpos = 3
  # print("len ll %d cl %d rl %d"%(lllen, cllen, rllen))
    if rllen > 0 and lllen > 0 and cllen > 0:
      for rl in currline:
        rldeg = self.orientation(rl)
        for ll in curlline:
          lldeg = self.orientation(ll)
          '''
          Check for the perfect lrc
          '''
          # if rl[0][0] <= ll[0][0] or rl[1][0] <= ll[1][0]:
          if ((rl[0][0] <= ll[0][0] and rl[1][0] >= ll[1][0]) or
              (rl[0][0] >= ll[0][0] and rl[1][0] <= ll[1][0])):
          # print("F1")
            continue
          if rl[0][0] <= midpix and (ll[0][0] >= midpix or ll[1][0] >= midpix):
          # print("F2")
            continue
          for cl in curcline:
            cldeg = self.orientation(cl)
            '''
             it is possible that previous cl was really ll or rl.
             Allow for this possibility.
            '''
            if ((rl[0][0] <= cl[0][0] and rl[1][0] >= cl[1][0]) or
                (rl[0][0] >= cl[0][0] and rl[1][0] <= cl[1][0])):
            # print("F3")
              continue
            if ((ll[0][0] >= cl[0][0] and ll[1][0] <= cl[1][0]) or
                (ll[0][0] <= cl[0][0] and ll[1][0] >= cl[1][0])):
            # print("F4")
            # print(cl)
            # print(ll)
              continue
            if ll[0][0] >= midpix and (cl[0][0] >= midpix or cl[1][0] >= midpix):
            # print("F5")
              continue
            # print("rl, cl, ll:")
            # print(rl)
            # print(cl)
            # print(ll)
            vb,vx,vy = self.vanishing_point(rl, cl, ll)
            if vb:
              # found vanishing point, clear emergency start
              TB.setEmergencyStop(False) 
              curpos = 3
              bestrl = rl
              bestll = ll
              bestcl = cl
              if ((abs(bestrl[0][0] - bestcl[0][0]) > laneWidth / 2) and
                  (abs(bestcl[0][0] - bestll[0][0]) > laneWidth / 2)):
                # print("VP LL")
                # print(bestll)
                # print("VP CL")
                # print(bestcl)
                # print("VP RL")
                # print(bestrl)

                curconf = cfg.MAX_ACCEL
                curpos = 3
                done = True
            elif (vx+vy) < (bestvx+bestvy):
              bestvprl = rl
              bestvpll = ll
              bestvpcl = cl
              bestvx = vx
              bestvy = vy
              donkeyvpangle = None
              dklinept = None
              curpos = 3
              curconf = min(cfg.MAX_ACCEL,int(100/(bestvx + bestvy)))
            if done:
              break
          if done:
            break
        if done:
          break
    if done:
      pass
    elif rllen == 1 and lllen == 1 and cllen == 0:
      bestrl = currline[0]
      bestll = curlline[0]
      rldeg = self.orientation(bestrl)
      lldeg = self.orientation(bestll)
      x,y, dkangle, lanewidth1 = self.vanishing_point2(bestrl,bestll)
    # print("Possible vp2 %d" % y)
      if bestrl[0][0] <= bestll[0][0] or bestrl[1][0] <= bestll[1][0]:
        if abs((rldeg - 90) - (90 - lldeg)) < 10 and bestrl[0][0] > 120 and bestll[0][0] < 40:
          bestcl = [[0 for x in range[2]] for y in range[2]]
          bestcl[0][0] = int((bestrl[0][0] + bestll[0][0])/2)
          bestcl[0][1] = int((bestrl[0][1] + bestll[0][1])/2)
          bestcl[1][0] = int((bestrl[1][0] + bestll[1][0])/2)
          bestcl[1][1] = int((bestrl[1][1] + bestll[1][1])/2)
        # print("estimated cl")
          for i in range(3):
            if self.check(cline[i], line):
              done = True
              curconf = min(cfg.MAX_ACCEL,int(100/(bestvx + bestvy)))
              curpos = 3
        if not done and pos[2] < 2:
          bestcl = bestrl
          bestrl = None
          curpos = 1
        elif not done and pos[2] > 3:
          bestcl = bestll
          bestll = None
          curpos = 5

    elif (rllen >= 1 or lllen >= 1) and cllen >= 1:
    # print("Try again: len ll %d cl %d rl %d"%(lllen, cllen, rllen))
      bestval = 10000
      bestx = 10000
      besty = 10000
      bestw = 10000
      lanewidth1 = None
      lwmaxdif = 10000
      for cl in curcline:
        cldeg = self.orientation(cl)
        if (lllen >= 1):
          for ll in curlline:
            lldeg = self.orientation(ll)
            '''
            if lldeg > cldeg:
              continue
            if ll[0][0] > cl[0][0]:
              continue
            '''
            if bestcl is None or 120 > cldeg > 60:
              x,y, donkeyvpangle, lanewidth1 = self.vanishing_point2(ll,cl)
              if (VPy is None or besty > abs(VPy - y)) and y <= 0:
              # print("possibe vp2")
                if laneWidth is None or abs(lanewidth1 - laneWidth) < lwmaxdif or abs(lanewidth1/2 - laneWidth) < lwmaxdif:
                # print("found possible best cl, ll")
                  lwmaxdif = min(abs(lanewidth1 - laneWidth), abs(lanewidth1/2 - laneWidth))
                  if lwmaxdif == abs(lanewidth1/2 - laneWidth):
                    bestcl = None
                    bestrl = cl
                  else:
                    bestcl = cl
                    bestrl = None
                  bestll = ll
                  bestx = x
                  besty = y
                  bestlw = lanewidth1
          '''
          if (VPx is None):
            VPy = besty
            VPx = bestx
            # laneWidth = lanewidth1
          else:
            VPy = .8*VPy + .2*besty
            VPx = .8*VPx + .2*bestx
            if laneWidth is None or lanewidth1 is None:
              pass
            else:
              if abs(lanewidth1 - laneWidth) < lwmaxdif:
              # laneWidth = .8 * laneWidth + .2*lanewidth1
              elif abs(lanewidth1/2 - laneWidth) < lwmaxdif:
              # laneWidth = .8 * laneWidth + .2*lanewidth1/2
          '''
        if (rllen >= 1):
          for rl in currline:
            rldeg = self.orientation(rl)
            '''
            if rldeg < cldeg:
              continue
            if rl[0][0] < cl[0][0]:
              continue
            '''
            if bestcl is None or 120 > cldeg > 60:
              x,y, donkeyvpangle, lanewidth1 = self.vanishing_point2(rl,cl)
              if (VPy is None or besty > abs(VPy - y)) and y <= 0:
              # print("Possibe vp2")
                if laneWidth < 0 or abs(lanewidth1 - laneWidth) < lwmaxdif or abs(lanewidth1/2 - laneWidth) < lwmaxdif:
                  lwmaxdif = min(abs(lanewidth1 - laneWidth), abs(lanewidth1/2 - laneWidth))
                # print("Found possible best cl, rl")
                  if laneWidth > 0 and lwmaxdif == abs(lanewidth1/2 - laneWidth):
                    bestcl = None
                    bestll = cl
                  else:
                    bestcl = cl
                    bestll = None
                  bestrl = rl
                  bestx = x
                  besty = y
                  bestlw = lanewidth1
        # apply to best of rllen >= 1 and llen >= 1
        if (VPx is None):
          VPy = besty
          VPx = bestx
          # laneWidth = lanewidth1
        else:
          VPy = .8*VPy + .2*besty
          VPx = .8*VPx + .2*bestx
          # print("lw : vp2 %d" % lanewidth1)
          ''' 
          # ARD: Need to use 3-line VP.
          # 2-line vp2 laneWidth is sometimes way off. 
          # Need to make sure within a range and angle
          # For most tracks, not worthwhile
          if laneWidth is None or lanewidth1 is None:
            pass
          else:
            if abs(lanewidth1 - laneWidth) < lwmaxdif:
              # laneWidth = .8 * laneWidth + .2*lanewidth1
            elif abs(lanewidth1/2 - laneWidth) < lwmaxdif:
              # laneWidth = .8 * laneWidth + .2*lanewidth1/2
          ''' 

    elif not done:
    # print("not done")
      self.throttle = 0
      self.steering = 0
      
      bestcl = None
      if curcline is not None:
        mindif = 10000
        maxlen = 0
        for cl in curcline:
          cldeg = self.orientation(cl)
          if cline[2] is not None:
            lastcldeg = self.orientation(cline[2])
            if abs(cldeg - lastcldeg) < mindif:
              bestcl = cl
              mindif = abs(cldeg - lastcldeg) 
            # print("cl mindif %d" % mindif)
          else:
            cllen = math.hypot(cl[0][0] - cl[1][0], cl[1][1] - cl[1][1])
            if cllen > maxlen:
              maxlen = cllen
              bestcl = cl
            # print("cl maxlen %d" % mindif)
      bestll = None
      if curlline is not None:
        mindif = 10000
        maxlen = 0
        for ll in curlline:
          lldeg = self.orientation(ll)
          if lline[2] is not None:
            lastlldeg = self.orientation(lline[2])
            if abs(lldeg - lastlldeg) < mindif:
              bestll = ll
              mindif = abs(lldeg - lastlldeg) 
            # print("ll mindif %d" % mindif)
          else:
            lllen = math.hypot(ll[0][0] - ll[1][0], ll[1][1] - ll[1][1])
            if lllen > maxlen:
              bestll = ll
              maxlen = lllen
            # print("ll maxlen %d" % mindif)
      bestrl = None
      if currline is not None:
        mindif = 10000
        maxlen = 0
        for rl in currline:
          rldeg = self.orientation(rl)
          if rline[2] is not None:
            lastrldeg = self.orientation(rline[2])
            if abs(rldeg - lastrldeg) < mindif:
              bestrl = rl
              mindif = abs(rldeg - lastrldeg) 
            # print("rl mindif %d" % mindif)
          else:
            rllen = math.hypot(rl[0][0] - rl[1][0], rl[1][1] - rl[1][1])
            if rllen > maxlen:
              bestrl = rl
              maxlen = rllen
            # print("rl maxlen %d" % mindif)
      curconf = 0

    if bestrl is not None and bestcl is not None and bestrl[0][0] < bestcl[0][0] and bestrl[1][0] < bestcl[1][0]:
      tmp = bestcl
      bestcl = bestrl
      bestrl = tmp
    if bestll is not None and bestcl is not None and bestcl[0][0] < bestll[0][0] and bestcl[1][0] < bestll[1][0]:
      tmp = bestll
      bestll = bestcl
      bestcl = tmp
    if bestrl is not None and bestll is not None and bestrl[0][0] < bestll[0][0] and bestrl[1][0] < bestll[1][0]:
      tmp = bestll
      bestll = bestrl
      bestrl = tmp
    if bestrl is not None and bestll is not None and bestrl[0][0] == bestll[0][0] and bestrl[1][0] == bestll[1][0]:
      # bestrl and bestll are the same
      if midpix > bestll[0][0]:
        bestrl = None
      else:
        bestll = None

    if  ((bestrl is not None and bestll is not None and bestcl is None and abs(bestrl[0][0] - bestll[0][0]) < laneWidth / 2) and abs(bestrl[0][0] - bestll[0][0]) > laneWidth / 6):
      # bestrl is too close to bestll. One is center
      for i in (2,1,0):
        foundR = False
        foundL = False
        foundC = False
        if bestll is not None and cline[i] is not None and self.check(bestll, cline[i]):
          bestcl = bestll
          bestll = None
          foundC = True
          break
        if bestrl is not None and cline[i] is not None and self.check(bestrl, cline[i]):
          bestcl = bestrl
          bestrl = None
          foundC = True
          break
        if bestll is not None and lline[i] is not None and self.check(bestll, lline[i]):
          foundL = True
        if bestrl is not None and rline[i] is not None and self.check(bestrl, rline[i]):
          foundR = True
      if foundC:
        pass
      elif foundL and not foundR:
        bestcl = bestrl
        bestrl = None
      elif not foundL and foundR:
        bestcl = bestll
        bestll = None
          
    if  ((bestrl is not None and bestll is not None and abs(bestrl[0][0] - bestll[0][0]) < laneWidth / 6) or
        (bestcl is not None and bestll is not None and abs(bestcl[0][0] - bestll[0][0]) < laneWidth / 6) or
        (bestcl is not None and bestrl is not None and abs(bestcl[0][0] - bestrl[0][0]) < laneWidth / 6)):
      # best lines are too close
      foundR = False
      foundL = False
      foundC = False
      for i in (2,1,0):
        if bestrl is not None and rline[i] is not None and self.check(bestrl, rline[i]):
          foundR = True
        if bestll is not None and lline[i] is not None and self.check(bestll, lline[i]):
          foundL = True
        if bestcl is not None and cline[i] is not None and self.check(bestcl, cline[i]):
          foundC = True
      if  (bestrl is not None and bestll is not None and abs(bestrl[0][0] - bestll[0][0]) < laneWidth / 6):
        if (foundR and foundL) or (not foundR and not foundL):
          if midpix > bestll[0][0]:
            bestrl = None
          else:
            bestll = None
        elif foundR and not foundL:
            bestll = None
        elif not foundR and foundL:
            bestrl = None

      if (bestcl is not None and bestll is not None and abs(bestcl[0][0] - bestll[0][0]) < laneWidth / 6):
        if (foundC and foundL) or (not foundC and not foundL):
          if abs(midpix - bestcl[0][0]) < laneWidth / 6:
            bestll = None
          elif (midpix - bestll[0][0]) > laneWidth / 6:
            bestcl = None
          else:
            bestll = None
        elif foundC and not foundL:
            bestll = None
        elif not foundC and foundL:
            bestcl = None

      if (bestcl is not None and bestrl is not None and abs(bestcl[0][0] - bestrl[0][0]) < laneWidth / 6):
        if (foundC and foundR) or (not foundC and not foundR):
          if abs(midpix - bestcl[0][0]) < laneWidth / 6:
            bestrl = None
          elif (bestrl[0][0] - midpix) > laneWidth / 6:
            bestcl = None
          else:
            bestrl = None
        elif foundC and not foundR:
            bestrl = None
        elif not foundC and foundR:
            bestcl = None


    '''
    # following has been replaced by above
    if  bestrl is not None and bestll is not None and bestrl[0][0] == bestll[0][0] and bestrl[0][1] == bestll[0][1] and bestrl[1][0] == bestll[1][0] and bestrl[1][1] == bestll[1][1]:
        if rline[i] is not None and self.check(bestrl, rline[i]):
          bestll = None
          break
        elif lline[i] is not None and self.check(bestll, lline[i]):
          bestrl = None
          break
        elif lline[i] is None and bestll is None and bestrl is not None:
          bestll = None
          break
        elif rline[i] is None and bestrl is None and bestll is not None:
          bestrl = None
          break
        else:
          if rline[i] is not None and bestll is not None:
            rl = rline[i]
            if bestll[0][0] < rl[0][0] and bestll[1][0] < rl[1][0]:
              bestrl = None
              break
          if lline[i] is not None and bestll is not None:
            ll = lline[i]
            if bestrl[0][0] > ll[0][0] and bestrl[1][0] > ll[1][0]:
              bestll = None
              break
    '''

    ########################
    if (((bestrl is None and bestvprl is not None) or
         (bestrl is not None  and np.array_equal(bestrl,bestvprl))) and
        ((bestcl is None and bestvpcl is not None) or
         (bestcl is not None  and np.array_equal(bestcl,bestvpcl))) and
        ((bestll is None and bestvpll is not None) or
         (bestll is not None  and np.array_equal(bestcl,bestvpll)))):
      bestrl = bestvprl
      bestcl = bestvpcl
      bestll = bestvpll
    ########################
    # Done, set globals and return vals
    ########################
    tmppos = self.setCurPos(bestll, bestcl, bestrl, pos[2])
    if tmppos >= 0:
      curpos = tmppos
    del(lline[0])
    lline.append(bestll)
    del(cline[0])
    cline.append(bestcl)
    del(rline[0])
    rline.append(bestrl)
    del(pos[0])
    pos.append(curpos)
    conf = curconf
    # print("lline")
    # print(lline)
    # print(bestll)
    # print("cline")
    # print(cline)
    # print(bestcl)
    # print(cline[2])
    # print("rline")
    # print(cline)
    # print(bestrl)
    # print(rline[2])
   
    conf, self.steering, self.throttle = self.setSteerThrottle(curpos, lline[2], cline[2], rline[2], conf)

    print ("steer %f throt %f conf %d pos(%s)" % (self.steering, self.throttle, conf, self.strpos(pos[2])))
    #######################
    # print to screen
    #######################
    croi = copy.deepcopy(roi)
    if lines is not None:
      lrclines = []
      str1 = "final: "
      if lline[2] is not None:
        lrclines.append(lline[2])
        str1 += "ll "
      if rline[2] is not None:
        lrclines.append(rline[2])
        str1 += "rl "
      if cline[2] is not None:
        lrclines.append(cline[2])
        str1 += "cl "
    # print(str1)
      for line in lrclines:
        if line is not None:
            x1 = line[0][0]
            y1 = line[0][1]
            x2 = line[1][0]
            y2 = line[1][1]
            cv2.line(croi,(x1,y1),(x2,y2),(0,255,0),2)
   
    global seq
    '''
    cv2.imshow(str(seq),croi)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    '''
    if cfg.SAVE_MOVIE:
      out = self.image_path("/tmp/movie4", seq)
      cv2.imwrite(out, croi)
      print("wrote %s" % (out))
    # ffmpeg -framerate 4 -i /tmp/movie4/1%03d_cam-image_array_.jpg -c:v libx264 -profile:v high -crf 20 -pix_fmt yuv420p output.mp4

    TB.checkThrottle(self.throttle)
    return self.steering, self.throttle

  def binary_hsv_mask(self, img, color_range):
    lower = np.array(color_range[0])
    upper = np.array(color_range[1])
    return cv2.inRange(img, lower, upper)

  def process_img_color(self, img):
    if TB.throttleCheckInProgress():
      TB.setMinMaxThrottle(img)
    roi = self.getROI(img)
    roi = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cmask = self.binary_hsv_mask(roi, cfg.COLOR_YELLOW)
    cimg = cv2.bitwise_and(roi, roi, mask = cmask)
    edges = cv2.Canny(roi, 100, 200) 
    hb = HoughBundler()
    lines = cv2.HoughLinesP(edges, 1, np.pi/90, 13, 20, 20, 20)
    # simple line follower
    simplecl = hb.line_follower(lines)
    ymergedlines = hb.process_lines(lines)

    cmask = self.binary_hsv_mask(roi, cfg.COLOR_WHITE)
    cimg = cv2.bitwise_and(roi, roi, mask = cmask)
    edges = cv2.Canny(roi, 100, 200) 
    hb = HoughBundler()
    wmergedlines = hb.process_lines(lines)
    return simplecl, wmergedlines, ymergedlines, roi

  def process_img(self, img):

    if TB.throttleCheckInProgress():
      TB.setMinMaxThrottle(img)
    # hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    '''
    # hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lab= cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    #-----Splitting the LAB image to different channels-------------------------
    l, a, b = cv2.split(lab)
    #-----Applying CLAHE to L-channel-------------------------------------------
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16,16))
    cl = clahe.apply(l)
    limg = cv2.merge((cl,a,b))
    # cv2.imshow('limg', limg)
    #-----Converting image from LAB Color model to RGB model--------------------
    hsv_img = cv2.cvtColor(limg, cv2.COLOR_BGR2HSV)
    # hsv_img = np.stack((limg,)*3, -1)
    '''


    '''
    from pylab import array, plot, show, axis, arange, figure, uint8 

    image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    maxIntensity = 255.0 # depends on dtype of image data
    x = arange(maxIntensity) 
    
    # Parameters for manipulating image data
    phi = 1
    theta = 1
    # Increase intensity such that
    # dark pixels become much brighter, 
    # bright pixels become slightly bright
    newImage0 = (maxIntensity/phi)*(image/(maxIntensity/theta))**0.5
    newImage0 = array(newImage0,dtype=uint8)
    # y = (maxIntensity/phi)*(x/(maxIntensity/theta))**0.5
    
    # Decrease intensity such that
    # dark pixels become much darker, 
    # bright pixels become slightly dark 
    hsv_img = (maxIntensity/phi)*(image/(maxIntensity/theta))**2
    hsv_img = array(hsv_img,dtype=uint8)
    hsv_img = np.stack((hsv_img,)*3, -1)
    '''

    '''
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # img = cv2.cvtColor(img, cv2.CV_8UC1)
    # ret,hsv_img = cv2.threshold(img,140,255,cv2.THRESH_BINARY)
    # (ret, hsv_img) = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # hsv_img = cv2.adaptiveThreshold(img,255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,11,2)
    hsv_img = cv2.adaptiveThreshold(img,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
    hsv_img = np.stack((hsv_img,)*3, -1)
    '''

    '''
    from PIL import Image
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img2 = np.array(gray).astype(np.float)
    THRESH = 140
    img2[img2 <= THRESH] = 0
    img2[img2 > THRESH] = 255
    # hsv_img = Image.fromarray(img2)
    img2 = np.uint8(img2)
    hsv_img = np.stack((img2,)*3, -1)
    '''

    roi = self.getROI(img)
    # roi = self.getROI(hsv_img)
    # edges = cv2.Canny(roi, 100, 200) # [100,200][30, 130][150,255]
    edges = cv2.Canny(roi, 100, 200) 

    # Change from 20->13 added more dotted lines at drive.ai
    # edges, rho, theta, threshold, [outputlines], MinLineLength, maxLineGap
    # lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi/90, threshold=15, minLineLength=20, maxLineGap=30)
    # lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi/90, threshold=15, minLineLength=15, maxLineGap=40)
    lines = cv2.HoughLinesP(edges, 1, np.pi/90, 13, 20, 20, 20)
    # croi = copy.deepcopy(roi)
    # if lines is not None:
    #   for line in lines:
    #     for x1,y1,x2,y2 in line:
    #       cv2.line(croi,(x1,y1),(x2,y2),(0,255,0),2)

    hb = HoughBundler()
    # simple line follower
    simplecl = hb.line_follower(lines)


    '''
    if cl is not None:
      croi = copy.deepcopy(roi)
      cv2.line(croi,(cl[0],cl[1]),(cl[2],cl[3]),(0,255,0),2)
      cv2.imshow('follow line', croi)
      cv2.waitKey(0)
      cv2.destroyAllWindows()
    '''

    mergedlines = hb.process_lines(lines)
    '''
    croi = copy.deepcopy(roi)
    if mergedlines is not None:
      for line in mergedlines:
        x1 = line[0][0]
        y1 = line[0][1]
        x2 = line[1][0]
        y2 = line[1][1]
        cv2.line(croi,(x1,y1),(x2,y2),(0,255,0),2)
    cv2.imshow('lines', croi)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    '''
    return simplecl, mergedlines, roi

  def get_map_data(self):
        global pixPerFrame, laneWidth, donkeyvpangle, dklinept, bestll, bestcl, bestrl, width, curpos
        return laneWidth, pixPerFrame, donkeyvpangle, bestll, bestcl, bestrl, width, curpos


  def image_path(self, tub_path, frame_id):
        return os.path.join(tub_path, str(frame_id) + "_cam-image_array_.jpg")

  def test_tub(self, tub_path):
        global width, height, pixPerFrame, laneWidth, donkeyvpangle
        global seq

        seqs = [ int(f.split("_")[0]) for f in os.listdir(tub_path) if f.endswith('.jpg') ]
        seqs.sort()
        entries = ((os.stat(self.image_path(tub_path, seq))[ST_ATIME], seq) for seq in seqs)

        (last_ts, seq) = next(entries)
        clips = [[seq]]
        for next_ts, next_seq in entries:
            if next_ts - last_ts > 100:  #greater than 1s apart
                clips.append([next_seq])
            else:
                clips[-1].append(next_seq)
            last_ts = next_ts

        # import donkey.parts.map
        # map = Map()

        # inputs = ['user/angle', 'user/throttle', 'cam/image']
        inputs = ['pilot/angle', 'pilot/throttle', 'cam/image']
        types = ['float', 'float', 'image']
        self.tub = Tub(path=tub_path, inputs=inputs, types=types)
        for clip in clips:
          for imgseq in clip:
            # if imgseq < 200:
              # continue
            # global seq
            # if seq < 19:
            #   seq += 1
            #   continue
            imgname = self.image_path(tub_path, imgseq)
            img = cv2.imread(imgname)
            if img is None:
              continue
            seq = imgseq

            # rec = self.tub.get_record(imgseq)
            # Did we record he wrong thing? should be pilot?
            # print("tub speed %f  throttle %f" % (float(rec["user/angle"]),float(rec["user/throttle"])))

            simplecl, lines, roi = self.process_img(img)
            # roi = self.getROI(img)
            if lines is not None:
              steering, throttle = self.lrclines(lines,roi)
            if simplecl is not None:
              pos = 4
              conf = cfg.MAX_ACCEL
              conf, steering, throttle = self.setSteerThrottle(pos, None, simplecl, None, conf)

            # map.update(steering, throttle, lines, dklinept, laneWidth, pixPerFrame)
            
            # return steering, position

  def __init__(self, tb):
    global lline, rline, cline, pos, throttle, steering, conf
    global width, height, pixPerFrame, PPFx, PPFy, laneWidth 
    global dklinept, VPx, VPy, donkeyvpangle
    global bestrl, bestll, bestcl, bestvx, bestvy, curconf, curpos
    global TB, seq, cfg

    TB = tb
    donkeyvpangle = None
    bestrl = None 
    bestll = None
    bestcl = None
    bestvx = 1000
    bestvy = 1000
    curconf = -1
    curpos = -1000
    cfg = dk.load_config(config_path=os.path.expanduser('~/donkeycar/donkeycar/parts/RLConfig.py'))
    
    # each array is global state cache of 3
    lline = [None,None,None]
    rline = [None,None,None]
    cline = [None,None,None]
    throttle = [0,0,0]
    steering = [0,0,0]
    pos = [3,3,3]
    conf = cfg.MAX_ACCEL / 3
    seq = 0
    width = -1
    height = -1
    dklinept = None
    pixPerFrame = -1
    laneWidth = -1
    VPx = None
    VPy = None
    PPFx = None
    PPFy = None
    
    # each array is global state cache of 3
    # self.test_tub("/home/ros/d2/data/tub_153_18-07-29")
