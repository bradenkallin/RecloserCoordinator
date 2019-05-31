"""
CAPE Recloser Setting Coordination Aide v0.2
    by Braden Kallin
    
This program aids in selecting recloser settings based on fusing and 
    breaker coordination. 
    
v0.1: 
    -initial
v0.2: 
    -now does logarithmic interpolation instead of linear
    -option to write solutions to a file
    -minimal devlogging
    
-NOTE: Curves which coordinate according to curve data may appear not to 
        coordinate in CAPE. Reason being that CAPE always plots the first TCC 
        point at the specified pickup current, while the current in the first 
        data point in the curve may actually be slightly greater than 1.

"""

import sys
import traceback
import os
import glob
import re
import copy
import math

startDir = os.getcwd()

#possible folder paths for curves are below.
#when adding folder paths, make sure to modify getCurveLists() accordingly
#processCurveFile() may also need editing, depending on the file format
fusePath = os.path.join(startDir, 'fuseCurves\\')
recloserPath = os.path.join(startDir, 'recloserCurves\\')
breakerPath = os.path.join(startDir, 'breakerCurves\\')

#set writeLog to True when debugging 
devLog = []
writeLog = True

def main():    
    #print introduction
    printIntro()
    
    #get a list of curve files
    #curveFileLists is a tuple of lists of curve filenames
    curveFileLists = getCurveLists()
    
    #print the lists of curve filenames
    printCurveList(curveFileLists)
    
    #ask the user which curves to coordinate with. pull in those files
    downstreamCurveFile, upstreamCurveFile = getUserCurves(curveFileLists)
    
    #ask user for amperage extents of recloser pickup current
    pickupMin, pickupMax, coordMaxAmps = getUserExtents()
    
    #ask user for minimum coordination time
    minCoordTime = getUserTime()
    
    #process relevant curve files to make them usable by the program
    downstreamCurve = processCurveFile(downstreamCurveFile, "d")
    upstreamCurve = processCurveFile(upstreamCurveFile, "u")
    recloserCurveFiles = readAllReclosers()
    recloserCurves = []
    for curveFile in recloserCurveFiles:
        recloserCurves.append(processCurveFile(curveFile, "r"))   
    
    #do the actual coordination
    coordCurves = downstreamCurve, upstreamCurve, recloserCurves
    coordAmps = pickupMin, pickupMax, coordMaxAmps
    solutionSet = getSolutions(coordCurves, coordAmps, minCoordTime)
    
    printSolutions(solutionSet, curveFileLists[2])
    
    #print out the dev log
    if writeLog: printDevLog()
    
#get lists of curves to eventually present to the user
#when adding types, make sure to modify the folder path variables accordingly
#processCurveFile() may also need editing, depending on the file format
def getCurveLists():
    breakerList = []
    fuseList = []
    recloserList = []
    
    #find all filenames in each path and add them to a list
    os.chdir(fusePath)
    for curveFile in glob.glob("*"):
        fuseList.append(curveFile)
    
    os.chdir(recloserPath)
    for curveFile in glob.glob("*"):
        recloserList.append(curveFile)
        
    os.chdir(breakerPath)
    for curveFile in glob.glob("*"):
        breakerList.append(curveFile)
        
    os.chdir(startDir)
        
    return (breakerList,fuseList,recloserList)

#print an introduction to the program    
def printIntro():
    print("\n==This program is intended to aid in choosing recloser settings to" +
            "\n  coordinate with fuses and breakers.\n")
            
    print("==Fuse naming convention: Type_AmpacitySpeed_Curve, e.g.:")
    print("  POSI_65K_MM -> S&C Positrol, 65A, K-Speed, Minimum Melting")
    print("  SMU20_50E_TC -> S&C SMU-20, 50A, Standard (E) Speed, Total Clear\n")
    print("==Typically, you'll use Total Clear if you want your fuse to go first," +
            "\n  or Minimum Melting if you want the fuse to go last.\n")
            
    print("==\'Kyle\' recloser curves are the curves used by Cooper Form 4 and later\n")
    
    input("Press enter to show the available breaker, fuse and recloser curves.\n")
    
#print a list of available curves
def printCurveList(curveFileLists):
    breakerList, fuseList, recloserList = curveFileLists
    
    print("==========================")
    print("Available Breaker Curves:")
    print("==========================")
    #print curve names next to curve numbers in 3 columns
    for i, curve in enumerate(breakerList):
        if i%3 != 2:
            print("[b{0:02}] {1:20}".format(i, curve), end=' ')
        else:
            print("[b{0:02}] {1:20}".format(i, curve))
        
    print("\n==========================")
    print("Available Fuse Curves:")
    print("==========================")
    for i, curve in enumerate(fuseList):
        if i%3 != 2:
            print("[f{0:02}] {1:20}".format(i, curve), end=' ')
        else:
            print("[f{0:02}] {1:20}".format(i, curve))
        
    print("\n==========================")
    print("Available Recloser Curves:")
    print("==========================")
    for i, curve in enumerate(recloserList):
        if i%3 != 2:
            print("[r{0:02}] {1:20}".format(i, curve), end=' ')
        else:
            print("[r{0:02}] {1:20}".format(i, curve))
    print("\n\n")
        
#get upstream and downstream curve selections from the user
def getUserCurves(curveFileLists):    
    #get input from the user in the form xnn for curve type (b/f/r) and number
    inputOK = False
    while inputOK == False:
        downstreamSel = input("Enter selection for downstream curve." +
                                " Typically the largest fuse downstream \n" +
                                "  or next downstream recloser \n>>")
        
        #check the input against a regex and availability
        inputOK = checkCurveSel(downstreamSel, curveFileLists)
        
        if inputOK == False:
            print("\n!! Please enter a valid curve name, such as f14 or r02\n")
        else:
            print("")
    
    inputOK = False
    while inputOK == False:
        upstreamSel = input("Enter selection for upstream curve. Typically" +
                                " the substation breaker \n" +
                                "  or next upstream recloser \n>>")
        
        inputOK = checkCurveSel(upstreamSel, curveFileLists)
        
        if inputOK == False:
            print("\n!! Please enter a valid curve name, such as f14 or r02\n")
    
    print("")
    
    #read the selected curves
    downstreamFile = readCurveFile(downstreamSel, curveFileLists)
    upstreamFile = readCurveFile(upstreamSel, curveFileLists)        
                            
    return (downstreamFile, upstreamFile)
    
#read a raw curve file. append curve type at beginning of the data
def readCurveFile(userSel, curveFileLists):
    #pull in the list of available files to read from
    breakerList, fuseList, recloserList = curveFileLists
    chosenList = []
    listIndex = int(userSel[1:])
    
    curveFile = []

    #switch to the chosen directory and start the data with an indicator
    if userSel[0] == 'b':
        os.chdir(breakerPath)
        chosenList = breakerList
        curveFile.append('breaker')
    elif userSel[0] == 'f':
        os.chdir(fusePath)
        chosenList = fuseList
        curveFile.append('fuse')
    elif userSel[0] == 'r':
        os.chdir(recloserPath)
        chosenList = recloserList
        curveFile.append('recloser')
        
    #read the chosen file
    for currentLine in open(chosenList[listIndex]):
            curveFile.append(currentLine)
            
    return curveFile

#check user input for curve selection
def checkCurveSel(userIn, curveFileLists):
    breakerList, fuseList, recloserList = curveFileLists
    #create regexes to match available curve selections
    brkPattern = re.compile(r"^[b]\d{2}$")
    fusPattern = re.compile(r"^[f]\d{2}$")
    recPattern = re.compile(r"^[r]\d{2}$")
    
    bm = brkPattern.match(userIn)
    fm = fusPattern.match(userIn)
    rm = recPattern.match(userIn)
    
    inputOK = False
    
    #check if the selected curve is on the list of available curves
    if bm:
        i = int(userIn[1:])
        if (i < len(breakerList)) and (i>=0):
            inputOK = True
    elif fm:
        i = int(userIn[1:])
        if (i < len(fuseList)) and (i>=0):
            inputOK = True
    elif rm:
        i = int(userIn[1:])
        if (i < len(recloserList)) and (i>=0):
            inputOK = True
        
    return inputOK
    
#get extents of recloser pickup current and max coordination amperage
def getUserExtents():
    pickupMin = 0
    pickupMax = 0
    coordMaxAmps = 0
    
    #accepts user input only if it's an integer, then converts it to an integer
    inputOK = False
    while inputOK == False:
        pickupMinIn = input("Enter minimum pickup current for new recloser in Amps\n" +
        "Note: This script only accepts whole numbers\n>>")
        
        inputOK = pickupMinIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid amperage\n")
        else:
            pickupMin = int(pickupMinIn)
            print("")
    
    #same as before, but checks that max pickup is greater than min pickup
    inputOK = False
    while inputOK == False:
        pickupMaxIn = input("Enter maximum pickup current for new recloser in Amps\n>>")
        
        if pickupMaxIn.isdecimal():
            pickupMax = int(pickupMaxIn)
            if pickupMax > pickupMin:
                inputOK = True
        
        if inputOK == False:
            print("\n!! Please enter a valid amperage " +
                    "greater than {0}A\n".format(pickupMin))
        else:
            print("")
            
    #same as before, but checks that max coord current is greater than max pickup
    inputOK = False
    while inputOK == False:
        coordMaxIn = input("Enter maximum coordination current in Amps\n" +
                            "Typically max SC current or feeder IOC current\n>>")
        
        if coordMaxIn.isdecimal():
            coordMaxAmps = int(coordMaxIn)
            if coordMaxAmps > pickupMax:
                inputOK = True
        
        if inputOK == False:
            print("\n!! Please enter a valid amperage " +
                    "greater than {0}A\n".format(pickupMax))
        else:
            print("")
    
    print("")
    
    return pickupMin, pickupMax, coordMaxAmps
    
#get pickup/time constant for downstream/upstream recloser
def getRecInfo(curveOrder):
    pickupCurrent = 0
    timeConstant = 0
    
    if (curveOrder == 'd'):
        orderString = "downstream"
    else:
        orderString = "upstream"
    
    #accepts user input only if it's an integer, then converts it to an integer
    inputOK = False
    while inputOK == False:
        pickupCurrIn = input("Enter pickup current for "+
                            "{0} recloser in Amps\n>>".format(orderString))
        
        inputOK = pickupCurrIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid amperage\n")
        else:
            pickupCurrent = int(pickupCurrIn)
            print("")
    
    inputOK = False
    while inputOK == False:
        timeConstIn = input("Enter time constant for "+
                            "{0} recloser in cycles\n>>".format(orderString))
        
        inputOK = timeConstIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid number of cycles\n")
        else:
            pickupCurrent = int(pickupCurrIn)
            print("")
    
    return pickupCurrent, timeConstant
    
#get minimum coordination time
def getUserTime():
    minCoordTime = 0
    
    #accepts user input only if an integer, then converts input to an integer
    inputOK = False
    while inputOK == False:
        coordTimeIn = input("Enter minimum coordination time in cycles " +
        "(typ. 20 cycles)\n"
        "Note: This script only accepts whole numbers\n>>")
        
        inputOK = coordTimeIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid coordination time\n")
        else:
            minCoordTime = int(coordTimeIn)
            print("")
    
    return minCoordTime

#read all the recloser files
def readAllReclosers():
    recloserCurveFiles = []
    
    os.chdir(recloserPath)
    for file in glob.glob("*"):
        currentCurve = ['recloser']
        for line in open(file):
            currentCurve.append(line)
        recloserCurveFiles.append(currentCurve)
    
    os.chdir(startDir)
    
    return recloserCurveFiles
    
#make curve files into usable, uniform data
def processCurveFile(curveFile, curveOrder):
    curveData = []
    pickupAmps = 1
    ctRatio = 1
    dataInSeconds = False #Otherwise it's in seconds 
    
    #determine format of time data
    for line in curveFile:
        if 'cycle' in line.lower():
            dataInSeconds = False
            break
        elif 'second' in line.lower():
            dataInSeconds = True
            break
    
    #breaker curves have a special format because CAPE is weird :-|
    if (curveFile[0] == 'breaker'):
        for line in curveFile:
            #breaker data points are numbered
            if line.split()[0].isdecimal():
                currentData = line.split()[1:]
                for i, val in enumerate(currentData):
                    currentData[i] = float(currentData[i])
                curveData.append(currentData)
        #CT ratios are often wrong.
        if (curveData[0][0] < 100):
            oldRatio, newRatio = getNewCTRatio(curveData[0][0])
            #correct data with new CT ratio
            for i in range(len(curveData)):
                curveData[i][0] = curveData[i][0] / oldRatio
                curveData[i][0] = curveData[i][0] * newRatio
                
    else:
        for line in curveFile:
            #data lines readable by CAPE start with whitespace
            if (len(line) != len(line.lstrip())):
                #store data as a 2-d array in format [current][time]
                currentData = line.split()
                for i, val in enumerate(currentData):
                    currentData[i] = float(currentData[i])
                curveData.append(currentData)
    
    #convert time data to cycles if it's in seconds
    if dataInSeconds:         
        for currentData in curveData:
            currentData[1] *= 60
        
    #handle upstream or downstream reclosers
    if (curveFile[0] == 'recloser'):
        if (curveOrder == 'u') or (curveOrder == 'd'):
            pickupCurrent, timeConstant = getRecInfo(curveOrder)
            for currentData in curveData:
                currentData[0] *= pickupCurrent
                currentData[1] += timeConstant
                
    #comment out to disable curve data in dev log
    
    global devLog
    if writeLog: 
        devLog.append("==BEGIN CURVE DATA")
        devLog.append(curveOrder)
        for datum in curveData:
            devLog.append(','.join(map(str,datum)))
        devLog.append("==END CURVE DATA\n")
    
    return curveData

#things start to get mildly interesting here:
def getSolutions(coordCurves, coordAmps, minCoordTime):
    downstreamCurve, upstreamCurve, recloserCurves = coordCurves
    pickupMin, pickupMax, coordMaxAmps = coordAmps
    ampStep = 5
    coordination = True
    
    global devLog
    
    solutionSet = []
    
    #test every available recloser curve
    for n, recloserCurve in enumerate(recloserCurves): 
        if writeLog: devLog.append("[r{0:02}]".format(n))
        #test at every pickup current
        for pickupCurrent in range(pickupMin, pickupMax+1, ampStep):
            if writeLog: devLog.append("PU = {0}".format(pickupCurrent))
        
            testCurve = copy.deepcopy(recloserCurve) 
            for m in range(len(testCurve)):
                testCurve[m][0] *= pickupCurrent
            #test recloser against downstream and vice versa
            if writeLog: devLog.append("dvr")
            coordination = testCoord(downstreamCurve, testCurve,
                                     minCoordTime, 'd',
                                     coordMaxAmps)
            if writeLog: devLog.append("rvd")
            coordination = coordination and testCoord(testCurve, downstreamCurve,
                                                      minCoordTime, 'u',
                                                      coordMaxAmps)
            #test recloser against upstream and vice versa
            if writeLog: devLog.append("uvr")
            coordination = coordination and testCoord(upstreamCurve, testCurve,
                                                      minCoordTime, 'u',
                                                      coordMaxAmps)
            if writeLog: devLog.append("rvu")
            coordination = coordination and testCoord(testCurve, upstreamCurve,
                                                      minCoordTime, 'd',
                                                      coordMaxAmps)                                         
            if coordination:
                solutionSet.append([n,pickupCurrent])
            #print(testCurve)
            #print(downstreamCurve)
            #print(upstreamCurve)
            if writeLog: devLog.append('--')
        if writeLog: devLog.append('\n')
                
    return solutionSet
    
#test coordination time between two curves
def testCoord(curve1, curve2, minCoordTime, direction, maxAmps):
    #test every point in the recloser curve against a test curve
    #a data point in a curve is [amperage, time]
    #curves are always sorted low to high on amperage
    for point in curve1:
        #check if point overlaps with curve2 at this current
        if ((point[0] >= curve2[0][0]) and 
            (point[0] <= curve2[-1][0]) and 
            (point[0] <= maxAmps)):
            #perform a linear interpolation to get time difference at specific current
            coordTime = point[1] - interpolateTime(curve2, point[0])
            if direction == 'd': coordTime = -coordTime
            if writeLog: devLog.append("coord time: {0}".format(coordTime))
            if coordTime < minCoordTime: return False
    
    return True

#helper function for linear interpolation
def interpolateTime(interCurve, interCurrent):
    interPoint0 = [] #nearest point with current < interCurrent
    interPoint1 = [] #nearest point with current > interCurrent
    
    global devLog
    
    for point in interCurve:
        if point[0] == interCurrent: return point[1]
        if point[0] < interCurrent: interPoint0 = point
        else:
            interPoint1 = point
            break
    
    """#linear interpolation. we want to do logarithmic interpolation instead
    interTime = (interPoint0[1] + (interCurrent - interPoint0[0]) * 
                (interPoint1[1] - interPoint0[1]) / 
                (interPoint1[0] - interPoint0[0]))
    """
    
    #logarithmic interpolation
    m = (math.log10(interPoint1[1]/interPoint0[1]) /
        math.log10(interPoint1[0]/interPoint0[0]))
            
    b = interPoint0[1] / math.pow(interPoint0[0],m)
    interTime = b * math.pow(interCurrent,m)
    
    if writeLog: 
        devLog.append(', '.join(map(str,interPoint0)))
        devLog.append(', '.join(map(str,interPoint1)))
        devLog.append("inter. curr: {0}".format(interCurrent))
        devLog.append("inter. time: {0}".format(interTime))
    
    return interTime
    
def getNewCTRatio(pickupCurrent):
    oldRatio = 0
    newRatio = 0
    
    #accepts user input only if an integer, then converts input to an integer
    inputOK = False
    while inputOK == False:
        oldRatioIn = input("!! Breaker pickup current is unusually low\n" +
                            "CT ratio setting in CAPE is likely wrong\n"
                            "Please enter current CT setting from CAPE (usually 1)\n>>")
        
        inputOK = oldRatioIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid CT ratio setting\n")
        else:
            oldRatio = int(oldRatioIn)
            print("")
            
    inputOK = False
    while inputOK == False:
        newRatioIn = input("Please enter new CT ratio (usually 160)\n>>")
        
        inputOK = newRatioIn.isdecimal()
        
        if inputOK == False:
            print("\n!! Please enter a valid CT ratio setting\n")
        else:
            newRatio = int(newRatioIn)
            print("")
    
    return oldRatio, newRatio
  
def printSolutions(solutionSet, recloserList):
    lastPrintedNumber = -1
    rangeMin = 0
    rangeMax = 0
    
    solutionOut = []
    
    solutionOut.append("========================")
    solutionOut.append("Possible Curve Settings:")
    solutionOut.append("========================\n")
    
    if not solutionSet:
        solutionOut.append("[no solutions found]")
    
    for i, solution in enumerate(solutionSet):
        if(lastPrintedNumber != solution[0]):
            lastPrintedNumber = solution[0]
            if(i != 0):
                solutionOut.append("Pickup Max (A): {0}\n".format(rangeMax))
            solutionOut.append("Curve: {0}".format(recloserList[solution[0]]))
            solutionOut.append("Pickup Min (A): {0}".format(solution[1]))
            
        if(i == (len(solutionSet) - 1)):
            solutionOut.append("Pickup Max (A): {0}\n".format(solution[1]))
        
        rangeMax = solution[1]
        
    for line in solutionOut:
        print(line)
        
    writeSol = input("\nWrite solutions to file? [y/n]\n")
    
    if (writeSol.lower() == 'y'):
        with open('solutions.txt', 'w') as f:
            for line in solutionOut:
                f.write(line)
                f.write('\n')
        
def printDevLog():
    with open('logFile', 'w') as f:
        for entry in devLog:
            f.write(entry)
            f.write('\n')
  
if __name__ == '__main__':
    try:
        main()
    except OSError as e:
        if(e.filename):
            print("Could not access %s" % e.filename)
    except:
        print("An error occurred. Here's what the program has to say about it:")
        traceback.print_tb(sys.exc_info()[2])
        print("")
    finally:
        input("\n\nPress enter to close...\n")