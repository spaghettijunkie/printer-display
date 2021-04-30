import argparse

parser = argparse.ArgumentParser(description="This program parses g-code files so they can be displayed")
parser.parse_args()



import requests
import time
import math
import os
import pygame
import datetime
from pygame.locals import *

DEBUG_MODE = True
GRAPHICS = True
LOCAL_GCODE_DIRECTORY = "gCodeFiles/"

class gCode:
    def __init__(self, filePosition, parameters=None):
        self.filePosition = filePosition
        if parameters is None:
            self.parameters = dict()
        else:
            self.parameters = parameters

    def __repr__(self):
        return "At file position" + str(self.filePosition) + "parameters = " + str(self.parameters)

    def getFilePosition(self):
        return self.filePosition

    def hasParameter(self, key):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        if key in self.parameters:
            return True
        return False
    
    def addParameter(self, key, value):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        self.parameters[key] = value

    def getParameter(self, key):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        return self.parameters[key]

    #def newDict(self, newDict=dict()):
        #self.parameters = newDict

    def getDict(self):
        return self.parameters
            

def get(url:"url to get data from", verifyCertificate=True) -> "response as a requests.get object": # get response from api
    apiToken = "3962233D8F744F6FA469C86B00EEC938"
    print("Getting from url:", url)
    resp = requests.get(url, headers={"Content-Type" : "application/josn", "x-Api-Key" : apiToken}, verify=verifyCertificate)

    if resp.status_code != 200:
        # This means something went wrong.
        raise Exception('GET {} {}'.format(resp.url, resp.status_code))
    #time.sleep(1)
    
    return resp


def fileExistsInDir(fileName, directory="") -> (bool, "If the file exists in the directory, return true"):
    if fileName in os.listdir(directory):
        return True
    return False

def gCodeParser(gCodeFile:"File name to read from", commandsToInclude:"Commands to include as movement commands" = ("G0 ", "G1 ")):
    gCodeList = []
    time.sleep
    print("Reading File")
    abs
    with open(gCodeFile, "rb") as inFile:
        lenFile = len(inFile.readlines())
        inFile.seek(0)
        for index in range(lenFile):
            if index % pow(10, math.floor(math.log(lenFile, 10))-1) == 0:
                print("line:", index, ":", "{:.2f}".format(100*index/lenFile) + "%")
            elif index == lenFile - 1:
                print("line:", index, ":", "100.00%")

            gCodeList.append(gCode(inFile.tell()))
            line = inFile.readline().strip().split(b";")

            if len(line) == 2: # There is a comment
                gCodeList[-1].addParameter(b"command", b"comment")
                gCodeList[-1].addParameter(b";", line[1])
                
                
            line = line[0].strip()
            if len(line) > 0: # The line before a comment has stuff in it
                gCodeList[-1].addParameter(b"command", line.split(b" ")[0])

                for i in line.split(b" ")[1:]:
                    gCodeList[-1].addParameter(i[0:1], i[1:])
            #gCodeList[-1].newDict(param)
    return gCodeList


# Write the chosen parameters of the gcode file out to a csv file
def writeCodeList(codeList, params:"list of parameters to be written together", notFoundChr:"bytes object to put in place of missing data, default will use the value from the previous line"="") -> None:
    last = ["0"]*len(params)
    print("Writing \"out.csv\"")
    with open("out.csv", "wb") as outfile:
        outfile.write(b",".join(params) + b"\n")
        for code in codeList:
            numParams = 0
            output = ""
            for i, param in enumerate(params):
                if code.hasParameter(param):
                    if not code.getParameter(param).startswith((b"+", b"-")):
                        numParams += 1
                        output += code.getParameter(param).decode("utf-8")
                        last[i] = code.getParameter(param).decode("utf-8")
                elif notFoundChr == "":
                    output += last[i]
                else:
                    output += notFoundChr
                output += ","
            if numParams > 0:
                output = output[:-1] + "\n" #Replace last comma with newline
                outfile.write(bytes(output, "utf-8"))
            

def getParsedGCode(localFile : "Local file to read gcode from"="" , writeCSV : "Name of CSV with points \"\" to not write a file"="", forceDownload : "Force downloading of the file currently used. localFile will override this"=False) -> None:
    if localFile != "": # Force a local file to be used
        parsedCode = gCodeParser(localFile) 

    else:
        print("GETTING UPDATED INFO FROM PRINTER")
        
        respJson = get("http://octopi.local/api/job").json() # Get job status
        
        # Download the file if we don't already have it
        if not fileExistsInDir(respJson["job"]["file"]["name"], LOCAL_GCODE_DIRECTORY) or forceDownload:
            print("File does not exist locally")
            time.sleep(1) # Make sure we don't send to many requests at once
            # Get download link
            fileDownload = get("http://octopi.local/api/files/" + respJson["job"]["file"]["origin"] + "/" + respJson["job"]["file"]["name"]).json()["refs"]["download"]
            print("Remote file located at:", fileDownload, "Downloading file now...")
            # TODO add check that a file is loaded

            time.sleep(1) # Make sure we don't send to many requests at once
            downloadedText = get(fileDownload).content # Get GCode
            
            print("Succesfully downloaded file\n")
            
            with open(LOCAL_GCODE_DIRECTORY + respJson["job"]["file"]["name"], "wb") as outfile:
                outfile.write(downloadedText)
            print("Saved file to:", LOCAL_GCODE_DIRECTORY + respJson["job"]["file"]["name"])
        
        parsedCode = gCodeParser(LOCAL_GCODE_DIRECTORY + respJson["job"]["file"]["name"])
        if writeCSV != "": # CSV file writing. "" to not make one
            print("Writing CSV")
            writeCodeList(parsedCode, [b"X", b"Y", b"Z"])
            print("Done writing CSV")

    return parsedCode


def getLayersByComments(parsedGCode) -> "list of lists of GCode lines. Each index in the list represents a layer":
    layerLineNumbers = []
    layers = []
    for lineNum, line in enumerate(parsedGCode):
        if line.hasParameter(b"command"):
            if line.getParameter(b"command") == b"comment":
                if line.getParameter(b";").startswith(b"LAYER:"):
                    layerLineNumbers.append(lineNum)
        else:
            print("NO COMMAND AT LINE", lineNum)
    lastLine = layerLineNumbers[0]
    for lineNum in layerLineNumbers[1:]:
        layers.append(parsedGCode[lastLine:lineNum])
        lastLine = lineNum
    return layers
                


def getLayersByZ(parsedGCode):
    lastZ = -1
    layers = []
    for lineNum, line in enumerate(parsedGCode):
        if line.hasParameter(b"Z"):
            newZ = line.getParameter(b"Z")
            if newZ != lastZ:
                layers.append(lineNum)
    lastZ = float(parsedGCode[layers[0]].getParameter(b"Z"))
    index = 0
    while index < len(layers):
        if not parsedGCode[layers[index]].getParameter(b"Z").startswith((b"+", b"-")):
            if float(parsedGCode[layers[index]].getParameter(b"Z")) < lastZ:
                lastZ = float(parsedGCode[layers[index]].getParameter(b"Z"))
                index -= 1
                print(parsedGCode[layers[index]].getParameter(b"Z"), lastZ)
                input()
                while float(parsedGCode[layers[index]].getParameter(b"Z")) > lastZ:
                    layers.pop(index)
                    index -= 1
        index += 1


        # RETURNS LAYER LINE NUMBERS!!!!!!!!!!!!!!!!!!!
    return layers

def getPointsAsGCode(layers, transform=[1,1,0,0]):
    points = []
    for layerNum, layer in enumerate(layers):
        points.append([])
        for command in layer:
            if command.getParameter(b"command") == b"G0" or command.getParameter(b"command") == b"G1":
                if command.hasParameter(b"X") and command.hasParameter(b"Y"):
                    points[layerNum].append([command, [float(command.getParameter(b"X").decode("utf-8"))*transform[0]+transform[2], float(command.getParameter(b"Y").decode("utf-8"))*transform[1]+transform[3]]])
    return points

def getPoints(layers, transform=[1,1,0,0]):
    points = []
    for layerNum, layer in enumerate(layers):
        points.append([])
        for command in layer:
            if command.getParameter(b"command") == b"G0" or command.getParameter(b"command") == b"G1":
                if command.hasParameter(b"X") and command.hasParameter(b"Y"):
                    points[layerNum].append([float(command.getParameter(b"X").decode("utf-8"))*transform[0]+transform[2], float(command.getParameter(b"Y").decode("utf-8"))*transform[1]+transform[3]])
    return points



def main():
    global GRAPHICS
    if GRAPHICS:
        screen = pygame.display.set_mode([1600,900], RESIZABLE)
        clock = pygame.time.Clock()
        pygame.font.init()
        myfont = pygame.font.SysFont('Times New Roman', 50)
        
        points = None
        pointsAsGCode = None

        layer = 0
        layers = None
        frame = 0
        filePos = 0
        fileName = None
        currentPointNumber = 0
        while GRAPHICS:
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.display.quit()
                    GRAPHICS = False
                    break
                elif event.type == VIDEORESIZE:
                    screen = pygame.display.set_mode([event.w, event.h], RESIZABLE)
            if frame % 10 == 0:
                remoteFile = get("http://octopi.local/api/job").json()
                if remoteFile["job"]["file"]["name"] != fileName:
                    print("New Job Detected")
                    time.sleep(1)
                    fileName = remoteFile["job"]["file"]["name"]
                    #Get new GCode and parse it
                    layers = getLayersByComments(getParsedGCode())

                    #Get points from the GCode
                    pointsAsGCode = getPointsAsGCode(layers, [min(screen.get_size())/210, -min(screen.get_size())/210, 0, min(screen.get_size())])
                    points = getPoints(layers, [min(screen.get_size())/210, -min(screen.get_size())/210, 0, min(screen.get_size())])

                    print("New File:", fileName, "\nNumber of layers:", len(points))
                if remoteFile["progress"]["filepos"] is not None:
                    filePos = remoteFile["progress"]["filepos"]
                else:
                    filePos = float("inf")
                #filePos = 100000 # TESTLINE --------------------------------------------------------------------------------------------------------------------
            if remoteFile["state"] != "Printing":
                layer = (layer+1)%len(pointsAsGCode) # When the file is done, this line will cycle through every layer
            elif frame % 1 == 0:
                done = False
                for layerNumber, layer2 in enumerate(pointsAsGCode):
                    for pointNumber, pt in enumerate(layer2):
                        if pt[0].getFilePosition() > filePos:
                            currentPointNumber = pointNumber
                            layer = layerNumber
                            pygame.draw.circle(screen, (0,0,255), [int(point) for point in pt[1]], 5)
                            done = True
                            break
                    if done: 
                        break
            
            screen.fill((255,255,255))
            pygame.draw.line(screen, (0,0,127), [0, 0], [min(screen.get_size())]*2)
            pygame.draw.line(screen, (0,0,127), [min(screen.get_size()), 0], [0, min(screen.get_size())])
            pygame.draw.line(screen, (0,0,127), [0, 0], [0, min(screen.get_size())])
            pygame.draw.line(screen, (0,0,127), [0, 0], [min(screen.get_size()), 0])
            pygame.draw.line(screen, (0,0,127), [min(screen.get_size()), 0], [min(screen.get_size())]*2)
            pygame.draw.line(screen, (0,0,127), [0, min(screen.get_size())], [min(screen.get_size())]*2)
            #Draw all points as lines
            for pointNum in range(len(points[layer])-1):
                #print(points[0][pointNum])
                color = (200,200,200)
                size = 1
                if pointNum < currentPointNumber:
                    color = (0,0,0)
                    size = 2
                pygame.draw.line(screen, color, points[layer][pointNum], points[layer][pointNum+1], size)
            #Draw start/end
            pygame.draw.circle(screen, (0,255,0), [int(point) for point in points[layer][0]], 5)
            pygame.draw.circle(screen, (255,0,0), [int(point) for point in points[layer][-1]], 5)
            #Draw layer#
            
            textString = ["Layer: {}/{}".format(str(layer+1), str(len(points)))]
            if "remoteFile" in vars():
                if remoteFile["progress"]["completion"] is not None: 
                    textString.append("Progress: {:.2f}%".format(remoteFile["progress"]["completion"]))
                else:
                    textString.append("Progress: 0.00%")
                if remoteFile["state"] == "Printing":
                    pygame.draw.rect(screen, (0,200,0), [int(min(screen.get_size())), 0, (screen.get_width() - min(screen.get_size()))*layer/len(points), myfont.get_height()])
                else:
                    pygame.draw.rect(screen, (50,50,255), [int(min(screen.get_size())), 0, (screen.get_width() - min(screen.get_size()))*layer/len(points), myfont.get_height()])

                textString.append(fileName)
                if remoteFile["state"] == "Printing":
                    textString.append("File position: {:.2f}".format(remoteFile["progress"]["filepos"]))
                    textString.append("Print time: " + str(datetime.timedelta(seconds=remoteFile["progress"]["printTime"])) + "/" + str(datetime.timedelta(seconds=int(remoteFile["job"]["estimatedPrintTime"]))))
                    textString.append("Print time left: " + str(datetime.timedelta(seconds=remoteFile["progress"]["printTimeLeft"])))
                else:
                    textString.append("Print time: " + str(datetime.timedelta(seconds=int(remoteFile["job"]["estimatedPrintTime"]))))

            for i, line in enumerate(textString):
                screen.blit(myfont.render(str(line), False, (0, 0, 0)), (min(screen.get_size()), myfont.get_height()*i))
            pygame.display.flip()
            clock.tick(5)
            frame += 1
    else:
        print(getPoints(getLayersByComments(getParsedGCode(writeCSV=True, forceDownload=True))))

def test(x: int) -> int:
    return x

if __name__ == "__main__":
    print(test)
    main()



