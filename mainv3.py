import argparse

parser = argparse.ArgumentParser(description="This program parses g-code files so they can be displayed")
parser.parse_args()



import requests
import time
import math
import os
import pygame

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
            

def get(url, verifyCertificate=True): # get response from api
    apiToken = "3962233D8F744F6FA469C86B00EEC938"
    print("Getting from url:", url)
    resp = requests.get(url, headers={"Content-Type" : "application/josn", "x-Api-Key" : apiToken}, verify=verifyCertificate)

    if resp.status_code != 200:
        # This means something went wrong.
        raise Exception('GET {} {}'.format(resp.url, resp.status_code))
    
    
    return resp


def fileExistsInDir(fileName, directory=""):
    if fileName in os.listdir(directory):
        return True
    return False

def getValueAfterLetter(gCodeLine, letter):
    gCodeLine = str(gCodeLine)
    letter = str(letter)
    startPos = gCodeLine.find(letter)
    if (gCodeLine.find(";") < startPos and gCodeLine.find(";") != -1) or startPos == -1:
        return None

    endPos = startPos + 1

    while endPos < len(gCodeLine):
        if " " in gCodeLine[endPos] or "\n" in gCodeLine[endPos] or ";" in gCodeLine[endPos]:
            break
        endPos += 1

    return gCodeLine[startPos+1:endPos].strip()


def gCodeParser(gCodeFile, commandsToInclude = ("G0 ", "G1 ")):
    gCodeList = []
    print("Reading File")
    with open(gCodeFile, "rb") as inFile:
        lenFile = len(inFile.readlines())
        inFile.seek(0)
        for index in range(lenFile):
            if index % pow(10, math.floor(math.log(lenFile, 10))-1) == 0:
                print("line:", index, " : ", str(100*index/lenFile) + "%")

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
def writeCodeList(codeList, params, notFoundChr=""):
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
            

def getParsedGCode(localFile="", writeCSV="out.csv", forceDownload=False):
    if localFile != "":
        parsedCode = gCodeParser(localFile)

    else:
        print("GETTING UPDATED INFO FROM PRINTER")
        
        respJson = get("http://octopi.local/api/job").json() # Get job status

        # Download the file if we don't already have it
        if not fileExistsInDir(respJson["job"]["file"]["name"], LOCAL_GCODE_DIRECTORY) or forceDownload:
            time.sleep(1) # Make sure we don't send to many requests
            # Get download link
            fileDownload = get("http://octopi.local/api/files/" + respJson["job"]["file"]["origin"] + "/" + respJson["job"]["file"]["name"]).json()["refs"]["download"]
            # TODO add check that a file is loaded
            print("File download link:", fileDownload, "\nDownloading now...")
            time.sleep(1) # Make sure we don't send to many requests
            downloadedText = get(fileDownload).content
            
            print("DONE GETTING DATA\n")
            
            with open(LOCAL_GCODE_DIRECTORY + respJson["job"]["file"]["name"], "wb") as outfile:
                outfile.write(downloadedText)
        
        parsedCode = gCodeParser(LOCAL_GCODE_DIRECTORY + respJson["job"]["file"]["name"])
        if writeCSV != "":
            writeCodeList(parsedCode, [b"X", b"Y", b"Z"])

    return parsedCode

# Returns the value of the parameter requested up to the line specified
def getParameterUpToLine(parsedGCode, parameter, lineNum):
    index = 0
    lastP = None
    while index < lineNum:
        if parsedGCode[index].hasParameter(parameter):
            lastP = parsedGCode[index].getParameter(parameter)
    return lastP


def getLayersByComments(parsedGCode):
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
                
def getPoints(layers, transform=[1,1,0,0]):
    points = []
    for layerNum, layer in enumerate(layers):
        points.append([])
        for command in layer:
            if command.getParameter(b"command") == b"G0" or command.getParameter(b"command") == b"G1":
                if command.hasParameter(b"X") and command.hasParameter(b"Y"):
                    points[layerNum].append([float(command.getParameter(b"X").decode("utf-8"))*transform[0]+transform[2], float(command.getParameter(b"Y").decode("utf-8"))*transform[1]+transform[3]])
    return points

def main(GRAPHICS):
    if GRAPHICS:
        screen = pygame.display.set_mode([1000,800])
        clock = pygame.time.Clock()
        pygame.font.init()
        myfont = pygame.font.SysFont('Comic Sans MS', 30)
        textsurface = myfont.render('Some Text', False, (0, 0, 0))
        points = None

        layer = 0
        frame = 0
        fileName = None
        while GRAPHICS:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.display.quit()
                    GRAPHICS = False
                    break
            if frame % 10 == 0:
                remoteFile = get("http://octopi.local/api/job").json()["job"]["file"]["name"]
                if remoteFile != fileName:
                    fileName = remoteFile
                    points = getPoints(getLayersByComments(getParsedGCode()), [min(screen.get_size())/210, -min(screen.get_size())/210, 0, min(screen.get_size())])
                    print("New File:", fileName, "\nNumber of layers:", len(points))
            screen.fill((255,255,255))
            pygame.draw.line(screen, (0,0,127), [0, 0], [min(screen.get_size())]*2)
            pygame.draw.line(screen, (0,0,127), [min(screen.get_size()), 0], [0, min(screen.get_size())])
            pygame.draw.line(screen, (0,0,127), [0, 0], [0, min(screen.get_size())])
            pygame.draw.line(screen, (0,0,127), [0, 0], [min(screen.get_size()), 0])
            pygame.draw.line(screen, (0,0,127), [min(screen.get_size()), 0], [min(screen.get_size())]*2)
            pygame.draw.line(screen, (0,0,127), [0, min(screen.get_size())], [min(screen.get_size())]*2)
            pygame.draw.circle(screen, (255,0,0), [int(point) for point in points[layer][0]], 5)
            pygame.draw.circle(screen, (255,0,0), [int(point) for point in points[layer][-1]], 5)
            for pointNum in range(len(points[layer])-1):
                #print(points[0][pointNum])
                pygame.draw.line(screen, (0,0,0), points[layer][pointNum], points[layer][pointNum+1])
            if frame % 1 == 0:
                layer = (layer+1)%len(points)
            
                
                
            pygame.display.flip()
            clock.tick(5)
            frame += 1
    else:
        getPoints(getLayersByComments(getParsedGCode()))


if __name__ == "__main__":
    main(GRAPHICS)
    

